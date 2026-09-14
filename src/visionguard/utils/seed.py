"""Reproducibility controls for Python, NumPy, and PyTorch."""

import os
import random

import numpy as np


def set_seed(seed: int, *, deterministic: bool = True) -> None:
    random.seed(seed)
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    import torch

    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    # Determinism improves reproducibility but can reduce training throughput.
    torch.backends.cudnn.deterministic = deterministic
    torch.backends.cudnn.benchmark = not deterministic
