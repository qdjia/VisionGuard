"""Create self-constructed VLM fixtures, not a representative accuracy dataset."""

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _font(size: int) -> ImageFont.ImageFont:
    candidates = (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/System/Library/Fonts/PingFang.ttc"),
    )
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow 10.0 has no scalable default-font argument.
        return ImageFont.load_default()


def main() -> int:
    directory = Path("data/vlm_eval")
    directory.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (224, 224), "white").save(directory / "safe.png")
    image = Image.new("RGB", (640, 240), "white")
    font = _font(36)
    ImageDraw.Draw(image).text((30, 80), "出版内容智能审校", font=font, fill="black")
    image.save(directory / "text.png")
    risky = Image.new("RGB", (640, 240), "white")
    ImageDraw.Draw(risky).text((30, 80), "鼓励暴力伤害他人", font=font, fill="black")
    risky.save(directory / "risky.png")
    rows = [
        {"image": name, "risk_level": "low", "categories": []} for name in ("safe.png", "text.png")
    ]
    rows.append({"image": "risky.png", "risk_level": "high", "categories": ["sensitive_text"]})
    (directory / "manifest.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
