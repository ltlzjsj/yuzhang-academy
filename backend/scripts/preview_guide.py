import cv2
import numpy as np

BASE = r"D:\workplace\GeoRag\书院文化图片\历史名人立绘"
OUT = r"D:\workplace\GeoRag\backend\scripts\_guide_preview.png"


def comp(png, bg):
    h, w = png.shape[:2]
    bgr = png[:, :, :3].astype(np.float32)
    a = png[:, :, 3:4].astype(np.float32) / 255.0
    return (bgr * a + np.full((h, w, 3), bg, np.float32) * (1 - a)).astype(np.uint8)


def load(name):
    return cv2.imdecode(np.fromfile(BASE + "\\" + name, np.uint8), cv2.IMREAD_UNCHANGED)


full = load("guide.png")
face = load("guide_face.png")
fig_navy = comp(full, (58, 62, 44))
# 把头像缩放到与立绘同高并放在右侧（圆形裁剪示意：直接方图）
fh = full.shape[0]
fc = comp(face, (243, 245, 244))
fc = cv2.resize(fc, (fh, fh))
combo = np.hstack([comp(full, (243, 245, 244)), np.full((fh, 14, 3), 0, np.uint8), fig_navy,
                   np.full((fh, 14, 3), 0, np.uint8), fc])
ok, buf = cv2.imencode(".png", combo)
buf.tofile(OUT)
print("wrote", OUT, combo.shape[1], combo.shape[0])
