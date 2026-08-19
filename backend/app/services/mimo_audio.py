"""MiMo 语音客户端 — 语音识别 (ASR) 与语音合成 (TTS v2.5)。

与 ``mimo_client.py`` 不同：聊天用的是 Anthropic Messages API
(``{base}/anthropic/v1/messages``)，而语音 ASR/TTS 走的是 OpenAI 风格端点
``https://api.xiaomimimo.com/v1/chat/completions``，鉴权同样用 ``api-key`` 头。

参考文档：
  - ASR: https://mimo.mi.com/docs/zh-CN/quick-start/usage-guide/audio/Speech-Recognition
  - TTS: https://mimo.mi.com/docs/zh-CN/quick-start/usage-guide/audio/speech-synthesis-v2.5

设计上保持「薄封装」：只负责拼请求 / 解响应，业务策略（鉴权、音色挑选、
错误信息文案）留给上层路由处理。复用一个常驻 ``httpx.AsyncClient``。
"""
from __future__ import annotations

import base64
import json
from collections.abc import AsyncIterator

import httpx

from app.core.config import settings

# 文档约定：base64 编码后音频不超过 10MB。
_MAX_AUDIO_BYTES = 10 * 1024 * 1024

# 预置音色清单（仅用于前端展示 / 校验，真实可用列表以 MiMo 文档为准）。
PRESET_VOICES = [
    "mimo_default", "冰糖", "茉莉", "苏打", "白桦", "Mia", "Chloe", "Milo", "Dean",
]


class MiMoAudioClient:
    """MiMo ASR/TTS 的异步薄封装。"""

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self.base_url = (base_url or settings.mimo_audio_base_url).rstrip("/")
        self.api_key = api_key or settings.mimo_api_key
        self._client: httpx.AsyncClient | None = None

    def _ensure(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(connect=15, read=None, write=60, pool=15),
                limits=httpx.Limits(max_connections=16, max_keepalive_connections=8),
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
        self._client = None

    def _headers(self) -> dict:
        if not self.api_key:
            raise RuntimeError("MIMO_API_KEY 未配置：请在环境变量或 .env 中设置 MiMo Api Key。")
        return {"api-key": self.api_key, "Content-Type": "application/json"}

    @property
    def _url(self) -> str:
        return f"{self.base_url}/v1/chat/completions"

    # ---------------------------------------------------------------- ASR ---
    async def transcribe(
        self,
        audio_bytes: bytes,
        *,
        mime_type: str = "audio/wav",
        language: str = "auto",
        model: str | None = None,
    ) -> str:
        """语音转文字。返回识别出的纯文本。

        ``language`` ∈ {"auto", "zh", "en"}；``mime_type`` 支持 wav / mp3。
        """
        if not audio_bytes:
            raise ValueError("空音频。")
        if len(audio_bytes) > _MAX_AUDIO_BYTES:
            raise ValueError("音频过大（base64 后需 ≤ 10MB）。")

        b64 = base64.b64encode(audio_bytes).decode("ascii")
        payload = {
            "model": model or settings.mimo_asr_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {"data": f"data:{mime_type};base64,{b64}"},
                        }
                    ],
                }
            ],
            "asr_options": {"language": language},
            "stream": False,
        }

        client = self._ensure()
        resp = await client.post(self._url, json=payload, headers=self._headers())
        if resp.status_code >= 400:
            raise RuntimeError(f"MiMo ASR {resp.status_code}: {resp.text[:500]}")
        data = resp.json()
        return _extract_text(data)

    # ---------------------------------------------------------------- TTS ---
    def _tts_payload(
        self,
        text: str,
        *,
        voice: str | None,
        voice_style: str | None,
        voice_desc: str | None,
        fmt: str,
        model: str | None,
        stream: bool,
    ) -> dict:
        """构造 TTS 请求体。

        ``voice_desc`` 非空 → 走「声音设计」模型(古风名儒音色)：描述放在 user
        消息，要朗读的文本放在 assistant 消息。否则用预置音色 ``voice``。
        """
        if voice_desc:
            return {
                "model": model or settings.mimo_tts_voicedesign_model,
                "messages": [
                    {"role": "user", "content": voice_desc},
                    {"role": "assistant", "content": text},
                ],
                "audio": {"format": fmt},
                "stream": stream,
            }
        messages = []
        if voice_style:
            messages.append({"role": "user", "content": voice_style})
        messages.append({"role": "assistant", "content": text})
        return {
            "model": model or settings.mimo_tts_model,
            "messages": messages,
            "audio": {"format": fmt, "voice": voice or settings.mimo_tts_voice},
            "stream": stream,
        }

    async def synthesize(
        self,
        text: str,
        *,
        voice: str | None = None,
        voice_style: str | None = None,
        voice_desc: str | None = None,
        fmt: str | None = None,
        model: str | None = None,
    ) -> tuple[bytes, str]:
        """文字转语音（非流式）。返回 ``(audio_bytes, mime_type)``。"""
        text = (text or "").strip()
        if not text:
            raise ValueError("空文本。")
        fmt = (fmt or settings.mimo_tts_format).lower()
        payload = self._tts_payload(
            text,
            voice=voice,
            voice_style=voice_style,
            voice_desc=voice_desc,
            fmt=fmt,
            model=model,
            stream=False,
        )
        client = self._ensure()
        resp = await client.post(self._url, json=payload, headers=self._headers())
        if resp.status_code >= 400:
            raise RuntimeError(f"MiMo TTS {resp.status_code}: {resp.text[:500]}")
        b64 = _extract_audio_b64(resp.json())
        return base64.b64decode(b64), _audio_mime(fmt)

    async def synthesize_stream(
        self,
        text: str,
        *,
        voice: str | None = None,
        voice_style: str | None = None,
        voice_desc: str | None = None,
        fmt: str | None = None,
        model: str | None = None,
    ) -> AsyncIterator[bytes]:
        """文字转语音（流式）。逐块 yield 原始音频字节。

        文档建议流式用 ``pcm16`` 便于拼接；前端若直接播放可用 mp3 分段。
        """
        text = (text or "").strip()
        if not text:
            return
        fmt = (fmt or settings.mimo_tts_format).lower()
        payload = self._tts_payload(
            text,
            voice=voice,
            voice_style=voice_style,
            voice_desc=voice_desc,
            fmt=fmt,
            model=model,
            stream=True,
        )
        client = self._ensure()
        async with client.stream("POST", self._url, json=payload, headers=self._headers()) as resp:
            if resp.status_code >= 400:
                body = (await resp.aread()).decode("utf-8", "replace")
                raise RuntimeError(f"MiMo TTS {resp.status_code}: {body[:500]}")
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data_str = line[len("data:"):].strip()
                if not data_str or data_str == "[DONE]":
                    continue
                try:
                    evt = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                chunk_b64 = _extract_audio_delta(evt)
                if chunk_b64:
                    yield base64.b64decode(chunk_b64)


# --- 响应解析（对返回结构做防御性提取，字段缺失时尽量降级而非抛错） --------

def _extract_text(data: dict) -> str:
    choices = data.get("choices") or []
    if not choices:
        return ""
    msg = choices[0].get("message") or {}
    content = msg.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):  # 兼容 content 为 block 数组
        parts = [b.get("text", "") for b in content if isinstance(b, dict)]
        return "".join(parts).strip()
    return ""


def _extract_audio_b64(data: dict) -> str:
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("MiMo TTS 未返回音频。")
    audio = (choices[0].get("message") or {}).get("audio") or {}
    b64 = audio.get("data")
    if not b64:
        raise RuntimeError("MiMo TTS 响应缺少 audio.data。")
    return b64


def _extract_audio_delta(evt: dict) -> str | None:
    choices = evt.get("choices") or []
    if not choices:
        return None
    delta = choices[0].get("delta") or {}
    audio = delta.get("audio")
    if isinstance(audio, dict):
        return audio.get("data")
    if isinstance(audio, str):
        return audio
    return None


def _audio_mime(fmt: str) -> str:
    return {
        "mp3": "audio/mpeg",
        "wav": "audio/wav",
        "pcm16": "audio/pcm",
    }.get(fmt.lower(), "application/octet-stream")


mimo_audio = MiMoAudioClient()
