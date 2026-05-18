# QA Studio — Claude Code 工作规范

## 项目概览

QA 数据生成评估平台，Vue 3 + FastAPI + MySQL，6 阶段 Pipeline。
详细架构参见项目记忆 `qa_studio_project.md`。

## 新需求工作流程（必须遵循）

每个新需求必须按以下流程执行，不得跳步：

### 1. 写需求文档
- 在 `docs/requirements/` 目录下新建 `序号_需求_<简述>.md`
- 内容包含：背景、输入输出定义、详细规则、UI/接口变更说明
- 写完后将简要条目追加到 `TODO.md`（勾选框格式，用于进度追踪）

### 2. 创建 git 分支
- 分支命名：`feature/<简述>`（如 `feature/answer-validation`）
- **阈值规则**：改动超过 2 个文件或涉及数据库变更 → 必须开分支；小修小补（1-2 文件、无 DB 变化）可直接在 main 上做
- 分支基于当前 main 创建

### 3. 用 sub-agent 实现
- 实际编码必须通过 Agent 工具委托（优先使用 `web-engineer` 类型）
- 主对话只负责：规划、审查、合并决策
- 不要在主上下文中大量写代码

### 4. 完成后合并
- 功能完成后，在分支上 commit，然后 merge 回 main
- 单人项目，直接 merge（无需 PR 审查）
- 合并后删除分支，保持分支列表干净

### 5. 更新 TODO.md
- 合并完成后，将 TODO.md 中对应条目勾选为 `[x]`

## 代码规范

- 后端：FastAPI + SQLAlchemy ORM，路由在 `backend/app/routers/`，服务在 `backend/app/services/`
- 前端：Vue 3 + Element Plus，页面在 `frontend/src/views/`，组件在 `frontend/src/components/`
- **数据库变更必须先通知用户**：任何涉及数据库表/列增删改的需求，必须先向用户说明变更内容（改什么表、加什么列、影响范围），等用户确认后再编写迁移脚本和修改代码。不得擅自执行数据库变更。
- 新接口必须遵循现有路由命名模式（`/api/<resource>`）
- **git 提交备注必须用中文**（如 `修复数据集切分自引用bug`，不要用英文）

## 文件结构约定

- 需求文档：`docs/requirements/需求_<简述>.md`
- 迁移脚本：`scripts/migrate_<描述>.py`
- 测试文件：与源文件同目录或 `tests/` 目录