"""音素对齐服务：把 MiMo TTS 生成的音频，用 faster-whisper 对齐出字级时间戳，
再通过拼音韵母映射到 ARKit 口型 blendshape，输出 viseme 时间轴。

设计说明：
- 保留 MiMo TTS（只负责合成音频），对齐用本地 faster-whisper small 模型（GPU）。
- 中文口型主要看韵母，因此用 pypinyin 提取韵母，映射到口型 morph 权重。
- 模型懒加载并复用，避免每次请求重新加载（首次加载约数秒）。
"""
from __future__ import annotations

import io
from typing import Any

from faster_whisper import WhisperModel
from pypinyin import Style, pinyin

from app.core.config import settings

MODEL_DIR = settings.faster_whisper_model_dir
MODEL_DEVICE = settings.faster_whisper_device
MODEL_COMPUTE = settings.faster_whisper_compute_type

_VISEME_BY_VOWEL: dict[str, dict[str, float]] = {
    "a": {"jawOpen": 0.45, "mouthSmileLeft": 0.12, "mouthSmileRight": 0.12},
    "o": {"mouthFunnel": 0.5, "jawOpen": 0.18},
    "e": {"mouthStretchLeft": 0.36, "mouthStretchRight": 0.36, "jawOpen": 0.1},
    "i": {"mouthSmileLeft": 0.32, "mouthSmileRight": 0.32, "jawOpen": 0.08},
    "u": {"mouthPucker": 0.5, "jawOpen": 0.08},
    "v": {"mouthPucker": 0.45, "jawOpen": 0.1},
    "ü": {"mouthPucker": 0.45, "jawOpen": 0.1},
}

_CLOSE_INITIALS = ("b", "p", "m")


def _vowel_of_final(final: str) -> str:
    for v in ("a", "o", "e", "i", "u", "ü", "v"):
        if v in final:
            return v
    return "a"


def final_to_viseme(final: str) -> dict[str, float]:
    v = _vowel_of_final(final)
    base = _VISEME_BY_VOWEL.get(v, _VISEME_BY_VOWEL["a"])
    out: dict[str, float] = dict(base)
    if final.endswith(("n", "ng")):
        out["mouthClose"] = out.get("mouthClose", 0.0) + 0.12
    return out


def text_to_viseme_frames(text: str) -> list[dict[str, float]]:
    frames: list[dict[str, float]] = []
    for ch in text:
        finals = pinyin(ch, style=Style.FINALS)
        final = (finals[0][0] if finals and finals[0] else "").strip() or "a"
        frames.append(final_to_viseme(final))
    return frames


class PhonemeAligner:
    _model: WhisperModel | None = None

    def _ensure_model(self) -> WhisperModel:
        if self._model is None:
            self._model = WhisperModel(
                MODEL_DIR,
                device=MODEL_DEVICE,
                compute_type=MODEL_COMPUTE,
            )
        return self._model

    def align(self, audio_bytes: bytes, text: str) -> list[dict[str, Any]]:
        model = self._ensure_model()
        segments, _info = model.transcribe(
            io.BytesIO(audio_bytes),
            language="zh",
            word_timestamps=True,
            initial_prompt=text,
            vad_filter=True,
        )

        # 只取 whisper 的时间戳（它识别的字可能出错，不用它的文本做拼音）
        words: list[tuple[float, float]] = []
        for seg in segments:
            for w in seg.words or []:
                words.append((w.start, w.end))

        if not words:
            return []

        # 用原文字符（去掉标点/空白）按顺序对应时间戳，拼音一定正确
        chars = [ch for ch in text if ch.strip() and ("\u4e00" <= ch <= "\u9fff" or ch.isalnum())]

        timeline: list[dict[str, Any]] = []
        n = min(len(words), len(chars))
        for i in range(n):
            start, end = words[i]
            ch = chars[i]
            finals = pinyin(ch, style=Style.FINALS)
            final = "a"
            if finals and finals[0] and finals[0][0]:
                final = finals[0][0].strip() or "a"
            visemes = final_to_viseme(final)
            timeline.append({"start": round(start, 3), "end": round(end, 3), "visemes": visemes})
        return timeline


aligner = PhonemeAligner()
