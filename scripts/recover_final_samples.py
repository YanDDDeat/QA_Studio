"""恢复单COT流水线的 final_samples.json

Bug：恢复运行时 per-doc 样本加载失败（文件名不匹配），
导致 run 级别的 final_samples.json 被不完整的 all_samples 覆盖。
本脚本从 per-document 产物重新聚合成完整的 final_samples.json。

用法：
    python scripts/recover_final_samples.py <run_id>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
STORAGE_ROOT = PROJECT_ROOT / "storage" / "professional_cot_runs"


def recover(run_id: str) -> int:
    run_dir = STORAGE_ROOT / run_id
    if not run_dir.exists():
        print(f"错误：运行目录不存在 {run_dir}")
        return 1

    documents_dir = run_dir / "documents"
    if not documents_dir.exists():
        print(f"错误：documents 目录不存在 {documents_dir}")
        return 1

    all_samples = []
    error_docs = []

    for doc_dir in sorted(documents_dir.iterdir()):
        if not doc_dir.is_dir():
            continue
        sample_file = doc_dir / "final_samples.json"
        if not sample_file.exists():
            # 尝试旧格式：直接存 sample 而非 wrapper
            old_file = doc_dir / "final_sample.json"
            if old_file.exists():
                sample_file = old_file
            else:
                continue

        try:
            data = json.loads(sample_file.read_text(encoding="utf-8"))
            if "samples" in data and isinstance(data["samples"], list):
                all_samples.extend(data["samples"])
            elif isinstance(data, dict) and "cot_type" in data:
                # 裸 sample dict
                all_samples.append(data)
            else:
                print(f"警告：无法识别格式 {sample_file}")
        except Exception as exc:
            error_docs.append((doc_dir.name, str(exc)))
            print(f"错误：读取 {sample_file} 失败：{exc}")

    if error_docs:
        print(f"\n{len(error_docs)} 个文献产物读取失败：")
        for name, err in error_docs:
            print(f"  - {name}: {err}")

    if not all_samples:
        print("未找到任何有效样本！")
        return 1

    # 重新编号 id
    for idx, sample in enumerate(all_samples, start=1):
        sample["id"] = idx

    # 生成完整的 final_samples.json
    final_payload = {
        "schema_version": "1.0",
        "run_id": run_id,
        "pipeline_name": "单COT生成流水线",
        "sample_count": len(all_samples),
        "samples": all_samples,
    }
    output_path = run_dir / "final_samples.json"
    backup_path = run_dir / "final_samples.json.bak"
    if output_path.exists():
        output_path.rename(backup_path)
        print(f"已备份原文件到 {backup_path.name}")

    output_path.write_text(
        json.dumps(final_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"已写入 {output_path}")
    print(f"恢复完成：共 {len(all_samples)} 条样本")

    # 同时更新 manifest 中的 sample_count
    manifest_path = run_dir / "manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["sample_count"] = len(all_samples)
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"已更新 manifest.json 的 sample_count 为 {len(all_samples)}")
        except Exception as exc:
            print(f"警告：更新 manifest 失败：{exc}")

    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：python scripts/recover_final_samples.py <run_id>")
        sys.exit(1)
    sys.exit(recover(sys.argv[1]))
