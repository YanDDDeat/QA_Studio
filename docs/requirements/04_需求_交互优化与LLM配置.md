# 需求补充 — 交互优化与 LLM 配置中心

本轮优化围绕四个用户痛点：提示词不可见 / 阶段页看不到结果 / 必须跳页才能上传源文件 / LLM endpoint 写死在源码不可动态配置。

---

## 1. 提示词预览 + 内联编辑面板

### 现状问题
每个阶段页只有「提示词下拉」+「版本下拉」，选完看不到任何内容，调试时必须跳到配置中心反复切页面。

### 解决方案
阶段页右侧加一个抽屉式面板，**立刻展示**当前选中提示词的内容并允许就地编辑保存为新版本。

### 详细行为
- 抽屉默认在阶段页右侧展开（用户也可手动收起 / 重新展开）
- 当用户在下拉中切换提示词或版本时，抽屉内容**自动同步**为最新选中的内容（无需任何额外点击）
- 展示内容：
  - 版本号、创建时间
  - `content` 文本（等宽字体 + 多行滚动）
- 编辑保存：
  - 文本框默认可编辑
  - 底部按钮"保存为新版本"
  - 调用现有 `POST /api/prompts` 创建一条 `version + 1` 的记录
  - 保存成功后页面自动切换到新版本，下拉刷新
- 不允许直接覆盖旧版本（保留历史，与现有版本管理逻辑一致）

### 影响范围
所有 6 个阶段页：QuestionGenerate / KnowledgeGenerate / QuestionValidate / AnswerGenerate / AnswerValidate / DataEvaluate。

---

## 2. 阶段页结果区（懒加载）

### 现状问题
阶段执行完只能跳到数据中心，且数据中心所有阶段记录混在一起，看不出某次任务到底产出了什么。

### 解决方案
每个阶段页底部加一块可折叠"生成结果"区，按需手动加载当前选中文件 + 当前阶段的记录。

### 详细行为
- 默认折叠，标题栏显示当前选中文件名
- 顶部按钮"加载最新结果"，**懒加载**（用户主动点击才请求，不自动刷新）
- 点击后调用：`GET /api/datasets?file_id={file_id}&stage={stage}&page=1&page_size=10`
- 表格分页：10 条/页，与数据中心一致
- 列只显示当前阶段相关字段，避免空列干扰：

| 阶段 | 展示列 |
|---|---|
| 问题生成 | input / category / difficulty / domain |
| 知识体系生成 | input / knowledge / scene |
| 问题校验 | input / passed |
| 答案生成 | input / output(截断) / cot(截断) |
| 答案校验 | input / output(截断) / passed |
| 数据评估 | input / score / relevance / clarity / reasoning / terminology |

- 单击行 → 弹出详情（复用数据中心 detail 组件，含 LaTeX 渲染）
- 长文本字段超过限制截断显示 "..."

### 后端改动
- `GET /api/datasets` 接口新增可选参数 `stage`（按当前阶段过滤记录）
- 已有 `file_id` 过滤参数则继续使用

---

## 3. 阶段页内直接上传源文件

### 现状问题
源文件只能在文件管理页统一上传，每个阶段页只能从下拉选已有文件，操作链路长。

### 解决方案
**所有阶段**的文件下拉旁加"上传新文件"按钮。

### 详细行为
- 按钮触发弹窗，包含：
  - 文件选择（仅 .json）
  - text_field 输入框（默认 "text"）
  - 提交按钮
- 提交走现有 `POST /api/files/upload` 接口
- 上传成功后：
  - 自动刷新阶段页文件下拉
  - 自动选中刚上传的文件
  - 关闭弹窗
- 适用范围：所有 6 个阶段（与"文件选择不限阶段"原则一致，用户可上传中间 JSON 直接进入任意阶段）

---

## 4. LLM 配置中心（核心变更）

### 现状问题
- `backend/app/config.py:7-20` 定义 `LLM_PROVIDERS` 字典，**API key 硬编码在源代码中**
- 所有用户共享同一组 endpoint/key
- 用户无法添加自己的 LLM endpoint，更不能切换
- `Prompt.model` 只是一个字符串名，不绑定任何 endpoint 信息，无法溯源到底用了哪个 base_url/key

### 解决方案
新增「LLM 配置」模块，用户可注册多个 OpenAI 兼容 endpoint，提示词关联到具体配置。

### 数据库变更

#### 新增表 `llm_configs`

| 字段 | 类型 | 说明 |
|---|---|---|
| id | int PK | 主键 |
| user_id | int FK → users.id, NULL | NULL 表示全局共享配置（仅 admin 可编辑） |
| name | varchar(128) | 显示名，例如"我的阿里 Qwen" |
| base_url | varchar(512) | endpoint URL |
| api_key | varchar(512) | **明文存储**（开发环境，生产环境后续可加密） |
| models | JSON | 该 endpoint 支持的模型名列表，例如 `["qwen3-max","qwen3-turbo"]` |
| default_model | varchar(128) | 默认使用的模型名 |
| created_at | datetime | |
| updated_at | datetime | |

#### 修改表 `prompts`
- 新增字段 `llm_config_id`（int, FK → llm_configs.id, NULL）
- 保留 `model` 字符串字段以兼容历史数据
- 历史数据迁移策略详见下文「迁移说明」

### 权限模型
管理员身份判定：**`username == 'admin'`**（不修改 User 表结构）

| 操作 | 普通用户 | admin |
|---|---|---|
| 查看自己的配置 | ✅ | ✅ |
| 查看全局配置（user_id=NULL） | ✅ | ✅ |
| 创建/编辑/删除自己的配置 | ✅ | ✅ |
| 创建/编辑/删除全局配置 | ❌ | ✅ |
| 在阶段页选择全局配置使用 | ✅ | ✅ |

### 后端改动

#### 新增路由 `routers/llm_config.py`
- `GET /api/llm-configs` — 列出当前用户能看到的配置（自己的 + 全局的）
- `POST /api/llm-configs` — 创建配置
  - 普通用户：自动设 user_id = 当前用户
  - admin 用户：可传 `is_global=true` 创建全局配置（user_id=NULL）
- `PUT /api/llm-configs/{id}` — 修改配置（权限检查）
- `DELETE /api/llm-configs/{id}` — 删除配置（权限检查）
- `POST /api/llm-configs/{id}/test` — 测试连接
  - 行为：用该配置发起一次完整的简短对话请求，例如 `messages=[{"role":"user","content":"你好"}]`，走完整 chat/completions 流程，验证 endpoint + key + model 三件套全部可用
  - 返回：`{ ok: true/false, latency_ms, reply: "<LLM 回复内容>", error }`
  - 前端 toast 显示：成功时展示延迟和回复前若干字符；失败时展示 error

#### 改造 `services/llm_service.py`
- `call_llm()` / `call_llm_json()` 新增参数 `llm_config_id`
- 路由层先查 `llm_configs` 表，注入 `base_url` / `api_key` / `model`
- 兼容老调用方式（直接传 base_url/api_key/model）保留不变

#### 改造各阶段路由
执行任务时优先通过 `Prompt.llm_config_id` 拿到配置，再传入 `call_llm()`。

#### 启动 seed
首次启动时把 `config.py` 中现有的 `dashscope` 和 `swust` 两个 preset 写入 `llm_configs` 表（user_id=NULL，admin 可编辑）。后续可逐步移除 `config.py` 中的硬编码字典。

### 前端改动

#### 配置中心新增 "LLM 配置" tab
- 列表展示：name / base_url / 模型数 / 默认模型 / 归属（"我的" / "全局"）/ 操作
- 操作列：编辑 / 删除 / 测试连接
- "新建配置"按钮 → 表单弹窗：
  - 配置名 / base_url / api_key / 模型列表（可逐个添加）/ 默认模型
  - admin 用户多一个"设为全局共享"开关
- 测试连接按钮 → 调用 `/test` 端点，弹 toast 显示结果和延迟

#### 阶段页"模型"下拉重构为两级
- 第一级：选 LLM 配置（显示 name）
- 第二级：选该配置下的 model（从 `models` 列表读取）
- 与提示词联动：保存提示词时同时存 `llm_config_id` 和 `model` 字符串

### 内置 LLM 模板（开箱即用）

系统当前 `config.py` 中已经定义两个 LLM provider preset：`dashscope`（阿里 Qwen）和 `swust`（学校内网）。这两个应当作为**内置模板**提供给用户，降低使用门槛。

#### 行为设计
- 数据库 seed 阶段，将这两个 preset 写入 `llm_configs` 表，标记 `user_id=NULL` 作为全局共享配置
- 在配置中心 "LLM 配置" tab 顶部增加一块"内置模板"区域，展示这两个模板：
  - 模板卡片显示：name / base_url / 默认模型 / 支持模型列表
  - 卡片右下角按钮"使用此模板" → 弹窗只需填写 API KEY（其他字段全部预填且只读）
  - 提交后在该用户名下创建一条新的 `llm_configs` 记录（user_id = 当前用户），其他字段从模板拷贝，api_key 用用户填写的值
- 用户也可以选择直接使用全局模板（如果 admin 已经为全局模板填好了 key）— 这种情况无需任何操作

#### admin 行为
- admin 用户可直接编辑全局模板的 api_key，使全局模板变得"开箱可用"
- admin 也可以新增其他全局共享的配置

#### 与"新建空白配置"的区别
- "使用模板"：base_url / models / default_model 已预填，仅需填 api_key 和 name
- "新建空白配置"：从零开始填全部字段，适合接入第三方 OpenAI 兼容 endpoint（如 OpenAI、DeepSeek、Moonshot 等）


1. 数据库迁移脚本（手动运行 `scripts/migrate_llm_config.py`）：
   - 建 `llm_configs` 表
   - `prompts` 表加 `llm_config_id` 字段
   - seed dashscope / swust 两条全局配置
2. 历史 Prompt 数据迁移：
   - 遍历所有 `prompts` 记录，按 `model` 字符串去匹配 dashscope / swust 哪个配置的 models 列表包含它
   - 命中则关联，不命中则关联到 dashscope（默认）
3. `config.py` 中的 `LLM_PROVIDERS` 字典本轮**不删除**，作为 seed 数据源保留，下个版本再清理

---

## 实施顺序建议

1. **LLM 配置中心**（4）— 影响数据模型，先做完才能改提示词面板
2. **提示词预览 + 内联编辑**（1）— 依赖 LLM 配置已就位
3. **阶段页上传文件**（3）— 独立改动，可并行
4. **阶段页结果区**（2）— 独立改动，可并行

---

## 待审核项（请确认）

- [x] 提示词内联编辑只允许"保存为新版本"，不允许覆盖旧版本
- [x] 结果区表格列设计（见 §2）
- [x] LLM 配置 API key 明文存储（仅开发环境）
- [x] 历史 Prompt 数据迁移策略：按 `model` 字符串匹配，匹配不到默认关联 dashscope
- [x] 测试连接改为发起一次真实简答对话请求（替代原 ping 方案）
- [x] 数据库迁移由独立脚本 `scripts/migrate_llm_config.py` 执行（需要你手动跑）
- [x] `config.py` 中的 `LLM_PROVIDERS` 字典本版本保留，下版本清理
- [x] 系统提供 dashscope / swust 两个内置 LLM 模板，用户只需填 API KEY 即可使用