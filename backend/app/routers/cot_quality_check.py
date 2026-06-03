"""CoT Quality Check router — Pipeline post-processing stage

对带思维链的 JSON 数据进行四维度深度质量评估。
逐条调用 LLM，解析 overall_quality 评级（三档：合格/存在缺陷/严重错误），按评级分桶输出三个文件。

Key design:
- User selects a file and provides an output name
- Backend flattens nested data, validates fields, then processes each record
- Creates three output JSON files: 通过（合格）、不通过（存在缺陷+严重错误）、评估结果
- Simple serial processing (one LLM call at a time, reliable)
- Supports pause/resume
"""

import asyncio
import json
import logging
import os
import traceback

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from typing import Optional, Tuple

from app.database import get_db, SessionLocal
from sqlalchemy import or_
from app.models.models import (
    File, Task, TaskLog, TaskStatusEnum,
    StageEnum, User, LLMConfig, Prompt,
)
from app.routers.auth import get_current_user
from app.services.llm_service import call_llm_json, LLMCallError
from app.services.cot_quality_check_service import (
    COT_QUALITY_CHECK_SYSTEM_PROMPT,
    normalize_cot_quality_check_records,
    _build_user_prompt,
    _PASS_RATINGS,
    _FAIL_RATINGS,
)
from app.services.file_service import create_output_file

logger = logging.getLogger("qa_studio.cot_quality_check")

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic request / response schemas
# ---------------------------------------------------------------------------


class CotQualityCheckStartRequest(BaseModel):
    file_id: int = Field(..., description="ID of the JSON file to process")
    output_name: str = Field(..., description="Base name for output files")
    prompt_id: Optional[int] = Field(None, description="ID of optional prompt override")
    model: Optional[str] = Field(None, description="Model name to use for LLM calls")
    llm_config_id: Optional[int] = Field(None, description="ID of the LLM config to use")


class TaskStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: int
    status: str
    progress_current: int
    progress_total: int
    pass_count: int = 0
    fail_count: int = 0
    file_id: Optional[int] = None
    filename: Optional[str] = None
    prompt_id: Optional[int] = None
    model: Optional[str] = None


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

# Field aliases for validation: chain_of_thought can be chainofThought or cot
_COT_QC_FIELD_ALIASES = {"chain_of_thought": ["chainofThought", "cot"]}


def _validate_flattened_fields(flat_data: list, stage: str) -> Tuple[bool, str, dict]:
    """Validate flattened data has required fields for this stage."""
    required = ["input", "chain_of_thought", "output"]
    aliases = _COT_QC_FIELD_ALIASES

    total = len(flat_data)
    if total == 0:
        return False, "JSON文件没有记录", {"total": 0, "qualified": 0}

    missing_counts: dict = {}
    qualified = 0

    for record in flat_data:
        if not isinstance(record, dict):
            for field in required:
                missing_counts[field] = missing_counts.get(field, 0) + 1
            continue

        has_all = True
        for field in required:
            value = record.get(field, "")
            if value is None or value == "" or value == [] or value == {}:
                found = False
                for alias in aliases.get(field, []):
                    alt_value = record.get(alias, "")
                    if alt_value and alt_value not in (None, "", [], {}):
                        found = True
                        break
                if found:
                    continue
                missing_counts[field] = missing_counts.get(field, 0) + 1
                has_all = False

        if has_all:
            qualified += 1

    stats = {"total": total, "qualified": qualified, "missing_fields": missing_counts}

    if qualified == 0:
        parts = [f"'{f}' 缺失 {c}/{total} 条" for f, c in missing_counts.items()]
        msg = f"文件不满足 {stage} 阶段字段要求: {', '.join(parts)}. 至少需要部分记录包含所有必需字段({', '.join(required)})"
        return False, msg, stats

    return True, "", stats


def _add_task_log(db: Session, task_id: int, content: str):
    log = TaskLog(task_id=task_id, log_content=content)
    db.add(log)
    db.commit()


def _update_progress(db: Session, task_id: int, current: int):
    task = db.query(Task).filter(Task.id == task_id).first()
    if task:
        task.progress_current = current
        db.commit()


def _flush_results_to_files(pass_file, fail_file, assessed_file, pass_items, fail_items, assessed_items):
    """将三个分桶结果写入对应的磁盘文件。"""
    for file_obj, items in [
        (pass_file, pass_items),
        (fail_file, fail_items),
        (assessed_file, assessed_items),
    ]:
        if file_obj is None:
            continue
        file_path = file_obj.file_path
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        logger.info("Written %d items to %s (file_id=%d)", len(items), file_obj.filename, file_obj.id)


# ---------------------------------------------------------------------------
# Background task runner — simple serial processing, reliable
# ---------------------------------------------------------------------------


async def _run_cot_quality_check_task(
    task_id: int,
    file_id: int,
    output_name: str,
    user_id: int,
    username: str,
    model: str = None,
    prompt_content: str = None,
    base_url_override: str = None,
    api_key_override: str = None,
):
    """Background coroutine: CoT质检 — 逐条串行 LLM 评估 + 按评级分桶。

    产出三个文件：通过（合格）、不通过（存在缺陷+严重错误）、评估结果（原数据+评估详情）。
    """
    db = SessionLocal()

    pass_file = None
    fail_file = None
    assessed_file = None
    pass_items = []
    fail_items = []
    assessed_items = []

    try:
        # ── 读取源文件 ──
        source_file = db.query(File).filter(File.id == file_id, File.user_id == user_id).first()
        if not source_file:
            _add_task_log(db, task_id, "源文件不存在")
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = TaskStatusEnum.FAILED
                db.commit()
            return

        with open(source_file.file_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        raw_items = normalize_cot_quality_check_records(raw_data)

        if not raw_items:
            _add_task_log(db, task_id, "源文件没有记录")
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = TaskStatusEnum.FAILED
                db.commit()
            return

        total = len(raw_items)

        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.progress_total = total
            task.source_file_id = file_id
            db.commit()

        _add_task_log(db, task_id, f"开始CoT质检，共 {total} 条记录")

        # ── 创建三个输出文件 ──
        pass_file = create_output_file(
            db=db, user_id=user_id, source_file=source_file,
            stage=StageEnum.COT_QUALITY_CHECK,
            output_filename=output_name, username=username,
            name_suffix="通过", initial_content=[], text_field="input",
        )
        fail_file = create_output_file(
            db=db, user_id=user_id, source_file=source_file,
            stage=StageEnum.COT_QUALITY_CHECK,
            output_filename=output_name, username=username,
            name_suffix="不通过", initial_content=[], text_field="input",
        )
        assessed_file = create_output_file(
            db=db, user_id=user_id, source_file=source_file,
            stage=StageEnum.COT_QUALITY_CHECK,
            output_filename=output_name, username=username,
            name_suffix="评估结果", initial_content=[], text_field="input",
        )

        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.file_id = assessed_file.id
            db.commit()

        _add_task_log(
            db, task_id,
            f"输出文件已创建: 通过={pass_file.filename}, "
            f"不通过={fail_file.filename}, 评估结果={assessed_file.filename}",
        )

        # ── 有效 system prompt ──
        effective_system_prompt = prompt_content or COT_QUALITY_CHECK_SYSTEM_PROMPT

        # ── 逐条串行处理 ──
        pass_count = 0
        fail_count = 0
        consecutive_failures = 0

        for idx, record in enumerate(raw_items):
            # ── 暂停检查 ──
            task_check = db.query(Task).filter(Task.id == task_id).first()
            if task_check and task_check.status == TaskStatusEnum.PAUSED:
                _flush_results_to_files(pass_file, fail_file, assessed_file, pass_items, fail_items, assessed_items)
                _add_task_log(db, task_id, f"任务已暂停，已将 {idx} 条数据写入文件")
                return

            # ── 连续失败保护 ──
            if consecutive_failures >= 10:
                _flush_results_to_files(pass_file, fail_file, assessed_file, pass_items, fail_items, assessed_items)
                _add_task_log(db, task_id, f"连续{consecutive_failures}次调用失败，任务终止")
                task = db.query(Task).filter(Task.id == task_id).first()
                if task:
                    task.status = TaskStatusEnum.FAILED
                    db.commit()
                return

            # ── 构造 prompt 并调用 LLM ──
            user_prompt = _build_user_prompt(record)

            try:
                llm_result = await call_llm_json(
                    prompt=user_prompt,
                    model=model,
                    system_prompt=effective_system_prompt,
                    temperature=0.3,
                    base_url_override=base_url_override,
                    api_key_override=api_key_override,
                    username=username,
                )
            except Exception as e:
                err_msg = str(e)[:200]
                logger.error("Task %d: LLM call failed for record %d: %s", task_id, idx, err_msg)
                _add_task_log(db, task_id, f"记录 {idx + 1}: LLM调用失败，归入不通过 - {err_msg}")
                # LLM失败 → 归入不通过
                fail_items.append(record)
                assessed_items.append({**record, "cot_quality_assessment": {
                    "overall_quality": "调用失败",
                    "evaluation_summary": f"LLM调用失败: {err_msg[:100]}",
                }})
                fail_count += 1
                consecutive_failures += 1
                _update_progress(db, task_id, idx + 1)
                continue

            consecutive_failures = 0

            # ── 解析评级 ──
            overall_quality = str(llm_result.get("overall_quality", "")).strip()

            # ── 构造评估结果记录 ──
            assessed_record = dict(record)
            assessed_record["cot_quality_assessment"] = llm_result
            assessed_items.append(assessed_record)

            if overall_quality in _PASS_RATINGS:
                pass_items.append(record)
                pass_count += 1
                _add_task_log(db, task_id, f"记录 {idx + 1}: CoT质检通过 - 评级={overall_quality}")
            elif overall_quality in _FAIL_RATINGS:
                fail_items.append(record)
                fail_count += 1
                _add_task_log(db, task_id, f"记录 {idx + 1}: CoT质检不通过 - 评级={overall_quality}")
            else:
                fail_items.append(record)
                fail_count += 1
                _add_task_log(db, task_id, f"记录 {idx + 1}: CoT质检评级未知({overall_quality})，归入不通过")

            _update_progress(db, task_id, idx + 1)

        # ── 最终写入三个输出文件 ──
        _flush_results_to_files(pass_file, fail_file, assessed_file, pass_items, fail_items, assessed_items)

        _add_task_log(
            db, task_id,
            f"CoT质检完成: 总计 {total} 条, 通过 {pass_count} 条({round(pass_count/total*100, 1) if total else 0}%), "
            f"不通过 {fail_count} 条({round(fail_count/total*100, 1) if total else 0}%)",
        )

        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = TaskStatusEnum.COMPLETED
            task.progress_current = total
            task.file_id = assessed_file.id
            db.commit()

        logger.info("Task %d completed: total=%d, pass=%d, fail=%d", task_id, total, pass_count, fail_count)

    except Exception as e:
        logger.error("Task %d unexpected error | user=%s: %s\n%s", task_id, username, str(e), traceback.format_exc())
        try:
            db.rollback()
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.status = TaskStatusEnum.FAILED
                db.commit()
            # 尝试将已有数据刷写到磁盘
            if assessed_file:
                _flush_results_to_files(pass_file, fail_file, assessed_file, pass_items, fail_items, assessed_items)
        except Exception:
            pass
    finally:
        db.close()


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------


@router.post("/start")
async def start_cot_quality_check(
    data: CotQualityCheckStartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a CoT quality check task."""
    file_obj = (
        db.query(File)
        .filter(File.id == data.file_id, File.user_id == current_user.id)
        .first()
    )
    if file_obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")

    # ── 校验字段（先展开嵌套） ──
    try:
        with open(file_obj.file_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
        flat_data = normalize_cot_quality_check_records(raw_data)
        is_valid, validation_msg, validation_stats = _validate_flattened_fields(flat_data, "cot_quality_check")
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"JSON文件解析失败: {str(e)}")

    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=validation_msg)

    # ── Resolve prompt (optional override) ──
    prompt_content = None
    prompt_id = None
    if data.prompt_id:
        prompt_obj = (
            db.query(Prompt)
            .filter(Prompt.id == data.prompt_id, or_(Prompt.user_id == current_user.id, Prompt.user_id.is_(None)))
            .first()
        )
        if prompt_obj is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="提示词不存在")
        prompt_content = prompt_obj.content
        prompt_id = prompt_obj.id

    # ── Resolve model ──
    effective_model = data.model
    if not effective_model:
        if prompt_id:
            prompt_obj = db.query(Prompt).filter(Prompt.id == prompt_id).first()
            if prompt_obj and prompt_obj.model:
                effective_model = prompt_obj.model
        if not effective_model:
            from app.config import settings
            effective_model = settings.effective_llm_model

    # ── Resolve LLM config overrides ──
    base_url_override = None
    api_key_override = None
    effective_llm_config_id = data.llm_config_id

    if prompt_id and not effective_llm_config_id:
        prompt_obj = db.query(Prompt).filter(Prompt.id == prompt_id).first()
        if prompt_obj:
            effective_llm_config_id = prompt_obj.llm_config_id

    if effective_llm_config_id:
        llm_config_obj = db.query(LLMConfig).filter(LLMConfig.id == effective_llm_config_id).first()
        if llm_config_obj is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="LLM配置不存在")
        if llm_config_obj.user_id != current_user.id and llm_config_obj.user_id is not None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权使用此LLM配置")
        base_url_override = llm_config_obj.base_url
        api_key_override = llm_config_obj.api_key

    # ── Create Task record ──
    task = Task(
        user_id=current_user.id,
        stage=StageEnum.COT_QUALITY_CHECK,
        file_id=data.file_id,
        model=effective_model,
        prompt_id=prompt_id,
        status=TaskStatusEnum.RUNNING,
        progress_current=0,
        progress_total=0,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # ── Launch background task ──
    asyncio.create_task(
        _run_cot_quality_check_task(
            task_id=task.id,
            file_id=data.file_id,
            output_name=data.output_name,
            user_id=current_user.id,
            username=current_user.username,
            model=effective_model,
            prompt_content=prompt_content,
            base_url_override=base_url_override,
            api_key_override=api_key_override,
        )
    )

    return {
        "task_id": task.id,
        "status": task.status.value,
        "progress_current": task.progress_current,
        "progress_total": task.progress_total,
    }


@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_cot_quality_check_status(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the status and progress of a CoT quality check task."""
    task = (
        db.query(Task)
        .filter(Task.id == task_id, Task.user_id == current_user.id)
        .first()
    )
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

    pass_count = db.query(TaskLog).filter(
        TaskLog.task_id == task_id,
        TaskLog.log_content.contains("CoT质检通过"),
    ).count()

    fail_count = db.query(TaskLog).filter(
        TaskLog.task_id == task_id,
        TaskLog.log_content.contains("CoT质检不通过"),
    ).count()
    fail_count += db.query(TaskLog).filter(
        TaskLog.task_id == task_id,
        TaskLog.log_content.contains("LLM调用失败，归入不通过"),
    ).count()
    fail_count += db.query(TaskLog).filter(
        TaskLog.task_id == task_id,
        TaskLog.log_content.contains("评级未知"),
    ).count()

    return TaskStatusResponse(
        task_id=task.id,
        status=task.status.value,
        progress_current=task.progress_current or 0,
        progress_total=task.progress_total or 0,
        pass_count=pass_count,
        fail_count=fail_count,
        file_id=task.file_id,
        filename=db.query(File).filter(File.id == task.file_id).first().filename if task.file_id else None,
        prompt_id=task.prompt_id,
        model=task.model,
    )


@router.get("/source-files")
async def list_source_files(
    show_all: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List JSON files for CoT quality check.

    默认只返回 source_stage=cot_hcot_pipeline 或 cot_filter 的文件；show_all=True 时返回所有 JSON。
    """
    target_stages = []
    if hasattr(StageEnum, "COT_HCOT_PIPELINE"):
        target_stages.append(StageEnum.COT_HCOT_PIPELINE)
    target_stages.append(StageEnum.COT_FILTER)
    target_stages.append(StageEnum.COT_QUALITY_CHECK)

    query = db.query(File).filter(
        File.user_id == current_user.id,
        File.file_type == "json",
    )
    if not show_all:
        query = query.filter(File.source_stage.in_(target_stages))
    files = query.order_by(File.created_at.desc()).all()

    return [
        {
            "id": f.id,
            "filename": f.filename,
            "source_stage": f.source_stage.value if f.source_stage else None,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        }
        for f in files
    ]