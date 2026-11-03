"""Generates design/textures/paper-grain.png (the subtle paper noise behind the Paper theme). Deterministic.
Usage: python scripts/make_texture.py"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

OUT = Path(__file__).resolve().parents[1] / "server" / "design" / "textures" / "paper-grain.png"


def main() -> None:
    rng = np.random.default_rng(7)
    n = 512
    lum = rng.normal(0, 1, (n, n))
    base = Image.fromarray(np.uint8(np.clip(128 + lum * 40, 0, 255)), "L").filter(ImageFilter.GaussianBlur(0.6))
    a = np.asarray(base).astype(float)
    alpha = np.clip((np.abs(a - 128) / 128.0) * 70, 0, 40).astype(np.uint8)       # darker or lighter specks, max alpha 40/255
    rgb = np.where(a[..., None] < 128, np.array([90, 82, 66]), np.array([255, 255, 255])).astype(np.uint8)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.dstack([rgb, alpha]), "RGBA").save(OUT, optimize=True)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
