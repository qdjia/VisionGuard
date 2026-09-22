"""PyInstaller startup hook for optional model hubs forbidden in local runtime."""

import os
import sys
import types

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"
os.environ["YOLO_AUTOINSTALL"] = "false"


def _offline_modelscope(*_args, **_kwargs):
    raise RuntimeError(
        "ModelScope downloads are disabled in the packaged VisionGuard runtime; "
        "use the versioned local model bundle."
    )


# PaddleX 3.7 imports ModelScope unconditionally even when every model directory
# is local.  Shipping all of ModelScope would recursively collect unrelated CV
# models and optional CUDA extensions.  This minimal module makes that optional
# import explicit while keeping any accidental download attempt fail-closed.
modelscope = types.ModuleType("modelscope")
modelscope.__path__ = []
modelscope.__version__ = "offline-shim"
modelscope.snapshot_download = _offline_modelscope
sys.modules["modelscope"] = modelscope
