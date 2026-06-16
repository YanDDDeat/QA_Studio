# QA Studio

以质量为中心的 AI 数据生成平台。智能化 QA 数据合成、标注与评估系统。

> 好数据，好模型。

## 功能特性

| 模块 | 说明 |
|------|------|
| 🧠 智能生成 | 基于 LLM 自动生成高质量 QA 问答对，支持多种策略 |
| 🔍 多级校验 | 问题校验、答案校验、CoT 质检，层层把关 |
| ⚙️ 流水线引擎 | 可视化流水线配置，全流程覆盖 |
| 📊 数据评估 | 自动评估数据多样性、一致性和覆盖度 |
| 🎯 CoT 标注 | 单/多 CoT 标注 + H-CoT 提示词模板管理 |
| 📦 一键导出 | 多格式导出，无缝对接训练 |

## 技术栈

- **前端**：Vue 3 + Element Plus + Vite
- **后端**：FastAPI + SQLAlchemy + MySQL
- **部署**：Docker + Docker Compose + Nginx
- **构建**：Vite (Rolldown)

## 快速开始

### 环境要求

- Docker 20.10+
- Docker Compose v2+

### 部署

```bash
# 克隆仓库
git clone git@github.com:YanDDDeat/QA_Studio.git
cd QA_Studio

# 配置环境变量
cp dev-ops/.env.example dev-ops/.env
# 编辑 .env 填入数据库密码和 API Key

# 启动服务
cd dev-ops
docker compose up -d --build
```

访问 `http://localhost:8088`

### 默认账号

- 用户名：`admin`
- 密码：`admin123`

## 项目结构

```
qa_gen/
├── backend/               # FastAPI 后端
│   ├── app/
│   │   ├── routers/       # API 路由
│   │   ├── services/      # 业务逻辑
│   │   └── models/        # 数据模型
│   └── requirements.txt
├── frontend/              # Vue 3 前端
│   └── src/
│       ├── views/         # 页面组件
│       ├── router/        # 路由配置
│       └── components/    # 通用组件
├── dev-ops/               # 部署配置
│   ├── docker-compose.yml
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   └── nginx/
└── docs/                  # 文档 & 提示词模板
```

## 开发

```bash
# 前端开发
cd frontend
npm install
npm run dev

# 后端开发
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## License

MIT
