"""王阳明/江万里「画像开口说话」视频服务。

本地复用参考项目中的 Wav2Lip 模型：输入一张古人半身像和 MiMo TTS 音频，
输出带音频的 MP4。嘴巴由 Wav2Lip 生成，身体层增加很轻的呼吸/点头/轻微侧身，
避免只有嘴巴在动的僵硬感。

注：MuseTalk / EchoMimic 可后续作为同一接口的 ``engine`` 扩展；当前引擎为
``wav2lip``，先把参考项目直接接入主站。
"""
from __future__ import annotations

import io
import os
import sys
import threading
from pathlib import Path

import av
import cv2
import numpy as np

REFERENCE_ROOT = Path(r"C:\Users\43486\Documents\Codex\2026-09-04\mo\work\wangyangming-avatar")
WAV2LIP_CODE = REFERENCE_ROOT / "wav2lip_code"
CHECKPOINT = WAV2LIP_CODE / "checkpoints" / "wav2lip_gan.pth"

if str(WAV2LIP_CODE) not in sys.path:
    sys.path.insert(0, str(WAV2LIP_CODE))

import audio as wav2lip_audio  # noqa: E402
import face_detection  # noqa: E402
from models import Wav2Lip  # noqa: E402

IMG_SIZE = 96
MEL_STEP_SIZE = 16
DEVICE = "cuda" if __import__("torch").cuda.is_available() else "cpu"

_model = None
_detector = None
_init_lock = threading.Lock()


def init() -> None:
    global _model, _detector
    if _model is not None and _detector is not None:
        return
    with _init_lock:
        if _model is not None and _detector is not None:
            return
        model = Wav2Lip()
        ckpt = __import__("torch").load(CHECKPOINT, map_location="cpu")
        state = ckpt["state_dict"]
        state = {k.replace("module.", ""): v for k, v in state.items()}
        model.load_state_dict(state)
        _model = model.to(DEVICE).eval()
        _detector = face_detection.FaceAlignment(
            face_detection.LandmarksType._2D,
            flip_input=False,
            device=DEVICE,
        )


def decode_audio(data: bytes, sample_rate: int = 16000) -> np.ndarray:
    container = av.open(io.BytesIO(data))
    astream = container.streams.audio[0]
    resampler = av.AudioResampler(format="fltp", layout="mono", rate=sample_rate)
    chunks: list[np.ndarray] = []
    for frame in container.decode(astream):
        for rf in resampler.resample(frame):
            chunks.append(rf.to_ndarray())
    container.close()
    if not chunks:
        raise ValueError("音频解码失败")
    return np.concatenate(chunks, axis=1).reshape(-1).astype(np.float32)


def build_mel_chunks(wav: np.ndarray, fps: int = 25) -> list[np.ndarray]:
    mel = wav2lip_audio.melspectrogram(wav)
    if np.isnan(mel).sum() > 0:
        raise ValueError("mel 频谱包含 NaN")
    chunks: list[np.ndarray] = []
    mul = 80.0 / fps
    i = 0
    while True:
        s = int(i * mul)
        if s + MEL_STEP_SIZE > mel.shape[1]:
            chunks.append(mel[:, mel.shape[1] - MEL_STEP_SIZE:])
            break
        chunks.append(mel[:, s:s + MEL_STEP_SIZE])
        i += 1
    return chunks


def detect_face(frame: np.ndarray) -> tuple[int, int, int, int]:
    rect = _detector.get_detections_for_batch(np.array([frame]))[0]
    if rect is None:
        raise ValueError("未检测到人脸")
    x1, y1, x2, y2 = [int(v) for v in rect]
    y1 = max(0, y1)
    y2 = min(frame.shape[0], y2 + 10)
    x1 = max(0, x1)
    x2 = min(frame.shape[1], x2)
    return x1, y1, x2, y2


def _warp_with_alpha(
    frame: np.ndarray,
    alpha: np.ndarray,
    matrix: np.ndarray,
    size: tuple[int, int],
) -> tuple[np.ndarray, np.ndarray]:
    """对人物帧和透明通道同时做同一仿射变换。"""
    frame = cv2.warpAffine(frame, matrix, size, borderMode=cv2.BORDER_REFLECT)
    alpha = cv2.warpAffine(
        alpha, matrix, size, borderMode=cv2.BORDER_CONSTANT, borderValue=0
    )
    return frame, alpha


def _apply_lecture_motion(
    frame: np.ndarray,
    alpha: np.ndarray,
    index: int,
    fps: int,
) -> tuple[np.ndarray, np.ndarray]:
    """只保留自然讲学动作：轻微点头 + 呼吸起伏，不再加入手部变形。"""
    t = index / max(fps, 1)
    h, w = frame.shape[:2]

    # 1. 头部轻微点头，动作幅度克制。
    face_cx, face_cy = w * 0.595, h * 0.155
    nod_angle = 0.35 * np.sin(2 * np.pi * t * 0.24)
    nod_dy = 1.6 * np.sin(2 * np.pi * t * 0.24 + np.pi * 0.45)
    nod = cv2.getRotationMatrix2D((face_cx, face_cy), nod_angle, 1.0)
    nod[1, 2] += nod_dy
    frame, alpha = _warp_with_alpha(frame, alpha, nod, (w, h))

    # 2. 身体呼吸：以人物躯干为锚点做很轻的纵向起伏。
    breath_scale = 1.0 + 0.004 * np.sin(2 * np.pi * t * 0.22)
    breath_dy = 1.1 * np.sin(2 * np.pi * t * 0.22)
    breath = cv2.getRotationMatrix2D(
        (w * 0.5, h * 0.55), 0.0, breath_scale
    )
    breath[1, 2] += breath_dy
    frame, alpha = _warp_with_alpha(frame, alpha, breath, (w, h))

    return frame, alpha


def _write_mp4(
    frames: list[np.ndarray],
    wav: np.ndarray,
    out_path: str,
    fps: int,
) -> None:
    if not frames:
        raise ValueError("没有可写入的视频帧")
    h, w = frames[0].shape[:2]
    ew, eh = w - (w % 2), h - (h % 2)
    if (ew, eh) != (w, h):
        frames = [cv2.resize(f, (ew, eh)) for f in frames]

    container = av.open(out_path, mode="w")
    vstream = container.add_stream("libx264", rate=int(fps))
    vstream.width = ew
    vstream.height = eh
    vstream.pix_fmt = "yuv420p"
    vstream.options = {"preset": "veryfast", "crf": "23"}

    for frame in frames:
        vf = av.VideoFrame.from_ndarray(frame, format="bgr24")
        for packet in vstream.encode(vf):
            container.mux(packet)
    for packet in vstream.encode():
        container.mux(packet)

    try:
        astream = container.add_stream("aac", rate=16000)
        astream.layout = "mono"
        astream.format = "fltp"
        aframe = av.AudioFrame.from_ndarray(
            wav.reshape(1, -1),
            format="fltp",
            layout="mono",
        )
        aframe.sample_rate = 16000
        aframe.pts = 0
        for packet in astream.encode(aframe):
            container.mux(packet)
        for packet in astream.encode():
            container.mux(packet)
    except Exception:
        # 视频仍可播放，只是没有音轨；由上层决定是否报错。
        pass

    container.close()


def generate_talking_video(
    image_path: str,
    audio_bytes: bytes,
    out_path: str,
    *,
    fps: int = 25,
    body_motion: bool = True,
) -> int:
    init()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    frame = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError(f"形象图片读取失败：{image_path}")

    wav = decode_audio(audio_bytes)
    mels = build_mel_chunks(wav, fps)
    x1, y1, x2, y2 = detect_face(frame)
    face = cv2.resize(frame[y1:y2, x1:x2], (IMG_SIZE, IMG_SIZE))

    import torch

    frames_out: list[np.ndarray] = []
    batch_size = 128
    for b in range(0, len(mels), batch_size):
        mel_batch = np.asarray(mels[b:b + batch_size])
        batch_count = mel_batch.shape[0]
        img_batch = np.tile(face, (batch_count, 1, 1, 1))
        img_masked = img_batch.copy()
        img_masked[:, IMG_SIZE // 2:] = 0
        img_input = np.concatenate((img_masked, img_batch), axis=3) / 255.0
        mel_input = mel_batch[..., None]

        img_t = torch.FloatTensor(np.transpose(img_input, (0, 3, 1, 2))).to(DEVICE)
        mel_t = torch.FloatTensor(np.transpose(mel_input, (0, 3, 1, 2))).to(DEVICE)

        with torch.no_grad():
            pred = _model(mel_t, img_t)
        pred = pred.cpu().numpy().transpose(0, 2, 3, 1) * 255.0

        for local_idx, p in enumerate(pred):
            p = cv2.resize(p.astype(np.uint8), (x2 - x1, y2 - y1))
            f = frame.copy()
            f[y1:y2, x1:x2] = p
            global_idx = b + local_idx
            if body_motion:
                f, _ = _apply_lecture_motion(
                    f, np.full(f.shape[:2], 255, dtype=np.uint8), global_idx, fps
                )
            frames_out.append(f)

    _write_mp4(frames_out, wav, out_path, fps)
    return len(frames_out)
