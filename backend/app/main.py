import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse

# Bypass VPN system proxy for all local services (Qdrant, Redis, MySQL, Ollama)
_LOCAL = "localhost,127.0.0.1,::1"
for _k in ("NO_PROXY", "no_proxy"):
    _existing = os.environ.get(_k, "")
    if _LOCAL not in _existing:
        os.environ[_k] = f"{_LOCAL},{_existing}".strip(",")
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1 import api_router
from app.core.config import settings

if settings.hf_endpoint.strip():
    os.environ["HF_ENDPOINT"] = settings.hf_endpoint
else:
    os.environ.pop("HF_ENDPOINT", None)
if settings.hf_home.strip():
    os.environ["HF_HOME"] = settings.hf_home
os.environ["MINERU_MODEL_SOURCE"] = settings.mineru_model_source


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.env.lower() not in {"dev", "local", "test"} and settings.jwt_secret in {
        "change-me",
        "change-me-to-a-long-random-string",
    }:
        raise RuntimeError("JWT_SECRET must be changed outside development")

    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)

    # Warm models so the first chat doesn't pay cold-load latency. Keep a
    # strong ref on app.state so tasks aren't garbage-collected mid-flight.
    import asyncio

    app.state.warm_tasks = []
    if settings.warm_models_on_start and settings.llm_provider.lower() == "ollama":
        from app.services.ollama_client import ollama

        async def _warm():
            try:
                await ollama.warm(settings.default_chat_model)
                if settings.rag_vector_enabled:
                    await ollama.warm(settings.embed_model)
            except Exception:
                pass

        app.state.warm_tasks.append(asyncio.create_task(_warm()))

    if settings.warm_reranker_on_start:
        def _warm_reranker():
            try:
                from app.services.rag.reranker import rerank_scores
                rerank_scores("warmup", ["warmup"])
            except Exception:
                pass

        asyncio.get_running_loop().run_in_executor(None, _warm_reranker)

    try:
        yield
    finally:
        try:
            from app.services.llm import aclose as llm_aclose
            await llm_aclose()
        except Exception:
            pass
        try:
            from app.services.mimo_audio import mimo_audio
            await mimo_audio.aclose()
        except Exception:
            pass
        try:
            from app.services.vector_store import close_client
            close_client()
        except Exception:
            pass


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

_FIELD_LABELS = {
    "username": "用户名",
    "password": "密码",
    "email": "邮箱",
    "title": "标题",
    "name": "名称",
    "question_count": "题目数量",
}


def _validation_message(error: dict) -> str:
    loc = [str(x) for x in error.get("loc", []) if x not in ("body", "query", "path")]
    field = _FIELD_LABELS.get(loc[-1], loc[-1]) if loc else "参数"
    typ = str(error.get("type") or "")
    ctx = error.get("ctx") or {}
    if typ.endswith("string_too_short"):
        return f"{field}至少需要 {ctx.get('min_length', 1)} 个字符"
    if typ.endswith("string_too_long"):
        return f"{field}不能超过 {ctx.get('max_length', '限制')} 个字符"
    if typ.endswith("value_error"):
        return f"{field}格式不正确"
    if "email" in typ:
        return "邮箱格式不正确"
    return f"{field}填写不正确"


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_, exc: RequestValidationError):
    errors = exc.errors()
    detail = _validation_message(errors[0]) if errors else "提交内容不完整或格式不正确"
    return JSONResponse(status_code=422, content={"detail": detail})

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def cache_static_assets(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/v1/assets/") and response.status_code < 400:
        response.headers.setdefault("Cache-Control", "public, max-age=604800, stale-while-revalidate=86400")
    return response


app.include_router(api_router)


def _asset_root(kind: str) -> Path:
    if kind == "academy":
        return Path(settings.academy_images_dir)
    if kind == "mineru":
        return Path(settings.mineru_output_dir)
    raise HTTPException(status_code=404, detail="unknown image kind")


@app.get("/api/v1/assets/thumb/{kind}/{src:path}")
async def image_thumb(
    kind: str,
    src: str,
    w: int = Query(288, ge=64, le=640),
    h: int = Query(192, ge=64, le=640),
) -> FileResponse:
    root = _asset_root(kind).resolve()
    fp = (root / src.lstrip("/")).resolve()
    try:
        fp.relative_to(root)
    except ValueError:
        raise HTTPException(status_code=404, detail="image not found")
    if not fp.is_file():
        raise HTTPException(status_code=404, detail="image not found")

    cache_root = Path(settings.upload_dir).resolve() / ".thumbs" / kind
    rel_key = fp.relative_to(root).as_posix().replace("/", "__").replace("\\", "__")
    thumb = cache_root / f"{w}x{h}_{fp.stat().st_mtime_ns}_{rel_key}.jpg"
    if not thumb.exists():
        thumb.parent.mkdir(parents=True, exist_ok=True)
        try:
            from PIL import Image

            with Image.open(fp) as img:
                img = img.convert("RGB")
                img.thumbnail((w, h))
                thumb.parent.mkdir(parents=True, exist_ok=True)
                img.save(thumb, format="JPEG", quality=72, optimize=True)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"thumbnail failed: {e}")

    return FileResponse(
        thumb,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=604800, stale-while-revalidate=86400"},
    )

# 图文: serve MinerU-extracted figures. Mounted under /api so it transparently
# reuses the frontend's Vite `/api` dev proxy. Chunk meta stores image `src` as
# "<stem>/<method>/images/<hash>.jpg" → URL /api/v1/assets/mineru/<src>.
_mineru_dir = Path(settings.mineru_output_dir)
_mineru_dir.mkdir(parents=True, exist_ok=True)
app.mount(
    "/api/v1/assets/mineru",
    StaticFiles(directory=str(_mineru_dir)),
    name="mineru-assets",
)

# 自备书院图片：<academy_images_dir>/<书院名>/*.jpg → /api/v1/assets/academy/<src>
_academy_dir = Path(settings.academy_images_dir)
_academy_dir.mkdir(parents=True, exist_ok=True)
app.mount(
    "/api/v1/assets/academy",
    StaticFiles(directory=str(_academy_dir)),
    name="academy-assets",
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "app": settings.app_name, "env": settings.env}
