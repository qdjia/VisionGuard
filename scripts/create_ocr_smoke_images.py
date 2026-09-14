"""Create lightweight printed Chinese and English images for OCR smoke testing."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _font(size: int) -> ImageFont.FreeTypeFont:
    candidates = (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    )
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size)
    raise FileNotFoundError("install a Chinese font or provide OCR smoke images manually")


def _save(path: Path, lines: list[str]) -> None:
    image = Image.new("RGB", (1000, 360), "white")
    draw = ImageDraw.Draw(image)
    font = _font(54)
    for index, line in enumerate(lines):
        draw.text((60, 50 + index * 110), line, fill="black", font=font)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def main() -> int:
    output = Path("data/ocr_smoke")
    _save(output / "chinese.png", ["VisionGuard 出版内容智能审校", "安全、准确、可追踪"])
    _save(output / "english.png", ["VisionGuard OCR Smoke Test", "Publishing Content Review"])
    print(output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
