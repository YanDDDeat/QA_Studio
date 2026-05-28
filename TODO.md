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
- [x] 分支 `feature/score-rename-qc-generic`：详见 `docs/requirements/19_需求_数据评分改名_质检页面_通用生成页面.md`
  - [x] Layout.vue 侧边栏「数据评估」改为「数据评分」（仅 2 行文案）
  - [x] 新增质检页面：StageEnum.QUALITY_CHECK + 后端 routers/quality_check.py（克隆 answer_validate.py，双文件 PASS/FAIL 模式）+ 前端 QualityCheck.vue + `_FAIL_SUFFIXES` 加 `质检失败` + 默认 Prompt（**无 DB 加列**）
  - [x] 新增通用生成页面：StageEnum.GENERIC + 后端 routers/generic_generate.py（不强制 stage 校验）+ 前端 GenericGenerate.vue（Prompt 跨阶段可选）
  - [x] 迁移脚本 `scripts/migrate_quality_check_and_generic.py`（仅扩展 4 个 enum 列 + 插入默认 Prompt，无 ALTER TABLE 加列）

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