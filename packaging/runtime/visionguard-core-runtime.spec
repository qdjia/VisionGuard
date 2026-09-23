# -*- mode: python ; coding: utf-8 -*-

from importlib.util import find_spec
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

ROOT = Path(SPECPATH).parents[1]
datas = [(str(ROOT / "configs"), "resources/configs"), (str(ROOT / "prompts"), "resources/prompts")]
datas += collect_data_files("paddleocr")
datas += collect_data_files("paddlex")
datas += collect_data_files("sklearn")
for distribution in ("imagesize", "opencv-contrib-python", "pyclipper", "pypdfium2", "python-bidi", "shapely"):
    datas += copy_metadata(distribution)

paddle_spec = find_spec("paddle")
if paddle_spec is None or not paddle_spec.submodule_search_locations:
    raise RuntimeError("paddle package is required to build the core runtime")
paddle_root = Path(next(iter(paddle_spec.submodule_search_locations)))
binaries = [(str(path), "paddle/libs") for path in (paddle_root / "libs").glob("*.dll")]
hiddenimports = []
for package in (
    "paddlex.inference.pipelines.ocr",
    "paddlex.inference.models.text_detection",
    "paddlex.inference.models.text_recognition",
    "paddlex.inference.models.image_classification",
):
    hiddenimports += collect_submodules(package)

analysis = Analysis(
    [str(ROOT / "src" / "visionguard" / "runtime" / "main.py")],
    pathex=[str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    runtime_hooks=[str(ROOT / "packaging" / "runtime" / "hooks" / "offline_model_hubs.py")],
    excludes=[
        "torch", "torchvision", "ultralytics", "transformers", "accelerate", "modelscope",
        "tensorflow", "flax", "pytest", "tensorboard", "notebook", "jupyter", "matplotlib",
        "polars",
    ],
    noarchive=False,
)
# The build environment also contains onnxruntime-gpu for experiments. The
# release-core profile is intentionally CPU-only, so remove provider DLLs and
# the CUDA libraries that the ORT hook opportunistically copied from PyTorch.
def core_binary(item):
    destination = item[0].replace("\\", "/").lower()
    return not (
        destination.startswith("torch/")
        or destination.endswith("onnxruntime_providers_cuda.dll")
        or destination.endswith("onnxruntime_providers_tensorrt.dll")
    )


analysis.binaries = [item for item in analysis.binaries if core_binary(item)]
pyz = PYZ(analysis.pure)
exe = EXE(pyz, analysis.scripts, [], exclude_binaries=True, name="visionguard-core-runtime", debug=False, bootloader_ignore_signals=False, strip=False, upx=False, console=False)
collect = COLLECT(exe, analysis.binaries, analysis.datas, strip=False, upx=False, name="visionguard-core-runtime")
