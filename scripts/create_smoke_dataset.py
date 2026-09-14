"""Generate a tiny synthetic YOLO dataset for pipeline smoke testing."""

from pathlib import Path

import cv2
import numpy as np


def main() -> int:
    root = Path("data/visionguard_smoke")
    samples = {"train": 4, "val": 2, "test": 2}
    for split, count in samples.items():
        image_dir = root / "images" / split
        label_dir = root / "labels" / split
        image_dir.mkdir(parents=True, exist_ok=True)
        label_dir.mkdir(parents=True, exist_ok=True)
        for index in range(count):
            image = np.full((320, 320, 3), 235, dtype=np.uint8)
            offset = index * 8
            cv2.rectangle(image, (80 + offset, 90), (220 + offset, 230), (20, 20, 220), -1)
            name = f"{split}_{index:02d}"
            if not cv2.imwrite(str(image_dir / f"{name}.jpg"), image):
                raise RuntimeError(f"failed to write smoke image: {name}")
            center_x = (150 + offset) / 320
            label = f"0 {center_x:.6f} 0.500000 0.437500 0.437500\n"
            (label_dir / f"{name}.txt").write_text(label, encoding="utf-8")
    print(f"created smoke dataset at {root.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
