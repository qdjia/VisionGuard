import numpy as np

from visionguard.config.models import OCRPreprocessingConfig
from visionguard.ocr.preprocessing import OCRPreprocessor


def test_preprocessor_keeps_original_shape_when_disabled_and_small() -> None:
    image = np.full((40, 80, 3), 127, dtype=np.uint8)
    result = OCRPreprocessor(OCRPreprocessingConfig(), max_side_len=100).process(image)

    assert result.shape == image.shape
    assert np.array_equal(result, image)


def test_preprocessor_resizes_long_side_without_changing_channels() -> None:
    image = np.zeros((100, 200, 3), dtype=np.uint8)
    result = OCRPreprocessor(OCRPreprocessingConfig(), max_side_len=100).process(image)

    assert result.shape == (50, 100, 3)
