"""收紧数字人的人脸框（LiveTalking wav2lip 用），按新框重裁 face_imgs 并更新 coords.pkl。

为什么需要：genavatar 检出的人脸框往往会带上头顶的帽子/头饰，以及下巴以下过长的胡须，
真正的脸只占框中间一小段。裁到 256x256 时嘴部有效像素被稀释，模型重绘的嘴部更糊。
收紧后（去掉上部头饰、下部多余胡须）：
  - 嘴部在模型输入里的占比提升，重绘的嘴部更清晰
  - 宽高比更接近 1，减少各向异性拉伸
  - 被重绘的区域变小，模型"改坏"的毛发面积也变小

用法（在 LiveTalking 同级目录执行）：
    python retighten_face_box.py <avatar_id> [--top 0.20] [--bottom 0.92] [--live-root D:\\path\\LiveTalking]

说明：原 face_imgs / coords.pkl 会备份到 <avatar>/_backup_before_tighten，可随时回滚
（把备份里的 face_imgs 与 coords.pkl 复制回去即可）。改完需重启 LiveTalking 生效。
"""

from __future__ import annotations

import argparse
import pickle
import shutil
from pathlib import Path

import cv2


def main() -> None:
    parser = argparse.ArgumentParser(description="收紧 wav2lip 人脸框")
    parser.add_argument("avatar_id", help="例如 zhuxi_lt")
    parser.add_argument("--top", type=float, default=0.20, help="框顶部去掉的比例（默认 0.20）")
    parser.add_argument("--bottom", type=float, default=0.92, help="框底部保留到的比例（默认 0.92）")
    parser.add_argument("--img-size", type=int, default=256, help="face_imgs 边长（wav2lip_v2 必须 256）")
    parser.add_argument(
        "--live-root",
        default=r"D:\Desktop\shuyuan\LiveTalking",
        help="LiveTalking 目录（默认取本机路径）",
    )
    args = parser.parse_args()

    avatar = Path(args.live_root) / "data" / "avatars" / args.avatar_id
    if not (avatar / "coords.pkl").exists():
        raise SystemExit(f"找不到 {avatar/'coords.pkl'}")

    coords_path = avatar / "coords.pkl"
    boxes = pickle.load(open(coords_path, "rb"))

    backup = avatar / "_backup_before_tighten"
    if not backup.exists():
        backup.mkdir()
        shutil.copy2(coords_path, backup / "coords.pkl")
        shutil.copytree(avatar / "face_imgs", backup / "face_imgs")
        print(f"已备份原 face_imgs / coords.pkl -> {backup}")
    else:
        print(f"备份已存在，保留不变：{backup}")

    new_boxes = []
    for idx, (y1, y2, x1, x2) in enumerate(boxes):
        h = y2 - y1
        ny1 = int(round(y1 + h * args.top))
        ny2 = int(round(y1 + h * args.bottom))
        new_boxes.append((ny1, ny2, x1, x2))

        frame = cv2.imread(str(avatar / "full_imgs" / f"{idx:08d}.png"))
        if frame is None:
            raise SystemExit(f"读不到 full_imgs/{idx:08d}.png")
        face = cv2.resize(frame[ny1:ny2, x1:x2], (args.img_size, args.img_size))
        if not cv2.imwrite(str(avatar / "face_imgs" / f"{idx:08d}.png"), face):
            raise SystemExit(f"写 face_imgs/{idx:08d}.png 失败")

    with open(coords_path, "wb") as fh:
        pickle.dump(new_boxes, fh)

    h0, w0 = new_boxes[0][1] - new_boxes[0][0], new_boxes[0][3] - new_boxes[0][2]
    print(f"完成：{len(new_boxes)} 帧，新框 {w0}x{h0}（宽高比 {w0 / h0:.2f}）")
    print("重启 LiveTalking 后生效。")


if __name__ == "__main__":
    main()
