from pathlib import Path

from visionguard.training import load_train_config
from visionguard.training.experiment import ExperimentManager


def test_experiment_directory_and_config_snapshot_are_created() -> None:
    config = load_train_config("configs/train_detector_smoke.yaml").model_copy(
        update={
            "artifacts_dir": Path("artifacts/test_experiments").resolve(),
            "experiment_name": "unit_test_experiment",
            "resume": True,
        }
    )
    manager = ExperimentManager(config)

    assert manager.prepare().is_dir()
    assert manager.save_config().is_file()
