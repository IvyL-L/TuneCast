"""Генерирует иконку приложения и логотип для README.

    python tools/make_assets.py

Нужен Pillow (ставится в build.bat).
"""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
GREEN = (30, 215, 96)
DARK = (18, 18, 18)


def vinyl(size: int) -> Image.Image:
    s = size * 4  # рисуем крупно и уменьшаем — так края гладкие
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = s / 2
    r = s * 0.48
    d.ellipse((c - r, c - r, c + r, c + r), fill=DARK)
    for k in (0.86, 0.74, 0.62):
        rr = r * k
        d.ellipse((c - rr, c - rr, c + rr, c + rr), outline=(255, 255, 255, 34), width=max(2, s // 160))
    d.arc((c - r * 0.8, c - r * 0.8, c + r * 0.8, c + r * 0.8), 200, 245, fill=(255, 255, 255, 110), width=s // 40)
    d.arc((c - r * 0.8, c - r * 0.8, c + r * 0.8, c + r * 0.8), 20, 65, fill=(255, 255, 255, 110), width=s // 40)
    lr = r * 0.36
    d.ellipse((c - lr, c - lr, c + lr, c + lr), fill=GREEN)
    # «Play» на этикетке
    t = lr * 0.55
    d.polygon([(c - t * 0.45, c - t * 0.6), (c - t * 0.45, c + t * 0.6), (c + t * 0.6, c)], fill=DARK)
    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    assets = ROOT / "assets"
    assets.mkdir(exist_ok=True)
    vinyl(256).save(assets / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    vinyl(512).save(assets / "logo.png")
    print("Готово: assets/icon.ico, assets/logo.png")


if __name__ == "__main__":
    main()
