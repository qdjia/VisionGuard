"""Image input normalization for OpenCV-based inference."""

from pathlib import Path
from typing import TypeAlias

import cv2
import numpy as np

from visionguard.core.exceptions import ImageLoadError

ImageInput: TypeAlias = str | Path | np.ndarray


def _validate_array(image: np.ndarray) -> None:
    if image.size == 0:
        raise ImageLoadError("image array is empty")
    if image.ndim not in (2, 3):
        raise ImageLoadError(f"image array must have 2 or 3 dimensions, got {image.ndim}")
    if image.dtype != np.uint8:
        raise ImageLoadError(f"image array must use uint8 dtype, got {image.dtype}")


def load_image(source: ImageInput) -> np.ndarray:
    """Return a contiguous uint8 BGR image.

    Three-channel ndarray inputs are interpreted as OpenCV-style BGR. Four-channel
    ndarray inputs are interpreted as RGBA and converted to BGR.
    """

    if isinstance(source, (str, Path)):
        path = Path(source).expanduser()
        if not path.is_file():
            raise ImageLoadError(f"image file does not exist: {path}")
        image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if image is None:
            raise ImageLoadError(f"image file is unreadable or corrupt: {path}")
    elif isinstance(source, np.ndarray):
        image = source
    else:
        raise ImageLoadError(f"unsupported image input type: {type(source).__name__}")

    _validate_array(image)
    try:
        if image.ndim == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        elif image.shape[2] == 1:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        elif image.shape[2] == 4:
            image = cv2.cvtColor(image, cv2.COLOR_RGBA2BGR)
        elif image.shape[2] != 3:
            raise ImageLoadError(f"image must have 1, 3, or 4 channels, got {image.shape[2]}")
    except cv2.error as exc:
        raise ImageLoadError("OpenCV failed to normalize the image") from exc

    return np.ascontiguousarray(image)
