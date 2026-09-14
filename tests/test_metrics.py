from pathlib import Path

from visionguard.detection.trainer import _best_epoch
from visionguard.training.metrics import extract_detection_metrics


class BoxMetrics:
    mp = 0.8
    mr = 0.7
    map50 = 0.75
    map = 0.55
    p = [0.81]
    r = [0.71]
    ap50 = [0.76]
    maps = [0.56]


class Result:
    box = BoxMetrics()
    names = {0: "weapon"}


def test_metrics_are_serializable_with_per_class_values() -> None:
    metrics = extract_detection_metrics(Result())

    assert metrics.map50_95 == 0.55
    assert metrics.per_class["weapon"].ap50 == 0.76
    assert metrics.model_dump(mode="json")["precision"] == 0.8


def test_best_epoch_is_read_from_ultralytics_results() -> None:
    assert _best_epoch(Path("tests/fixtures/results.csv")) == 2
