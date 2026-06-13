# 需求：单COT生成暂停/停止功能

## 背景

单COT生成（Professional CoT Pipeline）启动后，用户无法暂停或停止任务。后台任务 `run_pipeline_sync()` 在文献循环中没有检查 manifest 状态变化，一旦启动就跑到完成或失败。用户只能等待任务自然结束，或者重启服务（触发僵尸恢复），体验很差。

## 目标

为单COT生成添加协作式暂停功能：
- 用户可在任务运行中点击"暂停运行"
- 后台任务在当前文献处理完成后停止，已处理进度保留
- 用户可从暂停处"恢复运行"，跳过已处理的文献继续跑

## 规则

### 暂停机制
1. 暂停为**软停止**：后台任务检测到暂停信号后，完成当前文献处理再退出
2. 暂停信号通过修改 manifest.json 的 status 字段为 `"paused"` 实现
3. 后台循环在每次文献边界和每次步骤更新时重新读取 manifest，检测 paused
4. 检测到 paused 时，抛出 `_PipelinePausedError` 异常中断处理，将步骤状态重置为 pending

### 恢复机制
1. 只有 paused 或 failed 状态的 run 可以恢复
2. 恢复时从 `batch_summary.json` 加载已处理文献索引，跳过已完成的文献
3. 恢复后增量追加新处理结果到已有产物

### 前端交互
1. 详情页：running 状态显示"暂停运行"按钮（warning 色）
2. 详情页：paused/failed 状态显示"恢复运行"按钮（success 色）
3. 列表页：running 行显示"暂停"操作按钮

## 接口变更

### 新增 API
- `POST /professional-cot/runs/{run_id}/pause` — 暂停正在运行的 run
  - 请求：无额外参数
  - 响应：`{ run_id, status: "paused", message }`
  - 错误：404（不存在）、403（无权限）、400（非 running 状态）

### 现有 API 变更
- `POST /professional-cot/runs/{run_id}/resume` — 无变更，但恢复续跑逻辑改进（跳过已处理文献）