import logging
import json

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from app.services import nanoapple_image

log = logging.getLogger(__name__)
router = APIRouter(prefix="/photo", tags=["photo"])

_MAX_BYTES = 10 * 1024 * 1024
_MODEL = "u2netp"  # 轻量人像分割模型；追求更好质量可换 u2net_human_seg / isnet-general-use
_session = None


class GenerateIn(BaseModel):
    provider: str = "gemini"
    visitorImage: str
    faceImage: str | None = None
    poetImage: str
    backgroundImage: str
    person: str = ""
    quote: str = ""
    pose: str | None = None
    costume: bool = False


def _get_session():
    global _session
    if _session is None:
        from rembg import new_session

        log.info("loading rembg session: %s", _MODEL)
        _session = new_session(_MODEL)
    return _session


@router.post("/bg-remove")
async def bg_remove(file: UploadFile = File(...)):
    """去除上传照片的背景，返回透明背景 PNG。"""
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="空图片")
    if len(raw) > _MAX_BYTES:
        raise HTTPException(status_code=400, detail="图片过大（请控制在 10MB 以内）")
    try:
        from rembg import remove

        out = remove(raw, session=_get_session(), post_process_mask=True)
    except Exception as e:
        log.exception("rembg remove failed")
        raise HTTPException(status_code=502, detail=f"抠图失败：{e}")
    return Response(content=out, media_type="image/png")


@router.get("/config")
async def photo_config():
    """返回已配置的生图引擎，不暴露 API Key。"""
    return nanoapple_image.providers_config()


@router.post("/generate")
async def photo_generate(data: GenerateIn):
    """AI 合影：以 SSE 流式返回生成进度，最终事件包含 image。"""
    if data.provider not in ("gemini", "gptImage2"):
        raise HTTPException(status_code=400, detail="不支持的生图服务")

    def _sse(obj: dict) -> str:
        return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"

    async def events():
        if data.provider == "gptImage2":
            yield _sse(
                {
                    "error": "GPT Image 2 当前仅支持文生图，不支持本项目的游客、诗人和书院参考图融合，请选择 Gemini 3.1。"
                }
            )
            return
        try:
            async for ev in nanoapple_image.stream_generate_photo(data.model_dump()):
                yield _sse(ev)
        except ValueError as e:
            yield _sse({"error": str(e)})
        except Exception as e:
            log.exception("photo generate failed")
            yield _sse({"error": str(e) or "图像生成服务请求失败"})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
