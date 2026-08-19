import logging

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response

log = logging.getLogger(__name__)
router = APIRouter(prefix="/photo", tags=["photo"])

_MAX_BYTES = 10 * 1024 * 1024
_MODEL = "u2netp"  # 轻量人像分割模型；追求更好质量可换 u2net_human_seg / isnet-general-use
_session = None


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
