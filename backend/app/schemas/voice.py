"""语音对话 (ASR/TTS) 的请求/响应 schema。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ASRResult(BaseModel):
    text: str


class TTSIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    voice: str | None = None
    voice_style: str | None = Field(default=None, description="内置音色的朗读风格指令")
    voice_desc: str | None = Field(default=None, description="古风音色描述；非空则走声音设计模型")
    format: str | None = Field(default=None, description="mp3 | wav | pcm16")


class LivetalkingTalkIn(TTSIn):
    sessionid: str = Field(..., min_length=1, description="LiveTalking WebRTC 会话 ID")


class VoiceListOut(BaseModel):
    voices: list[str]
    default: str
