# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

ROOT = Path(SPECPATH).parents[1]
datas = [(str(ROOT / "prompts" / "vlm"), "resources/prompts/vlm")]
for distribution in ("transformers", "tokenizers", "huggingface-hub", "safetensors"):
    datas += copy_metadata(distribution)
datas += collect_data_files("transformers")
hiddenimports = collect_submodules("transformers.models.qwen3_vl")

analysis = Analysis(
    [str(ROOT / "src" / "visionguard" / "vlm_runtime" / "main.py")],
    pathex=[str(ROOT / "src")],
    datas=datas,
    hiddenimports=hiddenimports,
    runtime_hooks=[str(ROOT / "packaging" / "runtime" / "hooks" / "offline_model_hubs.py")],
    excludes=[
        "paddle", "paddleocr", "paddlex", "ultralytics", "onnxruntime", "sklearn", "cv2",
        "scipy", "pandas", "polars", "matplotlib", "tensorflow", "flax", "pytest",
    ],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz, analysis.scripts, [], exclude_binaries=True, name="visionguard-vlm-runtime",
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False, console=False,
)
collect = COLLECT(
    exe, analysis.binaries, analysis.datas, strip=False, upx=False,
    name="visionguard-vlm-runtime",
)
