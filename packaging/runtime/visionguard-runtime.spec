# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from importlib.util import find_spec

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

ROOT = Path(SPECPATH).parents[1]

datas = [
    (str(ROOT / "configs"), "resources/configs"),
    (str(ROOT / "prompts"), "resources/prompts"),
]
datas += collect_data_files("ultralytics")
datas += collect_data_files("paddleocr")
datas += collect_data_files("paddlex")
datas += collect_data_files("sklearn")
for distribution in (
    "imagesize",
    "opencv-contrib-python",
    "pyclipper",
    "pypdfium2",
    "python-bidi",
    "shapely",
):
    datas += copy_metadata(distribution)
paddle_spec = find_spec("paddle")
if paddle_spec is None or not paddle_spec.submodule_search_locations:
    raise RuntimeError("paddle package is required to build the local runtime")
paddle_root = Path(next(iter(paddle_spec.submodule_search_locations)))
binaries = [(str(path), "paddle/libs") for path in (paddle_root / "libs").glob("*.dll")]
hiddenimports = [
    "transformers.models.qwen3_vl.configuration_qwen3_vl",
    "transformers.models.qwen3_vl.modeling_qwen3_vl",
    "transformers.models.qwen3_vl.processing_qwen3_vl",
    "transformers.models.qwen3_vl.video_processing_qwen3_vl",
]
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
        "pytest",
        "tensorboard",
        "matplotlib.tests",
        "notebook",
        "jupyter",
        "modelscope",
        "tensorflow",
        "flax",
    ],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="visionguard-runtime",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)
collect = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="visionguard-runtime",
)
