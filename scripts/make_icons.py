"""Draw the app icon once and export every size the web app (PWA) and the desktop installers need.

    python scripts/make_icons.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
S = 1024


def draw(maskable: bool = False) -> Image.Image:
    k = 4                                                             # supersample for smooth edges
    im = Image.new("RGBA", (S * k, S * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    pad = 0 if maskable else int(S * 0.06 * k)
    r = 0 if maskable else int(S * 0.22 * k)
    box = (pad, pad, S * k - pad, S * k - pad)
    d.rounded_rectangle(box, r, fill="#f26a1f") if r else d.rectangle(box, fill="#f26a1f")
    inner = 0.8 if maskable else 1.0                                  # maskable icons keep the artwork inside the safe zone
    cx, cy = S * k / 2, S * k * 0.44
    u = S * k * 0.26 * inner
    d.polygon([(cx - u * 0.55, cy - u), (cx - u * 0.55, cy + u), (cx + u * 1.05, cy)], fill="#ffffff")     # play
    bw, bh = S * k * 0.46 * inner, S * k * 0.075 * inner
    by = S * k * 0.76 if not maskable else S * k * 0.74
    d.rounded_rectangle((S * k / 2 - bw / 2, by, S * k / 2 + bw / 2, by + bh), bh / 2, fill="#ffc83a")       # caption bar
    return im.resize((S, S), Image.LANCZOS)


def main() -> None:
    pub, build = ROOT / "studio" / "public", ROOT / "desktop" / "build"
    pub.mkdir(parents=True, exist_ok=True)
    build.mkdir(parents=True, exist_ok=True)
    a, m = draw(), draw(True)
    for size in (192, 512):
        a.resize((size, size), Image.LANCZOS).save(pub / f"icon-{size}.png")
    m.resize((512, 512), Image.LANCZOS).save(pub / "icon-maskable-512.png")
    a.resize((180, 180), Image.LANCZOS).save(pub / "apple-touch-icon.png")
    a.save(build / "icon.png")
    a.save(build / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    (pub / "favicon.svg").write_text(
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='8' fill='#f26a1f'/>"
        "<path d='M12 8l11 7-11 7z' fill='white'/><rect x='9' y='24' width='14' height='2.4' rx='1.2' fill='#ffc83a'/></svg>", encoding="utf-8")
    print("icons written")


if __name__ == "__main__":
    main()
