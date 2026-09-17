"""数字人视频端点。

江万里使用 MuseTalk：文本 → MiMo TTS → 对数字人视频重新对口型。
"""
from __future__ import annotations

import asyncio
import io
import uuid
from pathlib import Path

import av
import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.core.deps import get_current_user
from app.core.config import settings
from app.models.user import User
from app.schemas.voice import LivetalkingTalkIn, TTSIn
from app.services.mimo_audio import mimo_audio
from app.services.musetalk_video import generate_lip_sync_video
from app.services.talking_portrait import generate_talking_video

router = APIRouter(prefix="/avatar", tags=["avatar"])

LIVETALKING_URL = "http://127.0.0.1:8010"


def _audio_duration_seconds(data: bytes) -> float:
    """读取音频时长（秒），用于前端按说话速度逐字显示回答。失败时返回 0。"""
    try:
        with av.open(io.BytesIO(data)) as container:
            if container.duration:
                return float(container.duration) / 1_000_000  # AV_TIME_BASE 为微秒
            for stream in container.streams.audio:
                if stream.duration and stream.time_base:
                    return float(stream.duration * stream.time_base)
    except Exception:  # noqa: BLE001
        return 0.0
    return 0.0

PHOTO_FIGURES = {
    # 罗从彦的立绘直接以中文名存放，这里映射到实际文件名（不含扩展名）
    "luocongyan": "罗从彦",
    "zhuxi": "zhuxi",
    "lvzuqian": "lvzuqian",
}


def _portrait_path(figure_id: str) -> Path:
    base = Path(settings.academy_images_dir) / "历史名人立绘"
    stem = PHOTO_FIGURES[figure_id]
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        candidate = base / f"{stem}{ext}"
        if candidate.exists():
            return candidate
    return base / f"{stem}.png"


@router.post("/talk")
async def avatar_talk(
    data: TTSIn,
    figure_id: str = "jiangwanli",
    _: User = Depends(get_current_user),
) -> FileResponse:
    """根据人物 id 和文本，生成对应的数字人说话视频。"""
    text = (data.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="内容不能为空。")

    try:
        audio_bytes, _ = await mimo_audio.synthesize(
            text,
            voice=data.voice,
            voice_style=data.voice_style,
            voice_desc=data.voice_desc,
            fmt="mp3",
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"语音合成失败：{exc}")

    out_dir = Path("uploads/talking_portrait/temp")
    out_dir.mkdir(parents=True, exist_ok=True)
    audio_path = out_dir / f"{figure_id}_{uuid.uuid4().hex[:12]}.mp3"
    audio_path.write_bytes(audio_bytes)

    try:
        if figure_id == "jiangwanli":
            out_path = await asyncio.to_thread(
                generate_lip_sync_video,
                audio_path,
                out_dir,
            )
        elif figure_id in PHOTO_FIGURES:
            image_path = _portrait_path(figure_id)
            if not image_path.exists():
                raise HTTPException(status_code=404, detail="该人物暂未配置数字人画像。")
            out_path = out_dir / f"{figure_id}_{uuid.uuid4().hex[:12]}.mp4"
            await asyncio.to_thread(
                generate_talking_video,
                str(image_path),
                audio_bytes,
                str(out_path),
                fps=25,
                body_motion=True,
            )
        else:
            raise HTTPException(status_code=404, detail="该人物暂未配置数字人视频。")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"生成说话视频失败：{exc}")

    return FileResponse(
        out_path,
        media_type="video/mp4",
        headers={"Cache-Control": "no-store"},
    )


@router.post("/livetalking-talk")
async def livetalking_talk(
    data: LivetalkingTalkIn,
    _: User = Depends(get_current_user),
):
    """江万里实时数字人：MiMo 合成语音 → 送给 LiveTalking 做口型驱动。"""
    text = (data.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="内容不能为空。")

    sessionid = (data.sessionid or "").strip()
    if not sessionid:
        raise HTTPException(status_code=400, detail="缺少 LiveTalking 会话 ID。")

    try:
        audio_bytes, _ = await mimo_audio.synthesize(
            text,
            voice=data.voice,
            voice_style=data.voice_style,
            voice_desc=data.voice_desc,
            fmt="wav",
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"语音合成失败：{exc}")

    duration = _audio_duration_seconds(audio_bytes)

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{LIVETALKING_URL}/humanaudio",
                data={"sessionid": sessionid},
                files={"file": ("answer.wav", audio_bytes, "audio/wav")},
            )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"LiveTalking 连接失败：{exc}")

    if resp.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"LiveTalking 音频驱动失败（{resp.status_code}）：{resp.text[:300]}",
        )

    return {"ok": True, "duration": round(duration, 2)}
