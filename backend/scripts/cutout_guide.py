"""Cut out full-body guide/figure portraits in the academy portrait folder.

Default usage from ``backend``:

    python -m scripts.cutout_guide

The script scans ``书院文化图片/历史名人立绘`` for ``<id>.png`` files, skips
``*_src.png`` and ``*_face.png``, writes the transparent full-body portrait back
to ``<id>.png``, and exports a square chat avatar as ``<id>_face.png``.

If the input already has useful alpha, the alpha is preserved. Otherwise, a
bright neutral background connected to the image border is removed. On first
run, the original image is copied to ``<id>_src.png`` so the operation can be
repeated without degrading the user's source image.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DIR = ROOT / "书院文化图片" / "历史名人立绘"
TARGET_H = 1100


def imread(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"Cannot read image: {path}")
    return img


def imwrite_png(path: Path, img: np.ndarray) -> None:
    ok, buf = cv2.imencode(".png", img, [cv2.IMWRITE_PNG_COMPRESSION, 9])
    if not ok:
        raise ValueError(f"Cannot encode png: {path}")
    buf.tofile(str(path))


def to_bgra(img: np.ndarray) -> np.ndarray:
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
    if img.shape[2] == 4:
        return img
    if img.shape[2] == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    raise ValueError(f"Unsupported image shape: {img.shape}")


def cutout_white_border_background(img: np.ndarray) -> np.ndarray:
    """Remove bright neutral pixels that connect to the image border."""
    bgr = to_bgra(img)[:, :, :3]
    mn = bgr.min(2).astype(np.int16)
    mx = bgr.max(2).astype(np.int16)

    # White studio backgrounds are bright and low-saturation. Some AI exports
    # bake a checkerboard into the RGB pixels instead of real alpha; those
    # squares are also low-saturation, just darker. We only remove components
    # connected to the image border, so enclosed white clothing stays intact.
    neutral = (((mn > 185) & ((mx - mn) < 18)) | ((mx > 145) & ((mx - mn) < 24))).astype(np.uint8)
    num, labels = cv2.connectedComponents(neutral)
    if num <= 1:
        alpha = np.full(bgr.shape[:2], 255, dtype=np.uint8)
    else:
        border_labels = set(labels[0, :])
        border_labels.update(labels[-1, :])
        border_labels.update(labels[:, 0])
        border_labels.update(labels[:, -1])
        border_labels.discard(0)
        bg = np.isin(labels, list(border_labels))
        alpha = np.where(bg, 0, 255).astype(np.uint8)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    alpha = cv2.erode(alpha, kernel, iterations=1)
    alpha = cv2.GaussianBlur(alpha, (3, 3), 0)
    b, g, r = cv2.split(bgr)
    return cv2.merge([b, g, r, alpha])


def normalize_alpha(img: np.ndarray) -> np.ndarray:
    bgra = to_bgra(img)
    alpha = bgra[:, :, 3]
    transparent_ratio = float((alpha < 245).mean())
    bgr = bgra[:, :, :3]
    h, w = bgr.shape[:2]
    corner = np.concatenate(
        [
            bgr[: max(1, h // 12), : max(1, w // 12)].reshape(-1, 3),
            bgr[: max(1, h // 12), -max(1, w // 12) :].reshape(-1, 3),
            bgr[-max(1, h // 12) :, : max(1, w // 12)].reshape(-1, 3),
            bgr[-max(1, h // 12) :, -max(1, w // 12) :].reshape(-1, 3),
        ]
    )
    corner_mn = corner.min(1).astype(np.int16)
    corner_mx = corner.max(1).astype(np.int16)
    baked_checker_ratio = float(((corner_mx > 145) & ((corner_mx - corner_mn) < 24)).mean())

    if transparent_ratio > 0.01 and baked_checker_ratio < 0.35:
        return bgra
    return cutout_white_border_background(bgra)


def resize_if_needed(img: np.ndarray, target_h: int) -> np.ndarray:
    h, w = img.shape[:2]
    if h <= target_h:
        return img
    scale = target_h / h
    return cv2.resize(img, (round(w * scale), target_h), interpolation=cv2.INTER_AREA)


def export_face(path: Path, rgba: np.ndarray) -> tuple[int, int]:
    alpha = rgba[:, :, 3]
    ys, xs = np.where(alpha > 40)
    if len(xs) == 0 or len(ys) == 0:
        face = rgba
    else:
        y0, y1 = int(ys.min()), int(ys.max())
        x0, x1 = int(xs.min()), int(xs.max())
        figure_w = max(1, x1 - x0)
        figure_h = max(1, y1 - y0)
        side = int(max(96, min(figure_w * 0.72, figure_h * 0.38)))

        top_band = alpha[y0 : y0 + max(1, int(figure_h * 0.18)), x0:x1]
        band_xs = np.where(top_band > 40)[1]
        cx = int(x0 + band_xs.mean()) if len(band_xs) else (x0 + x1) // 2
        cy = int(y0 + side * 0.62)
        half = side // 2
        x_start, x_end = max(cx - half, 0), min(cx + half, rgba.shape[1])
        y_start, y_end = max(cy - half, 0), min(cy + half, rgba.shape[0])
        face = rgba[y_start:y_end, x_start:x_end]

    face_path = path.with_name(f"{path.stem}_face.png")
    imwrite_png(face_path, face)
    return face.shape[1], face.shape[0]


def process_one(path: Path, target_h: int, force_backup: bool = False) -> None:
    backup = path.with_name(f"{path.stem}_src.png")
    if force_backup or not backup.exists():
        shutil.copyfile(path, backup)

    img = imread(backup)
    rgba = resize_if_needed(normalize_alpha(img), target_h)
    imwrite_png(path, rgba)
    face_w, face_h = export_face(path, rgba)

    alpha = rgba[:, :, 3]
    print(
        f"{path.name}: full={rgba.shape[1]}x{rgba.shape[0]}, "
        f"transparent={(alpha < 128).mean() * 100:.1f}%, "
        f"face={face_w}x{face_h}"
    )


def collect_targets(folder: Path, ids: list[str] | None) -> list[Path]:
    if ids:
        return [folder / f"{figure_id}.png" for figure_id in ids]
    return sorted(
        p
        for p in folder.glob("*.png")
        if not p.stem.endswith("_src") and not p.stem.endswith("_face")
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR, help="portrait folder")
    parser.add_argument("--ids", nargs="*", help="figure ids without .png, e.g. zhuxi wangyangming")
    parser.add_argument("--height", type=int, default=TARGET_H, help="max output height")
    parser.add_argument("--force-backup", action="store_true", help="overwrite <id>_src.png from current image")
    args = parser.parse_args()

    folder = args.dir
    if not folder.exists():
        raise FileNotFoundError(folder)

    targets = collect_targets(folder, args.ids)
    if not targets:
        print(f"No png portraits found in {folder}")
        return

    for target in targets:
        if not target.exists():
            print(f"skip missing: {target}")
            continue
        process_one(target, args.height, args.force_backup)


if __name__ == "__main__":
    main()
