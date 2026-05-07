# COT过滤 & 数据集处理功能迁移方案

## 背景

将 `QA_Gen_Studio` 项目中的 **COT过滤** 和 **数据集处理（切分+评分）** 两个功能迁移到当前 `QA_Studio` 系统，遵循现有项目的架构风格（Vue + Element Plus + FastAPI + MySQL）。

## 一、功能概述

### 1. COT过滤页面 (`/cot-filter`)

**功能**：上传或指定 JSON 文件，将 QA 记录按 `cot`（推理链）字段是否为空分成两组，生成两个新 JSON 文件，支持下载。

**特点**：纯本地处理，不调用 LLM，速度很快。

**输入**：JSON 文件（上传或选择已有文件）
**输出**：两个 JSON 文件 — COT不为空文件 + COT为空文件
**结果展示**：总记录数、COT不为空数量、COT为空数量、占比百分比、下载按钮

### 2. 数据集处理页面 (`/dataset-processing`)

**功能**：在同一页面完成 **测试集切分** 和 **简答题评分标准生成** 两个操作。

#### 2a. 数据集切分

**功能**：将完整 QA 数据按策略切分为 train/test 两个子集，写入数据库。

**切分策略**：
- `difficulty_priority`：按难度优先（较难→中等→基础），保证各题型在测试集中有代表
- `task_type_random`：按题型比例随机选取，保持比例均衡

**输入**：JSON 文件（上传或选择已有文件）
**参数**：测试集数量、输出名称、切分策略
**输出**：train.json + test.json，同时写入数据库 Dataset 和 QA 记录
**结果展示**：测试集/训练集数量、各题型分布、跳过非QA条目数

#### 2b. 评分标准生成

**功能**：对测试集中的简答题，通过 LLM 生成评分标准（Assessment 字段），包含评分点、满分标准、失分规则。

**输入**：测试集 JSON 文件
**参数**：输出名称、LLM模型、配置版本
**输出**：带 Assessment 字段的 JSON 文件
**验证规则**：至少2个评分点、总分=100、每个评分点需满分标准和失分规则、不允许"酌情给分"
**结果展示**：QA条目数、简答题数量、已生成评分数、空评分数

---

## 二、适配改造要点

源项目 `QA_Gen_Studio` 使用原生 HTML + CSS（无 UI 框架），有独立的 job_runner 线程调度、workspace 文件系统、server_path + password 模式。当前 `QA_Studio` 使用 Element Plus + 已有 Task/文件管理体系。需要做以下适配：

### 去除 server_path 模式
- QA_Studio 已有完善的文件上传/管理体系，不需要"服务器路径+密码"这种入口
- 所有输入统一走 **上传文件** 或 **选择已有文件** 两种方式（与现有 FileSelector 组件一致）

### 任务调度适配
- QA_Studio 已有 Task 模型（id, status, progress_current, progress_total, stage 等）和 polling 机制
- 切分和评分是后台任务，复用现有 Task 表和轮询逻辑
- 新增 `stage` 枚举值：`cot_filter`、`dataset_split`、`dataset_assessment`
- 评分任务需要 LLM 配置，复用现有 `LLMConfig` 和 `PromptConfig` 体系

### 数据库适配
- 切分结果需要写入 Dataset 表，QA_Studio 已有 Dataset 模型
- 评分生成的 Assessment 字段写入 Dataset 表的对应记录

### UI 风格适配
- 使用 Element Plus 组件（el-card, el-form, el-select, el-button, el-progress 等）
- COT过滤页面：左侧输入配置 + 右侧结果展示（两栏布局，与现有页面风格一致）
- 数据集处理页面：上方切分区块 + 下方评分区块（或左右两栏），每个区块包含输入、参数、进度、结果

---

## 三、新增文件清单

### 前端

| 层级 | 文件路径 | 说明 |
|------|---------|------|
| 页面 | `frontend/src/views/CotFilter.vue` | COT过滤页面 |
| 页面 | `frontend/src/views/DatasetProcessing.vue` | 数据集处理页面（切分+评分） |
| API | `frontend/src/api/index.js` | 新增 `filterCot`, `startDatasetSplit`, `startDatasetAssessment`, `getDatasetSplitSourceFiles`, `getDatasetAssessmentSourceFiles` 等函数 |
| 路由 | `frontend/src/router/index.js` | 新增 `/cot-filter` 和 `/dataset-processing` 路由 |
| 导航 | `frontend/src/views/Layout.vue` | 侧边栏新增"COT过滤"和"数据集处理"菜单项 |

### 后端

| 层级 | 文件路径 | 说明 |
|------|---------|------|
| 路由 | `backend/app/routers/cot_filter.py` | COT过滤 API 路由 |
| 路由 | `backend/app/routers/dataset_processing.py` | 数据集切分+评分 API 路由 |
| 服务 | `backend/app/services/cot_filter_service.py` | COT过滤核心逻辑（从 filter_service.py 迁移） |
| 服务 | `backend/app/services/split_service.py` | 数据集切分核心逻辑 |
| 服务 | `backend/app/services/assessment_service.py` | 评分标准生成核心逻辑 |
| 模型 | `backend/app/models/models.py` | StageEnum 新增 `cot_filter`, `dataset_split`, `dataset_assessment` |

---

## 四、API 设计

### COT过滤

```
POST /api/cot-filter/start
请求体: { file_id: int, output_name: string }
响应: { task_id: int }

GET /api/cot-filter/source-files
响应: { items: [{ id, filename, record_count }] }

GET /api/cot-filter/download/{task_id}?type=with_cot|without_cot
响应: JSON 文件流
```

流程：选择文件 → 提交任务 → 后台执行过滤 → 前端轮询进度 → 完成后展示统计 + 下载按钮

### 数据集切分

```
POST /api/dataset-split/start
请求体: { file_id: int, test_count: int, output_name: string, split_strategy: string }
响应: { task_id: int }

GET /api/dataset-split/source-files
响应: { items: [{ id, filename, record_count }] }
```

### 评分标准生成

```
POST /api/dataset-assessment/start
请求体: { file_id: int, output_name: string, prompt_id: int, model: string, llm_config_id: int }
响应: { task_id: int }

GET /api/dataset-assessment/source-files
响应: { items: [{ id, filename, record_count }] }
```

---

## 五、页面布局设计

### COT过滤页面

```
┌─────────────────────────────────────────────────┐
│ COT过滤                                          │
│ ┌──────────────────┬─────────────────────────┐   │
│ │ 输入配置          │ 过滤结果                 │   │
│ │                  │                         │   │
│ │ 选择文件          │ 总记录: 120             │   │
│ │ [FileSelector]   │ COT不为空: 85 (70.8%)  │   │
│ │                  │ COT为空: 35 (29.2%)     │   │
│ │ 输出名称          │                         │   │
│ │ [el-input]       │ [下载COT不为空] [下载COT为空] │ │
│ │                  │                         │   │
│ │ [开始过滤]        │                         │   │
│ └──────────────────┴─────────────────────────┘   │
│                                                  │
│ [进度条 - 如果有任务]                              │
│ [任务日志]                                        │
└─────────────────────────────────────────────────┘
```

### 数据集处理页面

```
┌─────────────────────────────────────────────────┐
│ 数据集处理                                        │
│                                                  │
│ ┌── 切分区块 ──────────────────────────────────┐ │
│ │ config-layout: 左表单 + 右进度/结果            │ │
│ │                                              │ │
│ │ 左侧:                                        │ │
│ │  选择文件 [FileSelector]                      │ │
│ │  测试集数量 [el-input-number]                  │ │
│ │  输出名称 [el-input]                           │ │
│ │  切分策略 [el-select]                          │ │
│ │  [执行切分]                                    │ │
│ │                                              │ │
│ │ 右侧: 进度条 + 结果统计                        │ │
│ └──────────────────────────────────────────────┘ │
│                                                  │
│ ┌── 评分区块 ──────────────────────────────────┐ │
│ │ config-layout: 左表单 + 右进度/结果            │ │
│ │                                              │ │
│ │ 左侧:                                        │ │
│ │  选择文件 [FileSelector]                      │ │
│ │  输出名称 [el-input]                           │ │
│ │  选择Prompt [el-select] + 右侧PromptPreview  │ │
│ │  LLM配置 [el-select]                          │ │
│ │  选择模型 [el-select]                          │ │
│ │  [生成评分标准]                                │ │
│ │                                              │ │
│ │ 右侧: PromptPreview + 进度条 + 结果统计       │ │
│ └──────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

---

## 六、核心逻辑迁移说明

### COT过滤 (`cot_filter_service.py`)
- 从 `filter_service.py` 迁移核心函数 `filter_cot_items`
- 逻辑很简单：遍历 JSON 记录，按 `cot` 字段是否为空分组，写入两个文件
- 适配点：输入从 file_id 获取文件路径（通过现有 File 模型），输出文件存入 uploads 目录并注册到 File 模型

### 数据集切分 (`split_service.py`)
- 从原 `split_service.py` 迁移 `run_split_job` 核心逻辑
- `select_test_set` 模块需要迁移（切分算法 `split_items`, `load_output_items`, `write_items`, `summarize_task_counts`）
- 适配点：输入从 file_id 获取；切分结果写入数据库（复用 Dataset 模型）；输出文件注册到 File 模型供后续使用

### 评分标准生成 (`assessment_service.py`)
- 从原 `assessment_service.py` 迁移 `run_assessment_job` 核心逻辑
- `fill_qa_assessment` 模块需要迁移（LLM 调用、评分验证、修复重试）
- 适配点：LLM 调用复用现有 `llm_service.py` 的封装；Prompt 从 PromptConfig 体系加载（不再从文件系统加载）；输入从 file_id 获取

---

## 七、实施步骤

1. **后端模型**：在 `models.py` 的 `StageEnum` 新增 3 个枚举值
2. **后端服务**：迁移并适配 3 个 service 文件
3. **后端路由**：创建 2 个 router 文件，实现 API
4. **前端API**：在 `api/index.js` 新增对应函数
5. **前端页面**：创建 `CotFilter.vue` 和 `DatasetProcessing.vue`
6. **前端路由**：在 router 新增 2 个路由
7. **前端导航**：在 Layout.vue 侧边栏新增菜单项
8. **测试验证**：逐个功能测试

---

## 八、注意事项

- 评分功能依赖 LLM 调用，需要确保 Prompt 配置体系中有评分相关的 Prompt（需要新增 `dataset_assessment` stage 的默认 Prompt）
- 切分策略中的题型校验（单选/多选/判断/填空/简答）依赖 `task_type` 字段，QA_Studio 的 Dataset 模型已有此字段
- 评分验证的修复重试机制需要保留，这是保证评分质量的关键逻辑
- COT过滤是即时操作（数据量不大时秒级完成），可以考虑直接返回结果而不用 Task 轮询；但如果文件很大也可以走 Task 体系