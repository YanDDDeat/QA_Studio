# QA Studio

<div align="center">

**以质量为中心的 AI 数据生成平台**

智能化 QA 数据合成、标注与评估 — 一站式流水线

<!-- 截图占位，部署后可替换 -->
<!-- <img src="https://github.com/user-attachments/assets/placeholder.png" width="80%" /> -->

[![](https://img.shields.io/github/stars/YanDDDeat/QA_Studio?style=social)](https://github.com/YanDDDeat/QA_Studio)
[![](https://img.shields.io/github/issues-raw/YanDDDeat/QA_Studio)](https://github.com/YanDDDeat/QA_Studio/issues)
[![](https://img.shields.io/github/issues-closed-raw/YanDDDeat/QA_Studio)](https://github.com/YanDDDeat/QA_Studio/issues?q=is%3Aissue+is%3Aclosed)
[![](https://img.shields.io/github/license/YanDDDeat/QA_Studio)](https://github.com/YanDDDeat/QA_Studio/blob/master/LICENSE)

[![Vue](https://img.shields.io/badge/Vue-3.x-4FC08D?logo=vue.js)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?logo=mysql)](https://www.mysql.com/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker)](https://www.docker.com/)

[English](./README-en.md) | 简体中文

*可视化流水线编排，灵活的数据处理链路，覆盖多领域多场景。💪*

*将原始语料转化为高质量 LLM 训练数据集。🔧*

*🎉 好数据，好模型 — 给个 ⭐ Star 获取最新更新。*

</div>

---

## 📰 News

- **[2026-06-15] 🏠 官网首页上线！** 
  全新 Landing Page，粒子背景 + 渐入动画，访问 [QA Studio](http://20.243.9.88:8088/) 体验。

- **[2026-06-02] 🧠 专业 CoT 构建流水线发布！** 
  支持单/多 CoT 标注、H-CoT 提示词模板管理，流水线运行数据持久化存储。

- **[2026-05-25] 🎯 CoT 质检模块上线！** 
  链式思维质量评估，自动过滤低质量推理链。

- **[2026-05-10] ⚙️ 配置中心上线！** 
  集中管理所有 Pipeline 参数、提示词模板、模型配置，告别硬编码。

---

## 🔍 什么是 QA Studio？

QA Studio 是一个面向 **LLM 数据准备**的全栈平台，提供从原始文本到高质量训练数据集的端到端流水线。通过 **六阶段 Pipeline** 设计，将数据生成、校验、评估、过滤等环节组装为可复现、可追溯的标准化流程。

核心理念：**以数据质量驱动模型性能**。无论你是做 SFT 微调、RLHF 对齐还是 RAG 检索增强，QA Studio 都能帮你高效产出高质量 QA 数据集。

```
原始语料 → [预处理] → [生成] → [校验] → [评估] → [过滤] → [导出]
                ↓          ↓         ↓         ↓         ↓
              文本清洗    QA生成   多级校验   质量打分   CoT过滤   训练格式
```

---

## ✅ 核心特性

### 🧠 智能数据生成
- **多策略生成**：问题生成、知识体系生成、答案生成，覆盖 QA 对全链路
- **通用生成**：支持自定义 Prompt + 字段映射，适应任意数据格式
- **CoT 标注**：单 CoT / 多 CoT (H-CoT) 标注，支持专业提示词模板

### 🔍 多级质量校验
- **问题校验**：检查生成问题的合理性、一致性
- **答案校验**：验证答案与问题的匹配度和正确性
- **CoT 质检**：评估推理链的连贯性、逻辑性，自动过滤低质量 CoT

### ⚙️ 可视化流水线引擎
- **六阶段 Pipeline**：预处理 → 生成 → 校验 → 评估 → 过滤 → 导出
- **实时进度追踪**：每个阶段的状态、耗时、中间结果可视化
- **一键重跑/续跑**：支持从任意阶段恢复执行，断点续传

### 📊 数据评估体系
- **多维指标**：多样性、一致性、覆盖度自动评估
- **质量报告**：生成可读性强的评估报告，辅助决策
- **数据集切分**：训练/验证/测试集智能划分

### 📦 灵活导出
- **多格式支持**：JSON、JSONL、Parquet 等
- **字段映射**：LLM 返回字段自动映射到目标 Schema
- **一键下载**：流水线完成后直接导出训练数据集

### 🛠 工程化能力
- **文件管理**：支持 PDF/Word/Markdown/JSON 等多种上传格式
- **配置中心**：集中管理 Prompt、模型参数、流水线配置
- **用户权限**：多用户管理，登录鉴权

---

## 🚀 快速开始

### 环境要求

| 组件 | 版本要求 |
|------|---------|
| Docker | ≥ 20.10 |
| Docker Compose | ≥ v2.0 |
| Python | ≥ 3.9（仅开发环境） |
| Node.js | ≥ 18（仅开发环境） |

### 一键部署

```bash
# 1. 克隆仓库
git clone https://github.com/YanDDDeat/QA_Studio.git
cd QA_Studio

# 2. 配置环境变量
cp dev-ops/.env.example dev-ops/.env
# 编辑 .env，填入：
#   - MYSQL_ROOT_PASSWORD（数据库密码）
#   - DASHSCOPE_API_KEY（LLM API Key）
#   - JWT_SECRET_KEY（随机字符串）

# 3. 启动服务
cd dev-ops
docker compose up -d --build
```

访问 **http://localhost:8088** 即可使用。

### 默认账号

| 字段 | 值 |
|------|-----|
| 用户名 | `admin` |
| 密码 | `admin123` |

---

## 🏗 技术架构

```
┌─────────────────────────────────────────────┐
│                  Nginx                       │
│              (反向代理 + 静态文件)              │
│                  :8088→:80                   │
├──────────────┬──────────────────────────────┤
│   Frontend   │         Backend               │
│   Vue 3 +    │    FastAPI + SQLAlchemy       │
│ Element Plus │    ┌──────────────────┐       │
│   Vite 构建   │    │  六阶段 Pipeline  │       │
│              │    │  预处理→生成→校验   │       │
│              │    │  评估→过滤→导出    │       │
│              │    └──────────────────┘       │
├──────────────┴──────────────┬───────────────┤
│        MySQL 8.0            │   LLM APIs    │
│     (数据集 + 配置 + 用户)    │ (DashScope等) │
└─────────────────────────────┴───────────────┘
```

### 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 🎨 前端 | Vue 3 + Element Plus + Vite | SPA 架构，组件化开发 |
| ⚡ 后端 | FastAPI + SQLAlchemy | 异步 API，ORM 数据层 |
| 🗄 数据库 | MySQL 8.0 | 数据集、流水线、用户管理 |
| 🐳 部署 | Docker + Docker Compose | 四容器架构，一键部署 |
| 🔒 认证 | JWT Token | 无状态鉴权 |

---

## 📂 项目结构

```
qa_gen/
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── routers/            # API 路由（auth, data, pipeline...）
│   │   ├── services/           # 业务逻辑（生成/校验/评估引擎）
│   │   ├── models/             # SQLAlchemy 数据模型
│   │   ├── utils/              # 工具函数（字段映射、文件处理）
│   │   └── main.py             # 应用入口
│   └── requirements.txt
├── frontend/                   # Vue 3 前端
│   └── src/
│       ├── views/              # 页面组件（登录、流水线、配置中心...）
│       ├── components/         # 通用组件（文件选择、提示词预览...）
│       ├── router/             # Vue Router 路由配置
│       ├── api/                # Axios API 封装
│       └── utils/              # 工具函数
├── dev-ops/                    # 部署配置
│   ├── docker-compose.yml      # 四容器编排
│   ├── Dockerfile.backend      # 后端镜像
│   ├── Dockerfile.frontend     # 前端构建镜像
│   ├── .env.example            # 环境变量模板
│   └── nginx/default.conf      # Nginx 配置
├── docs/                       # 文档 & 提示词模板
├── scripts/                    # 数据库迁移脚本
└── README.md
```

---

## 💡 为什么选择 QA Studio？

与通用数据处理框架相比，QA Studio 的差异化优势：

| 维度 | QA Studio | 通用框架 |
|------|-----------|---------|
| 🎯 专注领域 | **QA 数据生成**，开箱即用 | 需自行开发 Pipeline |
| 🔗 全链路覆盖 | 生成→校验→评估→过滤→导出 | 通常只覆盖部分环节 |
| 🧠 CoT 支持 | 内置单/多 CoT 标注+质检 | 需自行集成 |
| ⚙️ 配置中心 | 统一管理 Prompt/模型/参数 | 分散在代码中 |
| 🖥️ 可视化 | Web UI 全流程操作 | 通常 CLI 驱动 |
| 🐳 部署 | Docker 四容器一键部署 | 环境配置复杂 |

---

## 🛠 开发指南

```bash
# === 前端开发 ===
cd frontend
npm install
npm run dev            # 启动 Vite 开发服务器

# === 后端开发 ===
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# === 数据库迁移 ===
cd scripts
python migrate_<描述>.py
```

**注意事项**：
- 数据库变更需先通知，确认后再执行迁移
- 新接口遵循 `/api/<resource>` 命名规范
- Git 提交信息使用中文

---

## 📄 License

MIT © YanDDDeat

---

<div align="center">
  <sub>好数据，好模型 🚀</sub>
</div>
