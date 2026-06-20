"""
Generate assets/icon.ico.
Usage:
  python make_icon.py                         # saves to assets/icon.ico
  python make_icon.py C:\path\to\icon.ico     # saves to specified path
"""

from __future__ import annotations

import sys
from pathlib import Path


def make_icon(output_path: str) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "pillow", "--quiet"], check=True)
        from PIL import Image, ImageDraw, ImageFont

    SIZE = 256
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Background circle
    d.ellipse([4, 4, SIZE - 4, SIZE - 4], fill=(25, 118, 210, 255))

    # Microphone body
    d.ellipse([80, 60, 176, 156], fill=(255, 255, 255, 255))

    # Microphone stand
    d.line([(128, 156), (128, 200)], fill=(255, 255, 255, 255), width=10)
    d.line([(100, 200), (156, 200)], fill=(255, 255, 255, 255), width=10)

    # "AI" label
    try:
        font = ImageFont.truetype("arial.ttf", 36)
    except Exception:
        font = ImageFont.load_default()
    d.text((100, 210), "AI", font=font, fill=(255, 255, 255, 220))

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    sizes = [16, 24, 32, 48, 64, 128, 256]
    icons = [img.resize((s, s), Image.LANCZOS) for s in sizes]
    icons[0].save(str(out), format="ICO", sizes=[(s, s) for s in sizes], append_images=icons[1:])
    print(f"[OK] Icon saved: {out}")


if __name__ == "__main__":
    dest = sys.argv[1] if len(sys.argv) > 1 else "assets/icon.ico"
    make_icon(dest)
