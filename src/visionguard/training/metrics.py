"""Conversion of Ultralytics metrics to stable schemas."""

from typing import Any

from visionguard.training.schemas import ClassMetrics, DetectionMetrics


def _list(value: Any) -> list[float]:
    if value is None:
        return []
    value = value.tolist() if hasattr(value, "tolist") else value
    return [float(value)] if isinstance(value, (int, float)) else [float(x) for x in value]


def extract_detection_metrics(result: Any) -> DetectionMetrics:
    box = getattr(result, "box", None) or getattr(getattr(result, "metrics", None), "box", None)
    if box is None:
        raise ValueError("validation result does not contain detection metrics")
    names = getattr(result, "names", {})
    arrays = [_list(getattr(box, key, None)) for key in ("p", "r", "ap50", "maps")]
    per_class: dict[str, ClassMetrics] = {}
    for index in range(max((len(values) for values in arrays), default=0)):
        name = str(names.get(index, index)) if isinstance(names, dict) else str(names[index])
        values = [items[index] if index < len(items) else 0.0 for items in arrays]
        per_class[name] = ClassMetrics(
            precision=values[0], recall=values[1], ap50=values[2], map50_95=values[3]
        )
    return DetectionMetrics(
        precision=float(getattr(box, "mp", 0)),
        recall=float(getattr(box, "mr", 0)),
        map50=float(getattr(box, "map50", 0)),
        map50_95=float(getattr(box, "map", 0)),
        per_class=per_class,
    )
