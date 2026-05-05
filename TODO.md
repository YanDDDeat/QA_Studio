# QA_Studio TODO
完成一个勾选一个，勾选后检查指导当前任务完成。
## 整体验证（待完成）
- [ ] COT过滤：上传JSON → 过滤 → 查看统计 → 下载两个结果文件
- [ ] 数据集切分：上传JSON → 选择策略 → 切分 → 查看统计 → 确认train/test文件生成
- [ ] 评分标准生成：上传测试集 → 选择Prompt和模型 → 生成 → 查看统计 → 确认Assessment字段写入
- [ ] 全流程串联：问题生成 → 知识体系 → 问题校验 → 答案生成 → 答案校验 → 数据评估 → COT过滤 → 切分 → 评分

## LLM调用流程改进（新需求，分两批）
- [x] 分支1 `feature/llm-task-improvements`：详见 `docs/requirements/需求_LLM任务改进.md`
  - [x] 修复 Prompt not found（全局共享 prompt 在 `/start` 校验时被漏掉）
  - [x] 默认输出文件名 `{源文件}_{阶段中文}_{username}_{时间}.json`，后端已就绪，前端 stageLabels.js 已提供工具函数
  - [x] 任务停止/恢复（软停：处理完当前条退出，进度保留可续跑）
- [ ] 分支2 `feature/no-overwrite-and-stage-tag`：详见 `docs/requirements/需求_输出新文件与阶段标签过滤.md`
  - [ ] 8 个阶段不再覆盖输入文件，每次生成新文件（带 source_stage 标签）
  - [ ] 切分阶段 train/test 各为独立 File 记录；校验阶段 fail file 旧逻辑保留
  - [ ] FileSelector 加 expectedStage 过滤 + 「显示全部」开关，默认仅显示上一阶段

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