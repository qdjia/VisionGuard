"""OCR polygon, bounding-box, and Unicode label rendering."""

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from visionguard.core.exceptions import ImageLoadError
from visionguard.schemas import OCRTextBlock


def _load_font(
    font_path: str | Path | None, size: int = 18
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [font_path] if font_path else []
    candidates.extend(
        [
            Path("C:/Windows/Fonts/msyh.ttc"),
            Path("C:/Windows/Fonts/simhei.ttf"),
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        ]
    )
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            try:
                return ImageFont.truetype(str(candidate), size)
            except OSError:
                continue
    return ImageFont.load_default()


def draw_ocr_blocks(
    image: np.ndarray,
    blocks: list[OCRTextBlock],
    *,
    font_path: str | Path | None = None,
) -> np.ndarray:
    canvas = image.copy()
    height, width = canvas.shape[:2]
    for block in blocks:
        polygon = np.array(
            [
                [min(max(round(x), 0), width - 1), min(max(round(y), 0), height - 1)]
                for x, y in block.polygon
            ],
            dtype=np.int32,
        )
        cv2.polylines(canvas, [polygon], True, (0, 200, 255), 2, cv2.LINE_AA)
        box = block.bbox
        cv2.rectangle(
            canvas,
            (max(0, round(box.x1)), max(0, round(box.y1))),
            (min(width - 1, round(box.x2)), min(height - 1, round(box.y2))),
            (255, 120, 0),
            1,
        )
    rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
    pil_image = Image.fromarray(rgb)
    draw = ImageDraw.Draw(pil_image)
    font = _load_font(font_path)
    for block in blocks:
        draw.text(
            (block.bbox.x1, max(0, block.bbox.y1 - 20)),
            f"{block.text} {block.confidence:.2f}",
            fill=(255, 0, 0),
            font=font,
        )
    return cv2.cvtColor(np.asarray(pil_image), cv2.COLOR_RGB2BGR)


def save_ocr_visualization(
    image: np.ndarray, blocks: list[OCRTextBlock], output_path: str | Path
) -> Path:
    target = Path(output_path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(target), draw_ocr_blocks(image, blocks)):
        raise ImageLoadError(f"failed to save OCR visualization: {target}")
    return target.resolve()
