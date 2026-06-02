# 21. CoT/H-CoT 流水线一键生成与进度条改造

## 背景

当前 CoT/H-CoT 流水线需要用户在详情页逐步点击「运行」按钮手动执行每一步（6-10 步），进度追踪仅有三阶段粗粒度（0/1/2/3），无法感知 LLM 调用等耗时操作的内部进度。用户体验差，操作繁琐。

## 需求

### 需求1：一键生成（链式自动执行）

用户只需选择源文件、模式、LLM 配置，点一次按钮，后端自动按步骤顺序链式执行全部流程，无需手动逐步触发。

**后端新增接口**：
- `POST /cothcot/auto-run` — 创建流水线 + 一键启动全部步骤
- `POST /cothcot/auto-continue/{task_id}` — 从当前进度继续一键运行剩余步骤（适用于手动跑了几步后想自动跑完的场景）

**核心机制**：后端在单个后台 coroutine 中顺序执行每一步，前一步完成后自动推进到下一步。失败时停止推进，标记父任务为 FAILED。

### 需求2：细粒度进度条

**单步进度改造**：
- `progress_current/progress_total` 从 0-3 三阶段改为 0-100 百分比制
- 新增 `progress_label` 字段（VARCHAR(100)），显示当前阶段描述（如"调用 LLM 生成事实卡..."）
- 每步骤分为 5 个阶段：读取输入(0-5%) → 组装提示词(5-10%) → 调用 LLM(10-80/85%) → 解析输出(80-95%) → 写入文件(95-100%)

**流水线总进度**：
- 详情页顶部新增总进度条：已完成步骤数 / 总步骤数
- 步骤圆点追踪器，直观显示各步骤状态

### 需求3：前端改造

- WorkflowList.vue 创建弹窗增加「创建并一键运行」按钮
- WorkflowDetail.vue 新增「一键运行全部剩余步骤」按钮
- 单步进度条改为百分比制 + 阶段标签
- 轮询策略：动态间隔，LLM 调用中慢轮询(5s)，初始阶段快轮询(2s)

## 数据库变更

| 表 | 字段 | 类型 | 说明 |
|---|---|---|---|
| Task | progress_label | VARCHAR(100) | 步骤进度阶段描述 |

仅需新增一个字段，`progress_current/progress_total` 已有，改语义为百分比制。

## 文件变更清单

| 文件 | 改动 |
|---|---|
| `backend/app/models/models.py` | 新增 progress_label 列 |
| `backend/scripts/migrate_auto_run_progress.py` | 新迁移脚本 |
| `backend/app/services/cot_hcot_service.py` | 抽取 _run_single_step + PIPELINE_STEP_PHASES + auto-run/continue 逻辑 |
| `backend/app/routers/cot_hcot_pipeline.py` | 新增 auto-run / auto-continue 路由 |
| `frontend/src/api/index.js` | 新增 autoRunCothcotPipeline / autoContinueCothcotPipeline |
| `frontend/src/views/CotHcot/WorkflowDetail.vue` | 总进度条 + 一键运行按钮 + 百分比进度 + 动态轮询 |
| `frontend/src/views/CotHcot/WorkflowList.vue` | 一键运行按钮选项 |