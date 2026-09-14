from pathlib import Path

import pytest

from visionguard.config import ConfigLoadError, load_config


def test_load_default_config() -> None:
    config = load_config("configs/default.yaml")

    assert config.detection.class_names[1] == "weapon"
    assert len(config.detection.class_names) == 8
    assert config.project.artifacts_dir == Path("artifacts").resolve()
    assert config.detection.classes_file == Path("configs/classes.yaml").resolve()


def test_unknown_config_key_is_rejected() -> None:
    with pytest.raises(ConfigLoadError, match="misspelled_option"):
        load_config("tests/fixtures/invalid_unknown_key.yaml")
