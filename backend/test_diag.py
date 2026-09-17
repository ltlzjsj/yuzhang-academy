import asyncio

from app.services.mimo_audio import mimo_audio
from app.services.phoneme_align import aligner


async def main() -> None:
    text = "问渠那得清如许，为有源头活水来。读书之法，在循序而渐进，熟读而精思。"
    print("原文:", text)
    audio_bytes, _ = await mimo_audio.synthesize(text, fmt="wav")

    timeline = aligner.align(audio_bytes, text)
    print("--- 对齐结果（原文拼音 + whisper 时间戳）---")
    for item in timeline:
        print(f"{item['start']:.2f}-{item['end']:.2f} -> {item['visemes']}")
    await mimo_audio.aclose()


if __name__ == "__main__":
    asyncio.run(main())
