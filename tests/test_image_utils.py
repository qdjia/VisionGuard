from pathlib import Path

import numpy as np
import pytest

from visionguard.detection import ImageLoadError
from visionguard.utils import load_image


def test_missing_path_raises_clear_error() -> None:
    with pytest.raises(ImageLoadError, match="does not exist"):
        load_image(Path("tests/fixtures/not-present.jpg"))


def test_corrupt_file_raises_clear_error() -> None:
    with pytest.raises(ImageLoadError, match="unreadable or corrupt"):
        load_image(Path("tests/fixtures/corrupt.jpg"))


def test_grayscale_is_converted_to_bgr() -> None:
    gray = np.full((4, 5), 17, dtype=np.uint8)
    converted = load_image(gray)

    assert converted.shape == (4, 5, 3)
    assert np.all(converted[:, :, 0] == 17)


def test_rgba_is_converted_to_bgr() -> None:
    rgba = np.zeros((2, 3, 4), dtype=np.uint8)
    rgba[:, :, :3] = [10, 20, 30]
    converted = load_image(rgba)

    assert converted[0, 0].tolist() == [30, 20, 10]


def test_bgr_array_is_preserved() -> None:
    bgr = np.zeros((2, 2, 3), dtype=np.uint8)
    bgr[0, 0] = [3, 2, 1]
    converted = load_image(bgr)

    assert converted.shape == (2, 2, 3)
    assert converted[0, 0].tolist() == [3, 2, 1]


def test_empty_array_is_rejected() -> None:
    with pytest.raises(ImageLoadError, match="empty"):
        load_image(np.array([], dtype=np.uint8))
