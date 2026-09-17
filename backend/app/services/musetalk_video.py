"""Run MuseTalk to lip-sync the 江万里 digital-human video to answer audio."""
from __future__ import annotations

import subprocess
import uuid
from pathlib import Path

MUSETALK_ROOT = Path(r"D:\Desktop\shuyuan\MuseTalk")
MUSETALK_PYTHON = r"D:\Anaconda\envs\echomimic\python.exe"
FFMPEG_DIR = MUSETALK_ROOT / "ffmpeg"
FFMPEG = FFMPEG_DIR / "ffmpeg.exe"
SOURCE_VIDEO = Path(r"D:\Desktop\shuyuan\数字人\江万里.mp4")


def generate_lip_sync_video(
    audio_path: str | Path,
    out_dir: Path,
) -> Path:
    """Run MuseTalk inference and return the generated mp4 path."""
    out_dir = Path(out_dir).resolve()
    audio_path = Path(audio_path).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex[:12]

    # Avoid Chinese paths in the ffmpeg ``os.system`` calls inside MuseTalk.
    # 同时把源视频按音频长度循环扩展成纯正向视频，避免 MuseTalk 在音频较长时
    # 使用“正放 + 倒放”补齐帧，导致人物像倒着播、不像数字人。
    source_copy = out_dir / f"src_{token}.mp4"
    loop_cmd = [
        str(FFMPEG),
        "-y",
        "-stream_loop", "-1",
        "-i", str(SOURCE_VIDEO),
        "-i", str(audio_path),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-pix_fmt", "yuv420p",
        "-shortest",
        str(source_copy),
    ]
    loop_proc = subprocess.run(loop_cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if loop_proc.returncode != 0:
        tail = (loop_proc.stdout or "")[-1200:] + "\n" + (loop_proc.stderr or "")[-1200:]
        raise RuntimeError(f"循环扩展源视频失败：{tail}")

    cfg = out_dir / f"cfg_{token}.yaml"
    cfg.write_text(
        "task_0:\n"
        f"  video_path: \"{source_copy.as_posix()}\"\n"
        f"  audio_path: \"{audio_path.as_posix()}\"\n"
        f"  result_name: \"{token}.mp4\"\n",
        encoding="utf-8",
    )

    result_dir = out_dir / "musetalk"
    cmd = [
        MUSETALK_PYTHON,
        "-m",
        "scripts.inference",
        "--inference_config",
        str(cfg),
        "--result_dir",
        str(result_dir),
        "--unet_model_path",
        "models/musetalk/pytorch_model.bin",
        "--unet_config",
        "models/musetalk/musetalk.json",
        "--version",
        "v1",
        "--ffmpeg_path",
        str(FFMPEG_DIR),
        "--use_float16",
    ]

    proc = subprocess.run(
        cmd,
        cwd=str(MUSETALK_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        tail = (proc.stdout or "")[-2000:] + "\n" + (proc.stderr or "")[-2000:]
        raise RuntimeError(f"MuseTalk 推理失败：{tail}")

    out = result_dir / "v1" / f"{token}.mp4"
    if not out.exists():
        raise RuntimeError(f"MuseTalk 未生成输出：{out}")
    return out
