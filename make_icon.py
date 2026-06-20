"""
아이콘 파일 생성 스크립트.
build.bat 내부에서 자동 실행되지만 독립 실행도 가능.
  python make_icon.py
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

    # 배경 원
    d.ellipse([4, 4, SIZE - 4, SIZE - 4], fill=(25, 118, 210, 255))

    # 음파 호 (좌)
    arc_color = (255, 255, 255, 200)
    d.arc([60, 130, 190, 380], start=210, end=150, fill=arc_color, width=22)
    d.arc([30, 100, 220, 410], start=210, end=150, fill=arc_color, width=14)

    # 음파 호 (우)
    d.arc([320, 130, 450, 380], start=330, end=30, fill=arc_color, width=22)
    d.arc([290, 100, 480, 410], start=330, end=30, fill=arc_color, width=14)

    # 마이크 몸체
    d.rounded_rectangle([186, 100, 324, 300], radius=70, fill=(255, 255, 255, 255))

    # 마이크 스탠드
    d.line([(255, 300), (255, 380)], fill=(255, 255, 255, 255), width=18)
    d.line([(200, 380), (310, 380)], fill=(255, 255, 255, 255), width=18)

    # "AI" 텍스트
    try:
        font = ImageFont.truetype("arial.ttf", 70)
    except Exception:
        font = ImageFont.load_default()
    d.text((200, 400), "AI", font=font, fill=(255, 255, 255, 230))

    # ICO 저장 (다중 해상도)
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
