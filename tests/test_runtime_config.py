import subprocess
from pathlib import Path

import yaml

from visionguard.runtime.config import (
    RUNTIME_CONFIG_FILES,
    RuntimeConfig,
    materialize_api_config,
)

ROOT = Path(__file__).resolve().parents[1]


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


def test_packaged_runtime_configuration_inputs_are_tracked() -> None:
    expected = {f"configs/{name}" for name in RUNTIME_CONFIG_FILES}
    tracked = set(
        subprocess.run(
            ["git", "ls-files", "configs"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
    )

    assert expected <= tracked
    assert "configs/local_vlm.yaml" not in expected


def test_runtime_materialization_uses_the_tracked_vlm_template(tmp_path: Path) -> None:
    baseline = tmp_path / "models/baseline"
    baseline.mkdir(parents=True)
    (baseline / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "baseline": {
                    "train": "train.csv",
                    "val": "val.csv",
                    "test": "test.csv",
                    "artifacts_dir": "artifacts",
                }
            }
        ),
        encoding="utf-8",
    )
    runtime = RuntimeConfig(
        port=43125,
        model_bundle_path=tmp_path / "models",
        user_data_dir=tmp_path / "data",
        artifact_root=tmp_path / "artifacts",
        log_root=tmp_path / "logs",
        cache_root=tmp_path / "cache",
    )

    materialized = materialize_api_config(
        runtime,
        resource_root=ROOT,
        run_dir=tmp_path / "run",
        bundle_version="core-models-v1",
        model_paths={
            "detector": tmp_path / "models/detector/model.onnx",
            "ocr_detection": tmp_path / "models/ocr/detection",
            "ocr_recognition": tmp_path / "models/ocr/recognition",
            "ocr_orientation": tmp_path / "models/ocr/orientation",
            "baseline": baseline,
        },
    )

    generated = yaml.safe_load(materialized.services.vlm_config.read_text(encoding="utf-8"))
    assert generated["vlm"]["provider"] == "remote"
    assert generated["vlm"]["model_name_or_path"] == "optional-advanced-ai"
    assert materialized.services.vlm_config == tmp_path / "run/configs/vlm.yaml"
