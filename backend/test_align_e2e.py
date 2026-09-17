import asyncio
import io
import sys

from faster_whisper import WhisperModel

from app.core.config import settings
from app.services.mimo_audio import mimo_audio
from app.services.phoneme_align import aligner

MODEL_DIR = "models/faster-whisper-small"


async def main() -> None:
    text = "问渠那得清如许，为有源头活水来。读书之法，在循序而渐进，熟读而精思。"
    print("synthesizing...")
    audio_bytes, mime = await mimo_audio.synthesize(text, fmt="wav")
    print("audio bytes:", len(audio_bytes), "mime:", mime)

    print("aligning...")
    timeline = aligner.align(audio_bytes, text)
    print("--- viseme timeline ---")
    for item in timeline:
        print(f"{item['start']:.2f}-{item['end']:.2f} -> {item['visemes']}")

    await mimo_audio.aclose()


if __name__ == "__main__":
    asyncio.run(main())
