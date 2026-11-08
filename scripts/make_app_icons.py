"""The server app's icon, made from the app's own icon (client/desktop/build/icon.png) so the two are one family: the same shape,
margin and play mark, recoloured the way a server or "pro" edition sits next to its app. The app is orange with a white triangle;
the server is graphite with an orange triangle; the yellow bar stays. Writes server/desktop/build/icon.png (1024), icon.ico and
server/desktop/server-icon.png (512).

    .venv/Scripts/python.exe scripts/make_app_icons.py
"""
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ORANGE = np.array([242, 106, 31], float)
GRAPHITE = np.array([43, 47, 54], float)
YELLOW = np.array([255, 200, 58], float)


def recolour(src: Image.Image) -> Image.Image:
    a = np.asarray(src.convert("RGBA")).astype(float)
    rgb, alpha = a[..., :3], a[..., 3:]
    white = np.clip((rgb.min(axis=2, keepdims=True) - 90) / (255 - 90), 0, 1)          # the triangle (and its soft edge)
    yellow = np.clip(1 - np.abs(rgb - YELLOW).sum(axis=2, keepdims=True) / 140, 0, 1)    # the bar
    yellow = yellow * (1 - white)
    base = 1 - white - yellow                                                            # the orange square
    out = base * GRAPHITE + white * ORANGE + yellow * rgb
    return Image.fromarray(np.concatenate([out, alpha], axis=2).round().clip(0, 255).astype(np.uint8), "RGBA")


def main() -> None:
    server = recolour(Image.open(ROOT / "client" / "desktop" / "build" / "icon.png"))
    out = ROOT / "server" / "desktop"
    server.save(out / "build" / "icon.png")
    server.resize((512, 512), Image.LANCZOS).save(out / "server-icon.png")
    server.resize((256, 256), Image.LANCZOS).save(out / "build" / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("wrote", out / "build" / "icon.png", out / "build" / "icon.ico", out / "server-icon.png")


if __name__ == "__main__":
    main()
