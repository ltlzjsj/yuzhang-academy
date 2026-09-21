# 项目交接说明

## 1. 项目概览

本项目是“豫章书院数智平台”，由早期 GeoRag 项目演进而来。当前主要功能包括：

- 书院知识库管理、PDF 上传与异步解析入库
- BM25 检索增强问答与引用溯源
- 书院图片展示与 MiMo 多模态问答
- 用户、会话、活动、训练和题库管理
- 朱熹、陆九渊、王阳明等历史人物角色对话
- MiMo ASR/TTS 语音对话与 LiveTalking 真人视频数字人

技术栈：

- 前端：Vue 3、TypeScript、Vite、Pinia、Three.js
- 后端：FastAPI、SQLAlchemy、Alembic、Celery
- 基础服务：MySQL 8、Redis；向量检索启用时可使用 Qdrant
- 模型/API：默认使用小米 MiMo；也保留 Minimax 和本地 Ollama 接口

## 2. 代码入口

- `frontend/src/views/`：主要页面
- `frontend/src/components/agent/LiveTalkingAvatar.vue`：LiveTalking 实时数字人（WebRTC）
- `frontend/src/components/agent/TalkingPortrait.vue`：画像开口说话（无 LiveTalking 时的回退）
- `frontend/src/views/Photo.vue`：AI 合影留念（选先贤 / 书院场景 / 姿势 / 服装）
- `backend/app/api/v1/photo.py`：合影接口（`/bg-remove` 本地抠图、`/generate` 调图像模型、`/config` 查配置）
- `backend/app/services/nanoapple_image.py`：图像生成通道（Gemini / GPT Image）
- `backend/app/main.py`：FastAPI 应用入口
- `backend/app/api/v1/`：接口路由
- `backend/app/services/`：问答、历史人物、模型调用和文档解析
- `backend/app/workers/`：Celery 异步任务
- `backend/alembic/versions/`：数据库结构迁移
- `docker/docker-compose.yml`：本地 MySQL、Redis、Qdrant
- `deploy/tencent/`：腾讯云 Docker 部署文件及说明

## 3. 本地启动

Windows 下可以直接用仓库根目录的三个脚本（里面的路径全部相对，克隆到任意目录都能用）：

| 脚本 | 作用 |
|---|---|
| `安装依赖.bat` | 首次运行：建虚拟环境、装后端依赖、由 `.env.example` 生成 `backend/.env`、装前端包、建数据库表 |
| `启动系统.bat` | 依次拉起后端 / Celery / 可选实时数字人 / 前端，并打印健康检查结果 |
| `停止系统.bat` | 停掉由本仓库启动的进程 |

下面是等价的手动步骤。

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

已经放进仓库的（克隆即可用）：

- `data/kb/pdf/`：知识库语料 PDF 11 篇
- `data/seed/georag_seed.sql`：知识库、文档、检索分块、题库；导入脚本 `scripts/import_data.ps1`
- `docs/`：数字人接入说明 + LiveTalking 本地改造补丁

放在 GitHub Release `assets-v1` 里按需下载（体积太大，进仓库会让克隆变慢）：

- `shuyuan-images.zip`：`书院文化图片/`（约 911 MB）
- `livetalking-data.zip`：`LiveTalking/data` 帧数据 + `数字人/` 原始视频（约 742 MB）
- 下载脚本 `scripts/download_assets.ps1`

仍然不入库、需要单独交接的：

- `backend/.env`：包含真实 API Key、数据库密码和 JWT 密钥（仓库里只有 `.env.example`）
- 线上/本地的账号、会话、训练记录等个人数据（导出时已剔除）
- `LiveTalking/`：第三方实时数字人引擎源码（独立仓库，按 `docs/livetalking-patch/` 打补丁）
- `mineru_out/`、`backend/uploads/` 里的解析临时产物
- MinerU / Hugging Face 等本地模型缓存与各种压缩归档

不要把真实密钥发到聊天群或提交到仓库。接手人应自行创建 `backend/.env`；如交接已有 Key，建议先在供应商控制台轮换后再通过安全渠道传递。

数据库结构可通过 Alembic 创建，但已有账号、知识库、文档分块、题库和活动数据只存在于数据库备份中。若需要完整接手线上/本地现状，必须同时交接数据库和对应上传文件、图片目录。

## 5. 当前开发状态

当前稳定开发基线为 `main`。历史人物语音对话与 LiveTalking 实时数字人已经合并到 `main` 并推送到远程仓库，无需再切换原功能分支。

数字人形态（2026-09 调整）：

- **只保留 LiveTalking 真人视频实时口型数字人**：`frontend/src/components/agent/LiveTalkingAvatar.vue`
- 原先基于 Three.js + GLB 的 3D 数字人已整体移除：`DigitalHuman3D.vue`、`frontend/public/models/*.glb`（含 anim）、`frontend/public/draco/`、`ZhuxiUe5Test.vue` 及其路由都不再存在
- 同时移除了长期写死为 `false` 的 Xmov SDK 旧链路（`XmovAvatar.vue`、`XmovAvatarTest.vue` 及 `xmov-test` 路由）
- 未接入 LiveTalking 时，历史人物页回退到 `TalkingPortrait.vue`（画像开口说话），最后兜底为静态画像
- 历史里仍保留过 GLB 的 LFS 对象（约 330 MB，占 GitHub LFS 配额）；如需彻底清空配额要重写历史 + 强推

AI 合影留念（`/photo`，公开路由）：

- 前端 `frontend/src/views/Photo.vue`；后端 `backend/app/api/v1/photo.py` + `backend/app/services/nanoapple_image.py`
- 人像抠图在本地跑（`rembg` 的 `u2netp`，首次使用自动下载到 `~/.u2net/`），生成环节才调云端图像模型
- 需要 `GEMINI_API_KEY`（或可选的 `GPT_IMAGE_API_KEY`）；未配置时 `/api/v1/photo/config` 返回 `configured: false`，页面会提示「未配置」
- 书院场景背景取自 `ACADEMY_IMAGES_DIR`，人物形象用仓库内 `frontend/public/assets/historical*/` 的图片

交接前已执行 `npm run build`，前端生产构建成功。构建存在单个大于 500 kB 的代码块提示，不影响运行，后续可按页面继续拆包优化。

## 6. 建议接手顺序

1. 克隆仓库，直接使用默认的 `main` 分支。
2. 按 `.env.example` 新建本地配置，启动 MySQL、Redis、后端、Celery 和前端。
3. 执行 Alembic 迁移，确认 `/health` 和 Swagger 可访问。
4. 单独导入数据库备份和素材目录，确认知识库、图片和 PDF 预览路径正常。
5. 验证普通问答、历史人物文字对话、ASR/TTS，以及接入 LiveTalking 后的实时数字人。
6. 后续开发从最新 `main` 创建新的功能分支，完成验证后再合并回 `main`。

## 7. 云端部署

腾讯云的部署流程见 `deploy/tencent/README.md`。云端方案默认使用 MySQL + Redis + BM25，不运行 MinerU 和 Qdrant；较重的 PDF 解析建议在本地完成，再迁移数据库、上传文件和解析结果。
