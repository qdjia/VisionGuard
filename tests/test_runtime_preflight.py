from pathlib import Path
from types import SimpleNamespace

import pytest

from visionguard.runtime.config import RuntimeConfig
from visionguard.runtime.main import HardwarePreflightError, _hardware_preflight


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
