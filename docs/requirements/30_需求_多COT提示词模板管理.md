# 需求30：多COT(H-CoT)提示词模板管理

## 背景

当前 CoT/H-CoT 流水线没有提示词模板管理功能。用户必须手动在数据库 Prompt 表中创建提示词（且需要精确匹配名称如 `[H-CoT] 3. L0 总问题生成`），才能运行流水线。单COT（Professional CoT）已实现了完整的文件化模板管理系统：内置默认提示词、副本自定义、树形浏览编辑。

用户希望为多COT流水线也提供同样级别的提示词管理，降低使用门槛。

## 输入输出定义

### 输入
- 系统内置默认提示词（覆盖 H-CoT 和 CoT 所有步骤）
- 用户自定义副本模板

### 输出
- 提示词模板管理页面（列表、详情、编辑）
- 流水线启动时可选择提示词模板
- 各步骤从模板读取提示词内容执行

## 详细规则

### 1. 提示词键格式
- 共享步骤：`common.{step_name}`（如 `common.fact_card_gen`）
- H-CoT专属：`hcot.{step_name}`（如 `hcot.l0_gen`）
- CoT专属：`cot.{step_name}`（如 `cot.question_gen`）

### 2. 存储结构（文件化，与单COT一致）
```
storage/hcot_prompt_templates/
  system/default_v1/
    manifest.json
    prompts/common/  prompts/hcot/  prompts/cot/
  users/{user_id}/
    preferences.json
    templates/{name}/manifest.json + prompts/
```

### 3. 模板管理CRUD
- 列出模板（系统模板 + 用户副本）
- 副本模板（从系统/其他模板复制）
- 编辑提示词内容
- 恢复单项默认
- 重命名/设为默认/删除（仅用户模板）

### 4. 流水线集成
- 流水线启动时可选 prompt_template_id
- 执行时优先从模板读取，回退到数据库 Prompt（向后兼容）
- 运行时创建提示词快照，确保历史一致性

### 5. 数据库变更
- tasks 表新增 `prompt_template_id` 列（VARCHAR(128), nullable）

## UI/接口变更

### 新增页面
- 多COT提示词管理页（路由 `/hcot-prompts`）
- 侧边栏菜单项"多COT提示词"

### 新增API
- `/api/cothcot/prompts/templates/*` 系列（9个端点）

### 修改
- 流水线启动对话框：添加模板选择下拉
- PipelineStartRequest：新增 `prompt_template_id` 可选字段