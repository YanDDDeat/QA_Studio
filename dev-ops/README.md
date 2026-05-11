# QA Studio Docker 部署

## 目录结构

```
dev-ops/
├── docker-compose.yml    # Docker Compose 编排文件
├── Dockerfile.backend    # 后端镜像构建文件
├── Dockerfile.frontend   # 前端镜像构建文件
├── nginx/
│   └── default.conf      # Nginx 配置（API 代理 + SPA 路由）
├── .env.example          # 环境变量模板
└── README.md             # 本文档
```

## 快速部署

### 1. 准备环境变量

```bash
cd dev-ops
cp .env.example .env
# 编辑 .env 填入实际配置
vim .env
```

**必须修改的配置：**
- `MYSQL_ROOT_PASSWORD` - MySQL root 密码
- `MYSQL_PASSWORD` - 应用数据库密码
- `DASHSCOPE_API_KEY` 或 `SWUST_API_KEY` - LLM API 密钥
- `JWT_SECRET` - JWT 密钥（随机字符串）
- `ADMIN_PASSWORD` - 管理员密码

### 2. 数据库初始化（可选）

项目已有 `init-db/create_tables.sql` 初始化脚本。如需使用：

```bash
# 取消 docker-compose.yml 中这行的注释：
# - ./init-db:/docker-entrypoint-initdb.d:ro
```

> **注意**: FastAPI 启动时会自动创建表结构（通过 SQLAlchemy ORM），此 SQL 脚本作为备用。

### 3. 构建并启动

```bash
# 从 dev-ops 目录运行
docker compose up -d --build
```

### 4. 访问应用

- 前端: http://localhost
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/docs

默认管理员账号: `admin` (密码在 .env 中设置)

## 常用命令

```bash
# 查看日志
docker compose logs -f

# 只看后端日志
docker compose logs -f backend

# 重启服务
docker compose restart

# 停止并删除容器
docker compose down

# 停止并删除容器和数据卷（清除数据）
docker compose down -v

# 重新构建某个服务
docker compose build backend
docker compose up -d backend
```

## 构建镜像（用于部署到其他服务器）

```bash
# 构建镜像
docker compose build

# 导出镜像
docker save qa-studio-backend:latest | gzip > qa-studio-backend.tar.gz
docker save qa-studio-frontend:latest | gzip > qa-studio-frontend.tar.gz

# 在目标服务器导入
docker load < qa-studio-backend.tar.gz
docker load < qa-studio-frontend.tar.gz
```

## 生产环境建议

1. **HTTPS**: 在前端前再加一层反向代理（如 Caddy/Nginx）处理 SSL
2. **数据备份**: 定期备份 MySQL 数据卷
3. **日志轮转**: 后端日志已配置按天轮转，保留 90 天
4. **资源限制**: 在 docker-compose.yml 中添加 `deploy.resources` 限制内存/CPU

## 端口说明

| 服务 | 容器端口 | 主机端口 |
|------|---------|---------|
| Frontend (Nginx) | 80 | 80 |
| Backend (FastAPI) | 8000 | 8000 |
| MySQL | 3306 | 3306 |

> 如果主机端口冲突，修改 docker-compose.yml 中的 `ports` 配置