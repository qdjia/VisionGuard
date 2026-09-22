from pathlib import Path

from visionguard.runtime.config import RuntimeConfig


def test_runtime_config_accepts_operating_system_assigned_port(tmp_path: Path) -> None:
    config = RuntimeConfig(
        port=0,
        model_bundle_path=tmp_path / "models",
        user_data_dir=tmp_path / "data",
        artifact_root=tmp_path / "artifacts",
        log_root=tmp_path / "logs",
        cache_root=tmp_path / "cache",
    )

    assigned = config.model_copy(update={"port": 43125})

    assert config.port == 0
    assert assigned.port == 43125
    assert assigned.warmup_on_startup is False
    assert assigned.runtime_edition == "gpu"
    assert assigned.minimum_free_disk_bytes == 512 * 1024 * 1024
