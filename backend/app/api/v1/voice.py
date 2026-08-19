"""历史名人语音对话 — ASR / TTS 端点 (基于小米 MiMo)。

只做「语音 ↔ 文字」的转换，对话本身仍复用既有的无状态 ``/agent/stream``：
  前端流程 = 录音 → POST /voice/asr 得到文字 → 走 /agent/stream 得到回答
            → POST /voice/tts 把回答合成语音播放。

这样语音层与对话层解耦：换 persona、加 RAG 都不影响这里。
"""
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse

from app.core.config import settings
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.voice import ASRResult, TTSIn, VoiceListOut
from app.services.mimo_audio import PRESET_VOICES, mimo_audio

log = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])

# 浏览器 MediaRecorder 常见 mime → MiMo 接受的 mime。MiMo 文档目前列出
# wav / mp3；webm/ogg 若不被支持需前端转码或后端转码（此处先透传，留 TODO）。
_MIME_FALLBACK = {
    "audio/webm": "audio/webm",
    "audio/ogg": "audio/ogg",
    "audio/wav": "audio/wav",
    "audio/x-wav": "audio/wav",
    "audio/mpeg": "audio/mpeg",
    "audio/mp3": "audio/mpeg",
}


@router.get("/voices", response_model=VoiceListOut)
async def list_voices(_: User = Depends(get_current_user)) -> VoiceListOut:
    return VoiceListOut(voices=PRESET_VOICES, default=settings.mimo_tts_voice)


@router.post("/asr", response_model=ASRResult)
async def speech_to_text(
    file: UploadFile = File(...),
    language: str = Form("auto"),
    _: User = Depends(get_current_user),
) -> ASRResult:
    """语音识别：上传音频文件，返回识别文本。"""
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="空音频。")
    # 去掉 `;codecs=opus` 等参数，否则会污染 data URL 的 mime 前缀。
    base_mime = (file.content_type or "").split(";")[0].strip().lower()
    mime = _MIME_FALLBACK.get(base_mime, base_mime or "audio/wav")
    try:
        text = await mimo_audio.transcribe(raw, mime_type=mime, language=language)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        log.warning("ASR failed: %s", e)
        raise HTTPException(status_code=502, detail=f"语音识别失败：{e}")
    return ASRResult(text=text)


@router.post("/tts")
async def text_to_speech(
    data: TTSIn,
    _: User = Depends(get_current_user),
) -> Response:
    """语音合成：文字 → 音频二进制（默认 mp3）。"""
    try:
        audio_bytes, mime = await mimo_audio.synthesize(
            data.text,
            voice=data.voice,
            voice_style=data.voice_style,
            voice_desc=data.voice_desc,
            fmt=data.format,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        log.warning("TTS failed: %s", e)
        raise HTTPException(status_code=502, detail=f"语音合成失败：{e}")
    return Response(content=audio_bytes, media_type=mime)


@router.post("/tts/stream")
async def text_to_speech_stream(
    data: TTSIn,
    _: User = Depends(get_current_user),
) -> StreamingResponse:
    """低延迟语音合成流：输出 24kHz mono PCM16LE，前端边收边播。"""
    async def chunks():
        try:
            async for chunk in mimo_audio.synthesize_stream(
                data.text,
                voice=data.voice,
                voice_style=data.voice_style,
                voice_desc=data.voice_desc,
                fmt="pcm16",
            ):
                yield chunk
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:  # noqa: BLE001
            log.warning("streaming TTS failed: %s", e)
            raise HTTPException(status_code=502, detail=f"语音合成失败：{e}")

    return StreamingResponse(
        chunks(),
        media_type="application/octet-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "X-Audio-Format": "pcm16",
            "X-Audio-Sample-Rate": "24000",
            "X-Audio-Channels": "1",
        },
    )
