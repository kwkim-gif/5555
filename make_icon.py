"""
Generate assets/icon.ico.
Run standalone: python make_icon.py
Called automatically by build.bat when icon is missing.
"""

from __future__ import annotations

from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    import subprocess, sys
    subprocess.run([sys.executable, "-m", "pip", "install", "pillow", "--quiet"], check=True)
    from PIL import Image, ImageDraw, ImageFont


def make_icon(output_path: str = "assets/icon.ico") -> None:
    SIZE = 512
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Background circle
    d.ellipse([4, 4, SIZE - 4, SIZE - 4], fill=(25, 118, 210, 255))

    # Sound wave arcs (left)
    arc_color = (255, 255, 255, 200)
    d.arc([60, 130, 190, 380], start=210, end=150, fill=arc_color, width=22)
    d.arc([30, 100, 220, 410], start=210, end=150, fill=arc_color, width=14)

    # Sound wave arcs (right)
    d.arc([320, 130, 450, 380], start=330, end=30, fill=arc_color, width=22)
    d.arc([290, 100, 480, 410], start=330, end=30, fill=arc_color, width=14)

    # Microphone body
    d.rounded_rectangle([186, 100, 324, 300], radius=70, fill=(255, 255, 255, 255))

    # Microphone stand
    d.line([(255, 300), (255, 380)], fill=(255, 255, 255, 255), width=18)
    d.line([(200, 380), (310, 380)], fill=(255, 255, 255, 255), width=18)

    # "AI" label
    try:
        font = ImageFont.truetype("arial.ttf", 70)
    except Exception:
        font = ImageFont.load_default()
    d.text((200, 400), "AI", font=font, fill=(255, 255, 255, 230))

    # Save multi-resolution ICO
    out = Path(output_path)
    out.parent.mkdir(exist_ok=True)
    sizes = [16, 24, 32, 48, 64, 128, 256]
    resized = [img.resize((s, s), Image.LANCZOS) for s in sizes]
    resized[0].save(
        str(out),
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=resized[1:],
    )
    print(f"Icon saved: {out}")


if __name__ == "__main__":
    make_icon()
