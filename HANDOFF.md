# 项目交接说明

## 1. 项目概览

本项目是“豫章书院数智平台”，由早期 GeoRag 项目演进而来。当前主要功能包括：

- 书院知识库管理、PDF 上传与异步解析入库
- BM25 检索增强问答与引用溯源
- 书院图片展示与 MiMo 多模态问答
- 用户、会话、活动、训练和题库管理
- 朱熹、陆九渊、王阳明等历史人物角色对话
- MiMo ASR/TTS 语音对话与浏览器端 3D 数字人

技术栈：

- 前端：Vue 3、TypeScript、Vite、Pinia、Three.js
- 后端：FastAPI、SQLAlchemy、Alembic、Celery
- 基础服务：MySQL 8、Redis；向量检索启用时可使用 Qdrant
- 模型/API：默认使用小米 MiMo；也保留 Minimax 和本地 Ollama 接口

## 2. 代码入口

- `frontend/src/views/`：主要页面
- `frontend/src/components/agent/DigitalHuman3D.vue`：3D 数字人加载、动作与口型
- `backend/app/main.py`：FastAPI 应用入口
- `backend/app/api/v1/`：接口路由
- `backend/app/services/`：问答、历史人物、模型调用和文档解析
- `backend/app/workers/`：Celery 异步任务
- `backend/alembic/versions/`：数据库结构迁移
- `docker/docker-compose.yml`：本地 MySQL、Redis、Qdrant
- `deploy/tencent/`：腾讯云 Docker 部署文件及说明

## 3. 本地启动

### 基础服务

```powershell
cd docker
docker compose up -d
```

### 后端

使用 Python 3.10+。建议创建独立虚拟环境：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

编辑 `backend/.env`，至少设置：

- `MIMO_API_KEY`
- `JWT_SECRET`
- 与 Docker 配置一致的数据库连接参数

然后执行：

```powershell
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

另开一个终端启动异步任务：

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
celery -A app.workers.celery_app worker --loglevel=info --pool=solo
```

### 前端

```powershell
cd frontend
npm install
npm run dev
```

访问：

- 前端：http://127.0.0.1:5173
- 后端接口文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/health

## 4. 不在 Git 中的数据

以下内容刻意不上传到 Git，接手人如需现有业务数据，应通过网盘、移动硬盘或服务器备份单独交接：

- `backend/.env`：包含真实 API Key、数据库密码和 JWT 密钥
- `georag_local.sql`：本地数据库导出
- `pdf/`：原始 PDF 资料
- `书院文化图片/`：书院图片素材
- `mineru_out/`、`output/`、`backend/uploads/`：解析和上传产物
- `models/`：MinerU/Hugging Face 等本地模型缓存
- `源码.zip`、Word 文档和其他本地归档

不要把真实密钥发到聊天群或提交到仓库。接手人应自行创建 `backend/.env`；如交接已有 Key，建议先在供应商控制台轮换后再通过安全渠道传递。

数据库结构可通过 Alembic 创建，但已有账号、知识库、文档分块、题库和活动数据只存在于数据库备份中。若需要完整接手线上/本地现状，必须同时交接数据库和对应上传文件、图片目录。

## 5. 当前开发状态

当前稳定开发基线为 `main`。历史人物语音对话和 3D 数字人功能已经合并到 `main` 并推送到远程仓库，无需再切换原功能分支。

3D 模型约定：

- 默认模型：`frontend/public/models/avatar.glb`
- 人物专属模型：`frontend/public/models/<人物 id>.glb`
- 已准备：`zhuxi.glb`、`wangyangming.glb`
- 其余人物缺少专属模型时自动回退到默认模型
- 动画文件位于 `frontend/public/models/anim/`

交接前已执行 `npm run build`，前端生产构建成功。构建存在单个大于 500 kB 的代码块提示，不影响运行，后续可按页面继续拆包优化。

## 6. 建议接手顺序

1. 克隆仓库，直接使用默认的 `main` 分支。
2. 按 `.env.example` 新建本地配置，启动 MySQL、Redis、后端、Celery 和前端。
3. 执行 Alembic 迁移，确认 `/health` 和 Swagger 可访问。
4. 单独导入数据库备份和素材目录，确认知识库、图片和 PDF 预览路径正常。
5. 验证普通问答、历史人物文字对话、ASR/TTS 和 3D 模型加载。
6. 后续开发从最新 `main` 创建新的功能分支，完成验证后再合并回 `main`。

## 7. 云端部署

腾讯云的部署流程见 `deploy/tencent/README.md`。云端方案默认使用 MySQL + Redis + BM25，不运行 MinerU 和 Qdrant；较重的 PDF 解析建议在本地完成，再迁移数据库、上传文件和解析结果。
