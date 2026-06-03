# QA_Studio TODO
完成一个勾选一个，勾选后检查指导当前任务完成。
## LLM调用流程改进（新需求，分两批）
- [x] 分支1 `feature/llm-task-improvements`：详见 `docs/requirements/需求_LLM任务改进.md`
  - [x] 修复 Prompt not found（全局共享 prompt 在 `/start` 校验时被漏掉）
  - [x] 默认输出文件名 `{源文件}_{阶段中文}_{username}_{时间}.json`，后端已就绪，前端 stageLabels.js 已提供工具函数
  - [x] 任务停止/恢复（软停：处理完当前条退出，进度保留可续跑）
- [x] 分支2 `feature/no-overwrite-and-stage-tag`：详见 `docs/requirements/需求_输出新文件与阶段标签过滤.md`
  - [x] 8 个阶段不再覆盖输入文件，每次生成新文件（带 source_stage 标签）
  - [x] 切分阶段 train/test 各为独立 File 记录；校验阶段 fail file 旧逻辑保留
  - [x] FileSelector 加 expectedStage 过滤 + 「显示全部」开关，默认仅显示上一阶段

## 小需求
- [x] 分支3 `feature/file-merge-download`：详见 `docs/requirements/08_需求_JSON文件合并导出.md`
  - [x] 文件管理页多选JSON文件合并下载

- [x] 分支4 `feature/llm-fields-extension`：详见 `docs/requirements/09_需求_LLM返回字段扩展存储.md`
  - [x] Dataset 新增 step_count (String) + extra_fields (JSON) 列
  - [x] 各阶段 LLM 处理取 step_count + 剩余字段存 extra_fields
  - [x] 前端 categorizeFields 展开 extra_fields 为独立字段显示

- [x] 分支5 `feature/export-field-select`：详见 `docs/requirements/10_需求_导出字段选择.md`
  - [x] 下载/合并下载前弹出字段选择 Dialog
  - [x] 默认勾选22个字段（忽略大小写匹配）
  - [x] extra 子字段解析与分组显示
  - [x] 后端下载接口支持 fields 参数过滤

## 新需求
- [x] 分支 `BIT/wj`：标注流水线2专业 CoT 构建，详见 `docs/requirements/26_需求_标注流水线2专业CoT构建.md`
  - [x] 在 COT/H-COT 标注分组下新增「标注流水线2」页面入口
  - [x] 实现系统已有单 chunk JSON 文件选择、字段下拉/默认 text 和一键 Pipeline，CoT 类型由 Step 3 模型自动判定
  - [x] 按固定 6 个逻辑步骤生成 Step 3 推荐的单个 CoT 类型样本，运行中步骤列表不得为空，阶段产物直接写 JSON 文件
  - [x] 流水线任务列表支持分页展示
  - [x] 最终产物区放在流水线步骤下方，生成并支持下载 `final_samples.json` / `final_samples.jsonl`

- [x] 分支 `BIT/wj`：标注流水线2支持批量文献 JSON 输入，详见 `docs/requirements/28_需求_标注流水线2支持批量文献JSON输入.md`
  - [x] 取消 JSON 数组长度必须为 1 的限制，允许数组长度 `>= 1`
  - [x] 一个任务内按数组顺序串行处理多篇文献，不创建多个独立任务
  - [x] 单篇失败时记录失败明细并继续处理后续文献
  - [x] 最终输出汇总 `input_count` / `success_count` / `failed_count` 和每篇文献状态
  - [x] `final_samples.json` / `final_samples.jsonl` 保留下载能力，并能追溯 `source_index` / `source`

- [x] 分支 `BIT/wj`：CoT/H-CoT 标注分组新增文本预处理入口，详见 `docs/requirements/27_需求_CoTHCoT标注文本预处理入口.md`
  - [x] 在 CoT/H-CoT 标注分组下新增「文本预处理」菜单项
  - [x] 复用现有文本预处理页面能力，原入口不受影响
  - [x] 支持一次上传多个 MD 文件并合并为 `[{source: 文件名, text: MD全文}]` JSON 数组
  - [x] 支持下载合并后的 JSON，或保存为系统文件供标注流水线2选择

- [x] 分支 `BIT/wj`：标注流水线2提示词模板管理，详见 `docs/requirements/29_需求_标注流水线2提示词模板管理.md`
  - [x] 在 COT/H-COT 下新增「标注流水线2提示词」管理入口
  - [x] 系统默认模板共享只读，用户复制后形成个人独立模板版本
  - [x] 模板包按通用步骤和 10 类 CoT 专属步骤树形展示并支持单项编辑
  - [x] 新建标注流水线2任务时选择一个完整提示词模板包版本
  - [x] 任务启动时保存完整提示词快照，历史 run 可追溯

- [ ] 分支 `feature/step1-3-integrated-cot`：单COT生成 Step1-3 融合节点修复，详见 `docs/requirements/31_需求_单COT生成Step1-3融合节点修复.md`
  - [ ] 使用融合提示词一次完成文献可用性、关键信息抽取和 CoT 类型路由
  - [ ] 单COT生成 manifest 展示节点从 6 个逻辑步骤调整为 4 个节点
  - [ ] Step 4/5 改为接收 `step1_3_result`，并兼容提示词快照与旧模板补默认文件

- [ ] 分支 `feature/document-stage-matrix`：单COT生成文献级阶段进度视图，详见 `docs/requirements/32_需求_单COT生成文献级阶段进度视图.md`
  - [ ] 详情接口返回 `document_stage_matrix`，按文献展示 Step1-3 / Step4 / Step5 / Step6 状态与中间产物路径
  - [ ] 单COT生成详情页新增文献级阶段进度矩阵，支持有产物的阶段点击预览

- [x] 分支 `feature/llm-field-auto-mapping`：详见 `docs/requirements/12_需求_LLM返回字段自动映射到数据库列.md`
  - [x] 新建 `field_mapper.py`：动态映射 LLM 字段到数据库列
  - [x] 改造 6 个管线阶段：替换硬编码白名单为自动映射
  - [x] 支持忽略大小写匹配（如 `Relevance` → `relevance`）
  - [x] 新增字段只需 `ALTER TABLE` + 改 Prompt，代码无需改动

## 数据持久化改进
- [ ] 分支 `feature/data-flush-and-sync`
  - [x] 任务暂停/停止时自动刷盘：各 `_run_*_task()` 检测到 PAUSED 状态退出前调用 `write_datasets_to_file()` 写入已有数据，避免中途暂停后 JSON 文件为空
  - [x] 数据中心文件列表新增"同步到文件"按钮：`POST /file-manage/sync/{file_id}`，从 DB 全量重写磁盘 JSON，覆盖写入让文件与 DB 一致
  - [ ] 详见 `docs/requirements/11_需求_数据持久化与手动同步.md`

## LLM 并发调用优化
- [ ] 分支 `feature/llm-concurrent`：详见 `docs/requirements/13_需求_LLM并发调用优化.md`
  - [x] `llm_service.py` 抽出公共逻辑，新增 `call_llm_sync` / `call_llm_json_sync`
  - [x] 新建 `thread_pool.py`：全局线程池 + 活跃任务计数器 + 动态批大小
  - [x] 6 个 Pipeline 阶段改造为分批并发（run_in_executor + gather）
  - [x] 适配进度追踪（每批更新）、暂停检查（每批检查）、失败处理（连续整批失败）
  - [x] 管理员前端配置线程池大小
  - [x] 配置项：`LLM_THREAD_POOL_SIZE`（默认20）

## 管理员查看运行中任务
- [x] 分支 `feature/admin-running-tasks`：详见 `docs/requirements/14_需求_管理员查看运行中任务.md`
  - [x] 后端 `GET /api/tasks/running`：查询所有 RUNNING 任务（关联用户名）
  - [x] 前端配置中心系统设置标签页新增运行中任务面板（表格 + 自动刷新）

## 线程池公平调度修复
- [x] 分支 `feature/fair-thread-pool`：详见 `docs/requirements/15_需求_线程池公平调度修复.md`
  - [x] 用 `AdjustableLimiter`（in_flight 计数 + 等待队列）替换 `SlidingWindowExecutor` 内部的 `asyncio.Semaphore`，消除窗口缩放时的突击提交与 permit 泄漏
  - [x] 新增并发模拟测试 `tests/test_thread_pool_fairness.py`，断言两用户场景下完成数比例在 [0.8, 1.25] 之间

## CoT/H-CoT 流水线架构修正
- [ ] 分支 `BIT/wj`：详见 `docs/requirements/23_需求_CoTHCoT流水线架构修正.md`
  - [x] 流水线执行逻辑从 per-chunk 全流程改为 document 级聚合
  - [x] 新增 merge_fact_cards 步骤（纯数据合成，合并所有 chunk 事实卡）
  - [x] 新增 Task.l0_question_index 字段（per-L0 步骤标识）
  - [x] 一键执行改为：per-chunk 事实卡 → 合并 → 数值抽象 → L0 总问题数组 → per-L0 推理树
  - [x] 导出支持多棵 H-CoT 树
  - [x] 前端 WorkflowDetail 展示步骤粒度（per-chunk/document/per-L0）

## 各阶段页面恢复/重试支持重选配置
- [x] 分支 `feature/stage-resume-config`：详见 `docs/requirements/16_需求_各阶段页面恢复重试支持重选配置.md`
  - [x] 抽出公共组件 `TaskConfigDialog.vue`（厂商/模型/提示词三联选）
  - [x] 8 个阶段页面（QG/KG/QV/AG/AV/DE/CF/DP）的恢复/重试按钮接入弹窗
  - [x] MyTasks.vue 改用公共组件，避免双份维护

## JSON 文件合并工具（独立页面）
- [x] 分支 `feature/json-merge-tool`：详见 `docs/requirements/17_需求_JSON文件合并工具.md`
  - [x] 新建 `JsonMergeTool.vue`：上传多个 JSON 数组文件 → 校验必填字段（source_id/source/source_type）→ 取字段交集合并 → 浏览器下载
  - [x] 注册路由 `/json-merge-tool`，Layout 新增「工具」菜单分组
  - [x] 严格模式校验：任一文件/记录不合格则整次任务失败，提示具体位置

## 任务列表展示输入/输出文件名
- [x] 分支 `feature/task-output-filename`：详见 `docs/requirements/18_需求_任务列表展示输入输出文件.md`
  - [x] 后端 3 个接口（list_tasks / my-running / running）响应加 source_filename + output_filename，批量查 file 表
  - [x] MyTasks.vue 两个表格拆「输入文件」+「输出文件」两列
  - [x] ConfigCenter.vue 运行中任务面板加同样两列

## 数据评分改名 + 质检页面 + 通用生成页面
- [x] 分支 `feature/score-rename-qc-generic`：详见 `docs/requirements/19_需求.md`
  - [x] 子需求1：侧边栏「数据评估」改名为「数据评分」（仅 Layout.vue 文案）
  - [x] 子需求2：新增「质检」页面（克隆 answer_validate 模板，PASS/FAIL 双文件输出，挂独立分组）
  - [x] 子需求3：新增「通用生成」页面（任意文件 + 任意 Prompt + 任意 LLM，挂工具分组）
  - [x] DB 迁移：scripts/migrate_quality_check_and_generic.py 扩展 4 个 ENUM 列加入 quality_check/generic，插入质检默认 Prompt（已执行）

## 问题生成前文本预处理
- [x] 分支 `feature/text-preprocess`：详见 `docs/requirements/20_需求_问题生成前文本预处理.md`
  - [x] 新建 `backend/app/services/preprocess_service.py`：纯函数模块（清洗/分类/合并/token估算/页眉识别）
  - [x] 改造 `backend/app/routers/question_generate.py`：主循环前插入预处理调用 + 写过滤文件 + 更新 progress_total
  - [x] 新建 `tests/test_preprocess_service.py`：单元测试覆盖每个规则
  - [x] 人工集成测试：典型脏数据 JSON → 验证过滤文件、task_logs、暂停恢复

## MD 标题级别选择切分
- [x] 分支 `feature/md-heading-level-select`：详见 `docs/requirements/24_需求_MD标题级别选择切分.md`
  - [x] 上传 MD 后先解析并展示实际存在的标题层级
  - [x] 用户选择指定标题级别后，按该级标题作为 chunk 边界切分
  - [x] 保持 JSON 输出格式和文件管理流程不变

## 已完成功能（简要）
- [x] 基础设施：Vue3 + FastAPI + MySQL + 前端路由框架
- [x] 用户管理：管理员创建账号 + 登录认证 + 数据隔离
- [x] LLM调用模块：统一方法 + OpenAI兼容接口 + 逐条调用
- [x] 配置中心：提示词版本管理 + 模型选择 + LLM配置中心（多endpoint、模板、测试连接）
- [x] 文件上传与管理：上传JSON + text_field指定 + 查看/下载/删除
- [x] Pipeline 6阶段：问题生成→知识体系→问题校验→答案生成→答案校验→数据评估（全部重构为选文件模式）
- [x] 文件选择不限阶段 + 文件删除策略修正 + 侧边栏分组导航
- [x] 提示词预览+内联编辑面板 + 阶段页内上传 + 阶段页结果区
- [x] FileSelector组件 + PromptPreview组件 + 左右两栏布局
- [x] COT过滤 + 数据集切分 + 评分标准生成（3个后处理阶段）
- [x] 任务日志持久化 + 前端状态恢复
- [x] 预执行字段校验（所有9个阶段启动前校验JSON必需字段）
