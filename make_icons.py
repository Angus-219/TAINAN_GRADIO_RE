"""產生 PWA 圖示（需要 pillow：pip install pillow）
用法：python make_icons.py
輸出：static/icons/ 底下的 4 個 PNG
"""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent / "static" / "icons"
OUT.mkdir(parents=True, exist_ok=True)


def make(size: int, path: Path, maskable: bool = False) -> None:
    S = size * 4  # 超取樣，縮小後邊緣較平滑
    img = Image.new("RGB", (S, S), "#4f46e5")
    d = ImageDraw.Draw(img)

    # 垂直漸層背景
    for y in range(S):
        t = y / S
        c = (
            int(79 + (14 - 79) * t * 0.6),
            int(70 + (165 - 70) * t * 0.6),
            int(229 + (233 - 229) * t * 0.6),
        )
        d.line([(0, y), (S, y)], fill=c)

    # maskable 圖示需保留安全區，圖案縮小一點
    scale = 0.62 if maskable else 0.78
    box = S * scale
    off = (S - box) / 2

    # 長條圖圖案
    bw, gap = box * 0.18, box * 0.09
    heights = [0.45, 0.75, 0.6, 1.0]
    total = bw * 4 + gap * 3
    x0 = off + (box - total) / 2
    base = off + box * 0.92
    for i, h in enumerate(heights):
        x = x0 + i * (bw + gap)
        top = base - box * 0.78 * h
        d.rounded_rectangle([x, top, x + bw, base], radius=bw * 0.22, fill="white")
    d.rounded_rectangle(
        [off + box * 0.06, base + box * 0.03, off + box * 0.94, base + box * 0.07],
        radius=box * 0.02,
        fill="white",
    )

    # 一般圖示加圓角；maskable / apple-touch 用滿版方形
    if not maskable:
        mask = Image.new("L", (S, S), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, S, S], radius=int(S * 0.22), fill=255)
        bg = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        bg.paste(img, (0, 0), mask)
        img = bg

    img.resize((size, size), Image.LANCZOS).save(path)


if __name__ == "__main__":
    make(192, OUT / "icon-192.png")
    make(512, OUT / "icon-512.png")
    make(512, OUT / "icon-maskable-512.png", maskable=True)
    make(180, OUT / "apple-touch-icon.png", maskable=True)  # iOS 會自行套用圓角
    print("圖示已產生：", OUT)
