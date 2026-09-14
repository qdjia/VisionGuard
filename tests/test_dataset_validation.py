from visionguard.detection.dataset import DatasetValidator, load_dataset_config


def test_dataset_config_resolves_root_and_classes() -> None:
    config = load_dataset_config("tests/fixtures/yolo_dataset.yaml")

    assert config.root.name == "yolo_dataset"
    assert config.names == {0: "weapon"}


def test_validator_reports_specific_pair_label_and_leakage_errors() -> None:
    report = DatasetValidator(load_dataset_config("tests/fixtures/yolo_dataset.yaml")).validate()
    codes = {issue.code for issue in report.issues}

    assert report.valid is False
    assert report.total_images == 4
    assert report.total_boxes == 1
    assert {"missing_label", "missing_image", "invalid_label", "cross_split_duplicate"} <= codes
