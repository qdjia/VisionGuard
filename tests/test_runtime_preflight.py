from pathlib import Path
from types import SimpleNamespace

import pytest

from visionguard.runtime.config import RuntimeConfig
from visionguard.runtime.main import HardwarePreflightError, _exception_chain, _hardware_preflight


def _config(tmp_path: Path, **values) -> RuntimeConfig:
    return RuntimeConfig(
        model_bundle_path=tmp_path / "models",
        user_data_dir=tmp_path / "data",
        artifact_root=tmp_path / "artifacts",
        log_root=tmp_path / "logs",
        cache_root=tmp_path / "cache",
        **values,
    )


def test_gpu_preflight_fails_before_model_loading(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "visionguard.runtime.main._diagnostics",
        lambda: {
            "platform": "Windows",
            "architecture": "AMD64",
            "cuda_available": False,
        },
    )

    with pytest.raises(HardwarePreflightError) as error:
        _hardware_preflight(_config(tmp_path))

    assert error.value.code == "GPU_REQUIREMENT_NOT_SATISFIED"


def test_cpu_preflight_reports_available_disk(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "visionguard.runtime.main._diagnostics",
        lambda: {
            "platform": "Windows",
            "architecture": "AMD64",
            "cuda_available": False,
        },
    )
    monkeypatch.setattr(
        "visionguard.runtime.main.shutil.disk_usage",
        lambda _path: SimpleNamespace(free=1024),
    )

    diagnostics = _hardware_preflight(
        _config(tmp_path, runtime_edition="cpu", minimum_free_disk_bytes=512)
    )

    assert diagnostics["runtime_edition"] == "cpu"
    assert diagnostics["user_data_free_disk_bytes"] == 1024


def test_startup_exception_chain_preserves_wrapped_provider_error() -> None:
    try:
        try:
            raise ValueError("missing inference.json")
        except ValueError as exc:
            raise RuntimeError("PaddleOCR prediction failed") from exc
    except RuntimeError as exc:
        chain = _exception_chain(exc)

    assert chain == [
        {"type": "RuntimeError", "message": "PaddleOCR prediction failed"},
        {"type": "ValueError", "message": "missing inference.json"},
    ]


def test_runtime_diagnostics_records_ocr_dependency_versions(monkeypatch) -> None:
    from visionguard.runtime import main

    monkeypatch.setattr(main.platform, "python_version", lambda: "3.11.9")
    monkeypatch.setattr(main.platform, "system", lambda: "Windows")
    monkeypatch.setattr(main.platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(main.os, "cpu_count", lambda: 2)
    versions = {
        "paddleocr": "3.4.0",
        "paddlepaddle": "3.3.0",
        "paddlex": "3.7.2",
        "numpy": "2.3.5",
        "opencv-contrib-python": "4.10.0.84",
    }
    monkeypatch.setattr(main.importlib.metadata, "version", versions.__getitem__)

    diagnostics = main._diagnostics()

    assert diagnostics["cpu_count"] == 2
    assert diagnostics["dependency_versions"] == versions
