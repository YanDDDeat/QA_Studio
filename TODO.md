# QA_Studio TODO List
完成一个需求后勾选需求，然后继续执行新的需求，直到全部勾选完毕。

## 基础设施
- [x] 项目初始化：Vue 前端 + FastAPI 后端 + MySQL 数据库
- [x] 数据库表结构设计与建表
- [x] .env 配置文件（数据库连接、LLM API Key 等）
- [x] 前端路由与页面框架搭建

## 用户管理
- [x] 管理员手动创建账号功能（无注册）
- [x] 登录认证机制
- [x] 用户数据隔离（每个用户只看到自己的数据）

## LLM 调用模块
- [x] 抽离统一 LLM 调用方法：输入提示词，返回文本解析结果
- [x] OpenAI 兼容接口对接（baseURL + API Key + model）
- [x] 逐条调用逻辑（不批量并发）
- [x] 多用户独立调用，互不影响

## 配置中心
- [x] 每个 LLM 调用环节独立配置提示词
- [x] 提示词修改时新增版本，保留历史版本
- [x] 每个用户独立管理自己的提示词
- [x] 每个环节可选择使用的模型

## 文件上传与管理
- [x] 上传一个或多个 JSON 文件
- [x] 上传时指定文本块字段名，默认 "text"
- [x] 工作区文件管理页面：查看、下载、删除
- [x] 校验失败记录文件的自动生成与展示

## ========== Pipeline 重构（核心修正） ==========

原因：原设计以"逐条选择Dataset记录"为单元，违背需求规格。正确设计应以JSON文件为核心载体，所有阶段选文件执行，结果覆盖写回同一个JSON文件。详见 `需求补充说明.md`。

### 共性改动（影响所有阶段）
- [x] 抽离文件写回服务：处理完成后，将Dataset记录同步覆盖写回JSON文件（新增 `backend/app/services/file_service.py`）
- [x] Dataset表增加 `file_id` 字段，关联每条记录属于哪个JSON文件
- [x] 任务日志持久化：页面加载时自动查询最近任务，恢复状态/进度/日志显示

### 问题生成（Pipeline 阶段1）— 修正
- [x] 产出新JSON文件（不是只存数据库），文件名如 `原文件名_问题生成.json`
- [x] 处理完成后写回JSON文件，每条记录包含所有已生成字段
- [x] 任务日志持久化：页面加载时自动恢复上次任务状态

### 知识体系生成（Pipeline 阶段2）— 重构
- [x] 前端改为选择JSON文件（下拉选文件），不是逐条选记录
- [x] 读取选中JSON文件的所有记录，逐条调用LLM
- [x] 处理完成后覆盖写回同一个JSON文件，追加 `knowledge` + `scene` 字段
- [x] 任务日志持久化

### 问题校验（Pipeline 阶段3）— 重构
- [x] 前端改为选择JSON文件（下拉选文件），不是逐条选记录
- [x] 读取选中JSON文件的所有记录，逐条调用LLM校验
- [x] PASS记录：覆盖写回原文件（不保留validation_result/reason）
- [x] FAIL记录：从原文件剔除，单独生成fail JSON文件到文件管理区
- [x] 任务日志持久化

### 答案生成（Pipeline 阶段4）— 重构
- [x] 前端改为选择JSON文件（下拉选文件），不是逐条选记录
- [x] 读取选中JSON文件的所有记录（仅PASS的），逐条调用LLM
- [x] 处理完成后覆盖写回同一个JSON文件，追加 `output` + `cot` 字段
- [x] 任务日志持久化

### 答案校验（Pipeline 阶段5）— 重构
- [x] 前端改为选择JSON文件（下拉选文件），不是逐条选记录
- [x] 读取选中JSON文件的所有记录，逐条调用LLM校验
- [x] PASS记录：覆盖写回原文件（不保留校验字段）
- [x] FAIL记录：从原文件剔除，单独生成fail JSON文件到文件管理区
- [x] 任务日志持久化

### 数据评估（Pipeline 阶段6）— 重构
- [x] 前端改为选择JSON文件（下拉选文件），不是逐条选记录
- [x] 读取选中JSON文件的所有记录（仅PASS的），逐条调用LLM评分
- [x] 处理完成后覆盖写回同一个JSON文件，追加 `relevance, clarity, reasoning, terminology, score` 字段
- [x] 任务日志持久化

## ========== 需求补充2：文件选择不限制阶段 + 删除策略修正 ==========

### 文件选择放开阶段限制
- [x] 后端：所有阶段的 `/source-files` 端点改为返回用户的全部JSON文件，不按阶段过滤（执行时只处理符合条件的记录，不符合的自动跳过）
- [x] 前端：所有Pipeline阶段的文件下拉改为显示用户全部JSON文件

### 文件删除策略修正
- [x] 后端：删除文件时，仅阻止删除正在运行中（status=running）的Task引用的文件；已完成/失败的Task引用的文件允许删除，并将对应Task的file_id设为NULL

### 侧边栏导航层级优化
- [x] 前端：Layout.vue侧边栏改为分组折叠式二级菜单：问题生成→(问题生成|知识体系生成|问题校验)、答案生成→(答案生成|答案校验)、数据评估→(数据评估)、管理中心→(配置中心|用户管理|数据中心)

## ========== 原已完成项（保留） ==========

## 数据管理
- [x] 表格展示数据集记录，只展示当前用户数据
- [x] 超长文本截断显示，超过字数限制显示 "..."
- [x] 分页：10条/页
- [x] 单击记录查看详情页
- [x] 详情页字段支持 LaTeX 公式渲染

## 任务日志
- [x] 每个生成任务提供实时日志
- [x] 前端只渲染最新 200 条日志

## ========== 需求补充3：交互优化与LLM配置中心 ==========

详细设计见 `需求补充_交互与LLM配置.md`。实施顺序：先做 LLM 配置中心（影响数据模型），再做提示词面板，阶段页上传 / 结果区可并行。

### LLM 配置中心（核心变更，最先实施）
- [x] 数据库：新增 `llm_configs` 表（id, user_id NULL=全局, name, base_url, api_key 明文, models JSON, default_model, created_at, updated_at）
- [x] 数据库：`prompts` 表新增 `llm_config_id` 字段（保留 `model` 字符串字段兼容历史数据）
- [x] 编写迁移脚本 `scripts/migrate_llm_config.py`：建表 + 加字段 + seed dashscope/swust 两条全局配置（user_id=NULL）+ 历史 Prompt 数据按 model 字符串匹配关联（匹配不到默认 dashscope）
- [x] ORM：在 `models/models.py` 新增 `LLMConfig` 模型，`Prompt` 模型加 `llm_config_id` 字段与关系
- [x] 后端：新增 `routers/llm_config.py`，包含 GET / POST / PUT / DELETE / POST `/test` 五个端点
- [x] 后端：管理员身份判定按 `username == 'admin'`；权限矩阵按需求文档执行
- [x] 后端：`/test` 端点发起一次真实简答对话（如"你好"），返回 `{ ok, latency_ms, reply, error }`
- [x] 后端：`services/llm_service.py` 的 `call_llm()` / `call_llm_json()` 新增参数，路由层先查表注入 base_url/api_key/model；老调用方式保留兼容
- [x] 后端：6 个阶段路由改造，执行任务时优先通过 `Prompt.llm_config_id` 拿配置传入 `call_llm()`
- [x] 前端：配置中心新增 "LLM 配置" tab，列表展示 name / base_url / 模型数 / 默认模型 / 归属（我的/全局）/ 操作
- [x] 前端：内置模板区域，dashscope / swust 两张卡片，"使用此模板"按钮只需填 API KEY 即创建用户私有配置
- [x] 前端："新建空白配置"表单，admin 用户多一个"设为全局共享"开关
- [x] 前端：每条配置加"测试连接"按钮，调 `/test` 端点 toast 显示延迟 + 回复片段或错误
- [x] 前端：阶段页"模型"下拉重构为两级（先选 LLM 配置，再选该配置下的 model）
- [x] 前端：保存提示词时同时存 `llm_config_id` 和 `model` 字符串

### 提示词预览 + 内联编辑面板（依赖 LLM 配置）
- [x] 6 个阶段页右侧加抽屉式面板，默认展开（可手动收起/重展）
- [x] 切换提示词或版本下拉时，抽屉内容自动同步为最新选中的 content
- [x] 抽屉展示：版本号、创建时间、content（等宽字体 + 多行滚动）
- [x] 文本框默认可编辑，底部"保存为新版本"按钮调 `POST /api/prompts` 创建 version+1 记录
- [x] 保存成功后自动切换到新版本，下拉刷新；不允许覆盖旧版本

### 阶段页内直接上传源文件（独立改动，可并行）
- [x] 6 个阶段页文件下拉旁加"上传新文件"按钮
- [x] 弹窗包含：文件选择（仅 .json）+ text_field 输入框（默认 "text"）+ 提交按钮
- [x] 提交走现有 `POST /api/files/upload`，上传成功后自动刷新下拉、自动选中刚上传的文件、关闭弹窗

### 阶段页结果区（独立改动，可并行）
- [x] 后端：`GET /api/datasets` 接口新增可选参数 `stage`（按当前阶段过滤记录）
- [x] 6 个阶段页底部加可折叠"生成结果"区，默认折叠，标题栏显示当前选中文件名
- [x] 顶部按钮"加载最新结果"，懒加载（用户主动点击才请求）
- [x] 调 `GET /api/datasets?file_id={file_id}&stage={stage}&page=1&page_size=10`
- [x] 各阶段表格列按需求文档定义（问题生成/知识体系生成/问题校验/答案生成/答案校验/数据评估各自展示该阶段相关字段）
- [x] 长文本字段超过限制截断显示 "..."；单击行弹出详情（复用数据中心 detail 组件，含 LaTeX 渲染）

## ========== 需求补充4：文件选择与Prompt选择UI重构 ==========

### 文件选择组件重构
- [x] 新建 `frontend/src/components/FileSelector.vue`：先让用户选"上传新文件"或"选择已有文件"，选中后按方式显示上传区或已有文件下拉
- [x] 6个阶段页替换旧 file-select-row 为 FileSelector 组件

### Prompt选择组件重构
- [x] 新建 `frontend/src/components/PromptPreview.vue`：选择prompt后右侧同页面显示完整内容（不再用弹出框/抽屉），支持内联编辑和"保存为新版本"
- [x] 6个阶段页改为左右两栏布局：左栏表单字段（含FileSelector和prompt下拉），右栏PromptPreview面板
- [x] 移除所有 el-drawer（提示词预览）和 el-dialog（文件上传弹窗）

## ========== 需求补充5：COT过滤 & 数据集处理（迁移自QA_Gen_Studio） ==========

从 `D:\SWUST\10_语料数据库构建\new_QA_generate\QA_Gen_Studio` 迁移 COT过滤和数据集处理功能，适配本系统架构风格（Element Plus + FastAPI + MySQL + FileSelector + Task轮询）。

### 数据模型扩展
- [x] `models/models.py` StageEnum 新增 `cot_filter`、`dataset_split`、`dataset_assessment` 三个枚举值
- [x] 编写迁移脚本 `scripts/migrate_cot_dataset.py`：更新 StageEnum + seed assessment Prompt

### COT过滤功能
- [x] 后端：新建 `routers/cot_filter.py`，实现 `POST /api/cot-filter/start`（提交过滤任务）和 `GET /api/cot-filter/source-files`（获取可选文件列表）
- [x] 后端：新建 `services/cot_filter_service.py`，核心逻辑：读取JSON文件，按cot字段是否为空分成两组，写入两个新JSON文件，注册到File模型，返回统计信息
- [x] 前端API：`api/index.js` 新增 `startCotFilter`、`getCotFilterStatus`、`getCotFilterSourceFiles` 函数
- [x] 前端页面：新建 `views/CotFilter.vue`，左右两栏布局 — 左侧输入配置（FileSelector + 输出名称 + 开始过滤按钮），右侧结果展示（总记录数/COT不为空/COT为空 + 百分比 + 下载按钮）+ 进度条 + 任务日志
- [x] 前端路由：`router/index.js` 新增 `/cot-filter` 路由
- [x] 前端导航：`Layout.vue` 侧边栏新增"COT过滤"菜单项（归属"数据后处理"分组）

### 数据集切分功能
- [x] 后端：新建 `routers/dataset_split.py`，实现 `POST /api/dataset-split/start`（提交切分任务）和 `GET /api/dataset-split/source-files`
- [x] 后端：新建 `services/split_service.py`，核心逻辑迁移：split_items（difficulty_priority/task_type_random两种策略）→ 写入两个JSON文件 + 注册到File模型
- [x] 后端：迁移 `studio_core/select_test_set.py` 中的切分算法（split_items, validate_records, select_test_records_difficulty_priority, select_test_records_task_type_random, summarize_task_counts）
- [x] 前端API：`api/index.js` 新增 `startDatasetSplit`、`getDatasetSplitStatus`、`getDatasetSplitSourceFiles` 函数
- [x] 前端页面：在 `DatasetProcessing.vue` 中实现切分区块 — 左侧配置（FileSelector + 测试集数量 + 输出名称 + 切分策略下拉 + 执行按钮），右侧进度/结果（进度条 + 统计：测试集/训练集数量 + 各题型分布 + 日志）
- [x] 前端路由：`router/index.js` 新增 `/dataset-processing` 路由

### 评分标准生成功能
- [x] 后端：新建 `routers/dataset_assessment.py`，实现 `POST /api/dataset-assessment/start`（提交评分任务）和 `GET /api/dataset-assessment/source-files`
- [x] 后端：新建 `services/assessment_service.py`，核心逻辑迁移：加载输入 → 识别简答题 → LLM生成评分标准 → 验证（至少2评分点、总分100、每点需满分标准和失分规则、不允许"酌情给分"）→ 失败时修复重试 → 写回JSON文件 + 注册到File模型
- [x] 后端：迁移 `studio_core/fill_qa_assessment.py` 中的评分生成逻辑，适配本系统 llm_service.py 的调用方式
- [x] 配置中心：新增 `dataset_assessment` stage 的默认 Prompt（评分标准生成提示词）— 通过迁移脚本 seed
- [x] 前端API：`api/index.js` 新增 `startDatasetAssessment`、`getDatasetAssessmentStatus`、`getDatasetAssessmentSourceFiles` 函数
- [x] 前端页面：在 `DatasetProcessing.vue` 中实现评分区块 — 左侧配置（FileSelector + 输出名称 + Prompt选择 + LLM配置 + 模型选择 + 生成按钮），右侧进度/结果（统计：QA条目数/简答题数/已生成评分数/空评分数 + 日志）
- [x] 前端导航：`Layout.vue` 侧边栏新增"数据集处理"菜单项（归属"数据后处理"分组）

### 整体验证
- [ ] COT过滤：上传JSON → 过滤 → 查看统计 → 下载两个结果文件
- [ ] 数据集切分：上传JSON → 选择策略 → 切分 → 查看统计 → 确认train/test文件生成
- [ ] 评分标准生成：上传测试集 → 选择Prompt和模型 → 生成 → 查看统计 → 确认Assessment字段写入
- [ ] 全流程串联：问题生成 → 知识体系 → 问题校验 → 答案生成 → 答案校验 → 数据评估 → COT过滤 → 切分 → 评分