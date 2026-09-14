"""Conservative optional OCR preprocessing."""

import cv2
import numpy as np

from visionguard.config.models import OCRPreprocessingConfig


class OCRPreprocessor:
    def __init__(self, config: OCRPreprocessingConfig, max_side_len: int) -> None:
        self.config = config
        self.max_side_len = max_side_len

    def process(self, image: np.ndarray) -> np.ndarray:
        output = self._resize(image)
        if not self.config.enabled:
            return output
        if self.config.grayscale:
            gray = cv2.cvtColor(output, cv2.COLOR_BGR2GRAY)
            output = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        if self.config.contrast_enhancement:
            lab = cv2.cvtColor(output, cv2.COLOR_BGR2LAB)
            light, a, b = cv2.split(lab)
            light = cv2.createCLAHE(2.0, (8, 8)).apply(light)
            output = cv2.cvtColor(cv2.merge((light, a, b)), cv2.COLOR_LAB2BGR)
        if self.config.denoise:
            output = cv2.fastNlMeansDenoisingColored(output, None, 3, 3, 7, 21)
        if self.config.sharpen:
            kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
            output = cv2.filter2D(output, -1, kernel)
        return output

    def _resize(self, image: np.ndarray) -> np.ndarray:
        height, width = image.shape[:2]
        longest = max(height, width)
        if longest <= self.max_side_len:
            return image
        scale = self.max_side_len / longest
        return cv2.resize(
            image,
            (max(1, round(width * scale)), max(1, round(height * scale))),
            interpolation=cv2.INTER_AREA,
        )
