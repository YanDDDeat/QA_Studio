# 需求：多COT生成指定内容字段

## 背景

在「CoT/H-CoT 标注 → 多COT生成 → 新建多COT生成」中，用户选择 JSON 源文件后，当前后端默认按 `input -> originContent` 的顺序读取内容。如果 JSON 文件使用了其他字段名，可能导致源内容为空、任务无法正常产出，且用户在创建任务时无法显式指定字段。

## 输入输出定义

### 输入

- 流水线名称
- 标注模式：`hcot` / `cot`
- 源文件：系统文件中的 JSON 文件
- 内容字段名：用户指定 JSON 中作为原文/正文的字段名
- LLM 配置
- 提示词模板（可选）

### 输出

- 创建 CoT/H-CoT 流水线任务
- 后端使用用户指定字段作为每条 JSON 记录的内容来源，生成 fact card 及后续 CoT/H-CoT 产物

## 详细规则

1. 在新建多COT生成弹窗中，源文件下方新增「内容字段名」输入框。
2. 用户选择源文件后，输入框默认使用该文件保存的 `text_field`；若文件没有该值，默认 `text`。
3. 用户可以手动修改字段名，例如 `text`、`content`、`originContent`、`paper_text`。
4. 创建/一键运行任务时，前端将字段名提交给后端。
5. 后端接收字段名后，在读取 JSON 文件写入 Dataset 时优先将该字段映射为 `originContent`。
6. 如果未填写字段名，保持现有兼容逻辑：优先读取 `input`，否则读取 `originContent`。
7. 不新增数据库表或列，复用现有 `files.text_field` 存储字段偏好。

## UI / 接口变更说明

### 前端

修改 `frontend/src/views/CotHcot/WorkflowList.vue`：

- `createForm` 新增 `content_field`。
- 弹窗新增「内容字段名」表单项。
- 选择源文件时自动填充为该文件的 `text_field || 'text'`。
- 提交 `/cothcot/start` 与 `/cothcot/auto-run` 时携带 `content_field`。

### 后端

修改 `backend/app/routers/cot_hcot_pipeline.py`：

- `PipelineStartRequest` 新增可选 `content_field`。
- 创建父任务前，将源文件 `text_field` 更新为用户指定值。
- `/source-files` 返回 `text_field`，供前端默认填充。

修改 `backend/app/services/file_service.py`：

- `ensure_datasets_for_file()` 支持基于 `File.text_field` 将指定 JSON 字段映射到 `originContent`。

修改 `backend/app/services/cot_hcot_service.py`：

- `_get_source_chunks()` 调用 `ensure_datasets_for_file()` 时继续复用文件上的 `text_field`。

## 验证方式

1. 选择包含自定义字段（如 `paper_text`）的 JSON 源文件。
2. 在「内容字段名」中填写 `paper_text`。
3. 点击「创建并一键运行」或「创建并启动首步」。
4. 确认任务日志不再因为缺少 `originContent`/`input` 而无内容，fact card 步骤可以读取到正文。
5. 验证旧文件未填写内容字段时仍兼容 `input` / `originContent` / `text` / `content`。
