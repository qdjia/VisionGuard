import pytest
from pydantic import ValidationError

from visionguard.training import load_train_config


def test_training_config_resolves_paths_and_augmentation() -> None:
    config = load_train_config("configs/train_detector.yaml")

    assert config.data.name == "visionguard.yaml"
    assert config.augmentation.degrees == 5.0
    assert config.amp is True


def test_training_config_rejects_generic_experiment_name() -> None:
    config = load_train_config("configs/train_detector.yaml")

    with pytest.raises(ValidationError, match="experiment_name"):
        config.model_copy(update={"experiment_name": "exp"}).model_validate(
            {**config.model_dump(), "experiment_name": "exp"}
        )
