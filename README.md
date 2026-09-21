# 赣书院·智典（Yuzhang Academy）

江西（江右）书院数智平台：**Vue 3 + FastAPI + Celery + MySQL + Redis**。
包含书院知识库问答、图文检索、用户与内容管理、活动训练与题库，以及朱熹、陆九渊、王阳明等历史人物的文字 / 语音 / 真人视频数字人对话。

> 二次开发请看 [HANDOFF.md](HANDOFF.md)（代码入口、启动流程、未纳入 Git 的数据与当前状态）。
> 本项目由地质探矿 RAG 系统 **GeoRag** 改造而来，保留了多用户鉴权、会话持久化、知识库 CRUD、PDF 异步解析入库、BM25 检索、引用溯源等能力；生成模型从本地 Ollama 切换为云端多模态 API。

## 主要功能

- **书院知识库**：上传 PDF 后由 Celery 异步解析、分块和入库，支持知识库与文档管理。
- **图文智能问答**：BM25 检索书院文字与配图，再交给多模态大模型生成带引用的回答。
- **历史人物对话**：朱熹、罗从彦、江万里、陆九渊、吕祖谦、王阳明等人物拥有独立身份、生平、提示词和古风音色。
- **语音交互**：ASR 语音识别 + TTS 语音合成，可边生成回答边播放语音。
- **数字人**：LiveTalking 真人视频实时口型数字人（wav2lip 逐帧改口型 + WebRTC 推流）；未接入时回退到人物画像。
- **AI 合影留念**：上传（或现场拍摄）游客全身照 → 本地抠图 → 选先贤、书院场景、互动姿势与服装 → 调图像模型生成合影；照片仅用于本次生成，服务端不保存原图。
- **管理与学习**：用户鉴权、会话记录、活动管理、训练、题库和管理后台。

## 环境要求

| 依赖 | 版本 / 说明 |
|---|---|
| 操作系统 | Windows 10/11（一键脚本为 Windows 编写，macOS/Linux 见下方手动步骤） |
| Python | 3.10 – 3.12 |
| Node.js | 18+ |
| MySQL | 8.x（必需） |
| Redis | 任意 5+ 版本（必需，Celery 用） |
| Qdrant | 可选，默认关闭向量检索，不装也能跑 |
| NVIDIA GPU | 可选，只有实时数字人（LiveTalking）需要 |
| API Key | 问答 / 语音需要一家大模型服务的 Key（默认小米 MiMo） |

## 快速开始（Windows，四步）

```powershell
git clone https://github.com/ltlzjsj/yuzhang-academy.git
cd yuzhang-academy
```

1. **装依赖**：双击 `安装依赖.bat`
   自动完成：建 `backend\.venv` 并 `pip install -r requirements.txt` → 由 `.env.example` 生成 `backend\.env` → 前端 `npm ci` → 建数据库表（MySQL 已启动时）。

2. **起基础服务**（MySQL + Redis，二选一）：

   ```powershell
   # 方式 A：用仓库自带的 Docker 配置（需要 Docker Desktop）
   docker compose -f docker/docker-compose.yml up -d mysql redis

   # 方式 B：本机已安装 MySQL 8 + Redis，改成开机自启即可
   ```

   然后编辑 `backend\.env`，至少填两项：`MIMO_API_KEY`（或其它服务商 Key）与 `JWT_SECRET`（任意长随机串）。

3. **导入自带数据**（知识库语料 + 题库，约 67 MB 随仓库提供）：

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\import_data.ps1
   ```

   导入后即可用 `admin / shuyuan@2026` 登录（详见下方「数据与素材」）。书院图片、数字人帧数据体积较大，放在 Release 里按需下载，同样有脚本。

4. **启动**：双击 `启动系统.bat`
   它会依次拉起后端（:8000）、Celery、可选数字人（:8010）、前端（:5173），等待后自动打开浏览器，并在窗口里打印健康检查结果。关掉这个窗口即停止全部服务（也可以用 `停止系统.bat`）。

- 前端：http://localhost:5173
- 接口文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/health

### 手动启动（macOS / Linux / 想自己控制进程时）

```bash
# 1) 基础服务
docker compose -f docker/docker-compose.yml up -d mysql redis

# 2) 后端
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .\.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # 再编辑 .env
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# 3) 异步任务（PDF 解析入库，另开一个终端）
cd backend && celery -A app.workers.celery_app worker --loglevel=info --pool=solo

# 4) 前端
cd frontend && npm install && npm run dev
```

## 数据与素材

### 一、随仓库自带（克隆即有）

| 内容 | 位置 | 说明 |
|---|---|---|
| 知识库语料 | `data/kb/pdf/` | 《江右书院行》图文 11 个分卷，共 67 MB |
| 知识库数据 | `data/seed/georag_seed.sql` | 知识库、文档、检索分块、题库（已剔除账号 / 会话 / 训练记录等个人数据） |

MySQL 起来之后导入（仓库根目录执行）：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\import_data.ps1
```

它会依次建表（alembic）、导入数据、并把 PDF 还原到 `backend/uploads/` 下数据库记录的位置。
导入后可直接登录管理后台：

> **默认账号：`admin`　密码：`shuyuan@2026`**（登录后请立即修改，或自己注册账号并用 `python -m scripts.set_admin <用户名>` 提权）

想给活动资讯加示例数据：`cd backend && .\.venv\Scripts\python.exe -m scripts.seed_activities`

### 二、大素材包（GitHub Release，按需下载）

图片和数字人帧数据加起来 1.7 GB，放进仓库会让每次克隆都变慢，所以单独放在 [Release `assets-v1`](https://github.com/ltlzjsj/yuzhang-academy/releases/tag/assets-v1)。
一条命令自动下载并解压到正确位置，并按需改好 `backend/.env`：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\download_assets.ps1
# 也可以只下其中一部分
powershell -ExecutionPolicy Bypass -File scripts\download_assets.ps1 -Only images
```

| 附件 | 内容 | 大小 | 解压位置 |
|---|---|---|---|
| `shuyuan-images.zip` | 书院实拍、事件画、历史名人立绘（`书院文化图片/`） | ~911 MB | `assets/书院文化图片/`，并自动写入 `ACADEMY_IMAGES_DIR` |
| `livetalking-data.zip` | 说话帧 `data/avatars`、待机帧 `data/custom`、原始素材视频 `数字人/` | ~742 MB | `LiveTalking/data/`（没有 LiveTalking 时先放 `assets/livetalking/`） |

脚本会自动查询附件直链（直连 CDN），失败时退回 `releases/download` 地址，并支持断点续传；
某个通道长时间没有进展会自动切换。

> 国内网络访问 GitHub 下载大文件可能很慢（本项目开发机上实测约 1 MB / 2 分钟，上传反而正常）。
> 如果太慢，建议把两个 zip 镜像到 Gitee 或网盘分发，脚本里的下载地址换成镜像地址即可。

不下载也能跑：书院配图位置显示书院名首字印章占位，历史人物页只有文字 / 语音对话 + 人物画像。

### 三、自己录入

| 素材 | 放置方式 | 没有会怎样 |
|---|---|---|
| 书院实拍 / 事件画 / 立绘 | 把目录指给 `backend\.env` 的 `ACADEMY_IMAGES_DIR`（**相对路径以 `backend/` 为基准**，默认 `./academy_images`）。系统递归遍历，按书院名在**文件路径**里做子串匹配，**无需按书院分文件夹** | 配图位置显示首字印章占位 |
| 书院 PDF 语料 | 后台新建知识库 → 上传 PDF → Celery 自动解析分块 | 知识库为空，问答只能闲聊 |
| 数字人素材 | 见 [docs/数字人实时引擎.md](docs/数字人实时引擎.md) | 历史人物页只有文字 / 语音对话 + 人物画像 |

> 「合影留念」页的书院场景背景同样取自 `ACADEMY_IMAGES_DIR`，人物形象用仓库自带的
> `frontend/public/assets/historical*/` 图片（「写实 3D」按钮指的是写实渲染图，与已移除的 GLB 模型无关）。

## 配置

复制 `backend/.env.example` 为 `backend/.env` 后按需修改，重点项：

```dotenv
LLM_PROVIDER=mimo                # 也可以切 minimax / ollama
DEFAULT_CHAT_MODEL=mimo-v2.5     # 全模态可识图；仅文本场景才用 mimo-v2.5-pro
MIMO_API_KEY=                    # ← 填自己的 Key，切勿提交到 Git
MIMO_BASE_URL=https://api.xiaomimimo.com/anthropic

JWT_SECRET=                      # ← 换成长随机串

RAG_VECTOR_ENABLED=false         # 关闭向量检索（BM25 即可，无需 Qdrant）
RAG_GATE_ENABLED=true            # 单域书院场景的语义门控
ACADEMY_IMAGES_DIR=./academy_images
MINERU_OUTPUT_DIR=./mineru_out

# AI 合影：图像生成 Key（不填则合影页提示未配置、无法生成）
GEMINI_API_KEY=                  # ← 填自己的图像生成 Key
GEMINI_MODEL=gemini-3.1-flash-image-preview-time
# GPT_IMAGE_API_KEY=             # 可选：换用 GPT Image 2 通道
```

> 合影页的人像抠图在本地跑（`rembg` 的 `u2netp` 模型，约 4.4 MB，**首次使用时自动下载** 到 `~/.u2net/`），
> 生成环节才调用云端图像模型。访问 `GET /api/v1/photo/config` 可以看到当前哪些通道已配置好。

也可以用环境变量临时注入 Key，不写进文件：

```powershell
$env:MIMO_API_KEY="你的Key"
```

> `backend/.env`、`deploy/tencent/*.env` 都已被 Git 忽略。**请勿把真实 Key 提交到仓库。**

## 目录结构

```
backend/            FastAPI + Celery（app/api/v1 路由、app/services 业务、alembic 迁移）
frontend/           Vue 3 + Vite（src/views 页面、src/components/agent 数字人组件）
docker/             本地开发的 MySQL / Redis / Qdrant
deploy/tencent/     服务器上的完整 Docker 部署（见目录内 README）
docs/               数字人引擎接入说明 + LiveTalking 本地补丁
data/               自带业务数据：知识库语料 PDF + 数据库种子 SQL
scripts/            数据导入、素材包下载、停止服务等辅助脚本
启动系统.bat        一键启动
安装依赖.bat        首次运行的环境安装
停止系统.bat        停止由本仓库启动的进程
```

## 技术要点

- **大模型**：默认小米 **MiMo `mimo-v2.5`**（Anthropic Messages API）。`mimo-v2.5` 才是全模态可识图，`mimo-v2.5-pro` 仅文本，图文场景务必用前者。由 `LLM_PROVIDER` 控制，可切回 `ollama`。
- **检索**：`RAG_VECTOR_ENABLED=false` 时用 **BM25 + 书院名加权**（`app/services/academies.py`），不依赖 embedding 模型与 Qdrant。
- **图文**：解析出的每页配图随入库写进 `chunk.meta.images`，检索命中后以 web URL 回传展示，并把若干张交给多模态模型识图，静态服务挂载在 `/api/v1/assets/mineru`。
- **数字人**：`frontend/src/components/agent/LiveTalkingAvatar.vue`（LiveTalking 实时视频数字人）、`TalkingPortrait.vue`（画像开口说话，作为回退）。原先基于 Three.js + GLB 的 3D 数字人已整体移除。
- **实时数字人**：见 [docs/数字人实时引擎.md](docs/数字人实时引擎.md)。
- **AI 合影**：前端 `frontend/src/views/Photo.vue`；后端 `backend/app/api/v1/photo.py`（`/bg-remove` 本地抠图、`/generate` 调图像模型、`/config` 查配置）+ `backend/app/services/nanoapple_image.py`。

## 服务器部署

`deploy/tencent/` 提供一套完整容器化部署（MySQL + Redis + 后端 + Celery + Nginx 前端）：

```powershell
Copy-Item deploy/tencent/backend.env.example deploy/tencent/backend.env
Copy-Item deploy/tencent/deploy.env.example deploy/tencent/deploy.env
cd deploy/tencent
docker compose --env-file deploy.env -f docker-compose.yml up -d --build
```

细节（必填变量、目录准备、日志排查、数据迁移）见 `deploy/tencent/README.md`。
注意：`DB_USER` / `DB_PASSWORD` / `DB_NAME` 必须与 `deploy.env` 完全一致；`JWT_SECRET` 必须改成随机串。

## 常见问题

| 现象 | 排查 |
|---|---|
| 后端起不来，日志报数据库错误 | MySQL 是否在跑？`backend/.env` 的 `DB_*` 是否与实际一致？ |
| 页面能开但接口 500 | 看启动窗口里的后端日志；确认 `alembic upgrade head` 已执行 |
| 问回答复为空 / 报鉴权失败 | `MIMO_API_KEY` 没填或已失效 |
| 数字人黑屏 | LiveTalking 未启动或该人物 `data/avatars/<id>` 不存在，见 `docs/数字人实时引擎.md` |
| 书院配图不显示 | `ACADEMY_IMAGES_DIR` 路径不对，或文件名里没有书院名 |
| 上传 PDF 后一直不解析 | Celery worker 没起，或 Redis 没起 |
| 合影页提示未配置 / 生成失败 | `backend\.env` 没填 `GEMINI_API_KEY` 或 Key 失效；`GET /api/v1/photo/config` 可确认各通道状态 |
| 合影第一次生成明显偏慢 | 首次使用会下载并加载抠图模型 `u2netp`（约 4.4 MB），之后正常 |

## 维护要点

- 生成走云端 API，注意配额与网络；连接失败会通过 SSE 的 `error` 事件返回。
- BM25 索引按知识库缓存，文档入库 / 删除后自动失效。
- 图片静态目录由 `MINERU_OUTPUT_DIR` 决定，经前端 `/api` 代理访问。
- 需要完全离线：设 `LLM_PROVIDER=ollama`、`RAG_VECTOR_ENABLED=true`，并自行启动 Ollama 与 Qdrant。

## License

见 [LICENSE](LICENSE)。
