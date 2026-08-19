# 赣书院·智典 (ShuyuanRAG)

> 接手开发请先阅读 [HANDOFF.md](HANDOFF.md)，其中说明了代码入口、启动流程、未纳入 Git 的业务数据和当前开发状态。

江西（江右）书院数智平台：Vue 3 + FastAPI + Celery + MySQL + Redis。平台包含书院图文知识库问答、用户与内容管理、活动训练与题库，以及朱熹、陆九渊、王阳明等历史人物的文字、语音和浏览器端 3D 数字人对话。

> 本项目由地质探矿 RAG 系统 **GeoRag** 改造而来，保留了多用户鉴权、会话持久化、知识库 CRUD、PDF 异步解析入库（MinerU）、BM25 检索、引用溯源等能力；生成模型从本地 Ollama 切换为 MiMo 云端多模态 API。

## 主要功能

- **书院知识库**：上传 PDF 后由 Celery 异步解析、分块和入库，支持知识库与文档管理。
- **图文智能问答**：使用 BM25 检索书院文字与配图，再交给小米 MiMo 多模态模型生成带引用的回答。
- **历史人物对话**：朱熹、陆九渊、王阳明等人物拥有独立身份、生平、提示词和古风音色。
- **语音交互**：支持 MiMo ASR 语音识别和 TTS 语音合成，可边生成回答边播放语音。
- **3D 数字人**：Three.js 在浏览器加载 GLB 人物，支持待机、说话手势、口型、眨眼和头部动作，并跟随 TTS 音量变化。
- **管理与学习**：包含用户鉴权、会话记录、活动管理、训练、题库和管理后台。

### 3D 数字人模型

3D 入口位于历史人物对话页面，核心组件为 `frontend/src/components/agent/DigitalHuman3D.vue`。

- 默认模型：`frontend/public/models/avatar.glb`
- 朱熹模型：`frontend/public/models/zhuxi.glb`
- 王阳明模型：`frontend/public/models/wangyangming.glb`
- 动作模型：`frontend/public/models/anim/`
- 人物专属模型约定：`frontend/public/models/<人物 id>.glb`

没有专属 GLB 的人物会自动回退到默认模型。加载器支持 Draco 和 Meshopt 压缩；模型自带动画时优先使用自带动画，否则使用公共待机和说话动作。

## 关键变化

- **大模型**：不再使用本地 Ollama / gemma3。改用 **MiMo `mimo-v2.5`**（Anthropic Messages API，`https://api.xiaomimimo.com/anthropic/v1/messages`）。注意：`mimo-v2.5` 才是**全模态(可识图)**，`mimo-v2.5-pro` 仅文本，图文务必用 `mimo-v2.5`。由 `LLM_PROVIDER` 开关控制，仍可切回 `ollama`。
- **检索**：关闭向量检索（`RAG_VECTOR_ENABLED=false`），改为 **BM25 关键词 + 书院名加权**（见 `app/services/academies.py`），无需任何本地 embedding 模型，也无需 Qdrant。单域书本场景关闭了语义门控（`RAG_GATE_ENABLED=false`）。
- **图文**：MinerU 解析出的每页配图随入库写进 `chunk.meta.images`；检索命中后，图片以 web URL 回传前端展示，并将其中若干张 base64 交给 MiMo 多模态识图。图片经 `/api/v1/assets/mineru/...` 静态服务。

## 先决条件

- Windows + Docker Desktop（MySQL / Redis）
- Python/Conda 环境（如 `D:\anaconda3\envs\geogemma`），已装 `backend/requirements.txt` 与 MinerU
- Node.js 18+
- **MiMo Api Key**：到 https://platform.xiaomimimo.com 申请 / 重置，通过环境变量注入，切勿写入代码或提交 git。

## 配置

复制并编辑 `backend/.env`（已预置书院默认值），重点：

```dotenv
LLM_PROVIDER=mimo
DEFAULT_CHAT_MODEL=mimo-v2.5     # 全模态可识图；勿用 mimo-v2.5-pro(仅文本)
MIMO_MODEL=mimo-v2.5
MIMO_API_KEY=        # ← 填入你重置后的新 Key（或用环境变量 MIMO_API_KEY 注入）
RAG_VECTOR_ENABLED=false
RAG_GATE_ENABLED=false
MINERU_OUTPUT_DIR=D:/workplace/GeoRag/mineru_out
ACADEMY_IMAGES_DIR=D:/workplace/GeoRag/academy_images
```

PowerShell 注入 Key（推荐，不落盘）：

```powershell
$env:MIMO_API_KEY="你的新Key"
```

## 启动

基础服务（MySQL / Redis）：

```powershell
cd D:\workplace\GeoRag\docker
docker compose up -d
```

后端 API：

```powershell
conda activate geogemma
cd D:\workplace\GeoRag\backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Celery worker（PDF 解析入库）：

```powershell
conda activate geogemma
cd D:\workplace\GeoRag\backend
celery -A app.workers.celery_app worker --loglevel=info --pool=solo
```

前端：

```powershell
cd D:\workplace\GeoRag\frontend
npm install
npm run dev
```

访问：

- 前端：http://127.0.0.1:5173
- Swagger：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/health

## Docker 是做什么的

项目提供两套 Docker 配置：本地开发模式只启动数据库等基础服务；完整容器模式会同时启动前端、后端和异步任务。第一次运行时，Docker 会从镜像仓库拉取所需基础镜像，后续通常直接使用本地缓存。

### 第一次使用 Docker

1. 安装并启动 Docker Desktop（Windows/macOS）或 Docker Engine + Compose Plugin（Linux）。
2. 克隆项目并进入项目目录：

```powershell
git clone https://github.com/ZhouJiaJun2333/yuzhang-academy.git
cd yuzhang-academy
```

3. 确认 Docker 引擎已经启动。下面命令应同时显示 `Client` 和 `Server` 信息：

```powershell
docker version
docker compose version
```

如果只有 `Client`、没有 `Server`，先打开 Docker Desktop，等待状态显示为 Running。

### 本地开发：`docker/docker-compose.yml`

本地 Docker 只负责运行基础服务，前端、后端和 Celery 仍在电脑上分别启动，便于开发调试：

- **MySQL 8**：保存用户、知识库、文档分块、会话、活动、训练和题库数据。
- **Redis 7**：作为 Celery 的任务队列和结果存储。
- **Qdrant**：用于可选的向量检索；当前默认关闭向量检索、使用 BM25，因此可以不依赖它。

数据保存在 Docker volumes 中，停止或重启容器不会自动丢失。`docker compose down -v` 会删除这些数据卷，请谨慎使用。

拉取镜像并启动：

```powershell
docker compose -f docker/docker-compose.yml pull
docker compose -f docker/docker-compose.yml up -d
docker compose -f docker/docker-compose.yml ps
```

正常情况下会看到 `georag-mysql`、`georag-redis`、`georag-qdrant` 三个容器。当前项目默认使用 BM25，若确定不使用向量检索，也可以只启动 MySQL 和 Redis：

```powershell
docker compose -f docker/docker-compose.yml up -d mysql redis
```

停止容器但保留数据：

```powershell
docker compose -f docker/docker-compose.yml down
```

此模式下还需按照上面的“启动”章节，在电脑上单独运行后端、Celery 和前端。

### 完整 Docker 部署：`deploy/tencent/docker-compose.yml`

这套配置用于腾讯云等服务器的完整容器化部署，包含：

- MySQL
- Redis
- FastAPI 后端
- Celery worker
- Vue 前端和 Nginx

完整模式默认采用 MySQL + BM25，不运行 Qdrant 和 MinerU；较重的 PDF 解析建议在本地完成后，再迁移数据库、上传文件和解析结果。

#### 1. 创建配置文件

在项目根目录执行：

```powershell
Copy-Item deploy/tencent/backend.env.example deploy/tencent/backend.env
Copy-Item deploy/tencent/deploy.env.example deploy/tencent/deploy.env
New-Item -ItemType Directory -Force deploy/tencent/data/images
New-Item -ItemType Directory -Force deploy/tencent/data/uploads
New-Item -ItemType Directory -Force deploy/tencent/data/mineru_out
```

Linux/macOS 可将 `Copy-Item` 换成 `cp`，将 `New-Item` 换成 `mkdir -p`。

编辑 `deploy/tencent/deploy.env`：

```dotenv
HTTP_PORT=8080
DATA_DIR=./data
MYSQL_ROOT_PASSWORD=换成强密码
DB_USER=georag
DB_PASSWORD=换成强密码
DB_NAME=georag
```

再编辑 `deploy/tencent/backend.env`：

- `DB_USER`、`DB_PASSWORD`、`DB_NAME` 必须和 `deploy.env` 完全一致。
- 把 `JWT_SECRET` 改为足够长的随机字符串。
- 默认对话使用 MiniMax，需填写 `MINIMAX_API_KEY`。
- 历史人物语音识别与合成需填写 `MIMO_API_KEY`；留空时文字功能仍可运行，但语音不可用。
- 如果改用 MiMo 生成文字回答，将 `LLM_PROVIDER` 和模型配置改为 README 前面“配置”章节中的 MiMo 设置。
- 使用 `HTTP_PORT=8080` 时，将 `CORS_ORIGINS` 加入 `http://localhost:8080` 和 `http://127.0.0.1:8080`。

`backend.env` 和 `deploy.env` 已被 Git 忽略，禁止把真实密码或 API Key 提交到仓库。

#### 2. 拉取镜像并构建项目镜像

```powershell
cd deploy/tencent
docker compose --env-file deploy.env -f docker-compose.yml config -q
docker compose --env-file deploy.env -f docker-compose.yml pull mysql redis
docker compose --env-file deploy.env -f docker-compose.yml build --pull backend worker frontend
```

这里会拉取 MySQL、Redis、Python、Node.js 和 Nginx 等基础镜像，并使用仓库里的 Dockerfile 构建本项目的前后端镜像。首次构建需要下载依赖，耗时会明显长于后续启动。

#### 3. 启动并检查

```powershell
docker compose --env-file deploy.env -f docker-compose.yml up -d
docker compose --env-file deploy.env -f docker-compose.yml ps
```

等待 `mysql`、`redis`、`backend` 显示为 `healthy`，`worker` 和 `frontend` 显示为运行状态，然后访问：

```text
http://localhost:8080
```

如启动失败，查看日志：

```powershell
docker compose --env-file deploy.env -f docker-compose.yml logs -f backend
docker compose --env-file deploy.env -f docker-compose.yml logs -f worker
```

停止但保留数据库：

```powershell
docker compose --env-file deploy.env -f docker-compose.yml down
```

重新构建更新后的代码：

```powershell
docker compose --env-file deploy.env -f docker-compose.yml up -d --build
```

云服务器的目录、端口和数据迁移说明见 `deploy/tencent/README.md`。

## 录入书院语料

1. 登录后新建一个知识库（KB）。
2. 把 `pdf/` 下的 11 个分卷依次上传到该 KB（`POST /api/v1/documents/upload?kb_id=...` 或前端上传入口）。
3. Celery worker 会逐个 MinerU 解析 → 分块 → 写库（含每页配图路径），无需 embedding。
4. 入库完成后，在聊天页打开 RAG、勾选该 KB，即可问答。例如「白鹿洞书院的历史」，答案末尾会标注 `[n]` 引用，下方出现该书院的高清配图。

> 旧的 `mineru_out/`、`kb_1`、`kb_3` 是地质语料残留，可删除。

### 自备书院图片（推荐）

除了从 PDF 自动抽取的配图，你可以放入手工整理的高清图，质量更可控。把目录指向 `ACADEMY_IMAGES_DIR`（默认 `D:/workplace/GeoRag/书院文化图片`）即可——**无需按书院重整目录**：系统会递归遍历该目录，按书院名在「文件路径」里做子串匹配。书院名出现在文件名或父目录里都行，例如：

```
书院文化图片/
  组织拍摄了江西遗存书院/吉安科山书院.JPG          # 文件名含"科山书院"
  组织拍摄了江西遗存书院/江西四大书院/白鹿洞书院/...  # 父目录含"白鹿洞书院"
  组织画家绘制了十大书院事件图/潋江书院与红色故土.jpg # 事件画也会被"潋江书院"命中
```

当用户问题点名某书院时，系统取所有路径含该名的图，在答案下方展示，并把其中若干张交给 MiMo 识图（**放好图即生效，无需重启或入库**）。书院名录见 `app/services/academies.py`。

## 维护要点

- 生成走 MiMo 云端，注意 Api Key 配额与网络；连接失败会在 SSE `error` 事件返回。
- BM25 索引按知识库缓存，文档入库 / 删除后会自动失效缓存。
- 图片静态目录由 `MINERU_OUTPUT_DIR` 决定，挂载在 `/api/v1/assets/mineru`，经前端 `/api` 代理访问。
- 如需切回本地模型：设 `LLM_PROVIDER=ollama`、`RAG_VECTOR_ENABLED=true`，并按需启动 Ollama / Qdrant。
