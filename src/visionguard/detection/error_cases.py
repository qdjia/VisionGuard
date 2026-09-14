"""Lightweight IoU-based error case export for Phase 3."""

import json
from pathlib import Path

from visionguard.config.models import DetectionConfig
from visionguard.detection.dataset import _images, _label_dir, load_dataset_config
from visionguard.detection.detector import YOLODetector
from visionguard.detection.visualization import save_visualization
from visionguard.schemas import BoundingBox
from visionguard.utils.image import load_image


def box_iou(left: BoundingBox, right: BoundingBox) -> float:
    x1, y1 = max(left.x1, right.x1), max(left.y1, right.y1)
    x2, y2 = min(left.x2, right.x2), min(left.y2, right.y2)
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    left_area = (left.x2 - left.x1) * (left.y2 - left.y1)
    right_area = (right.x2 - right.x1) * (right.y2 - right.y1)
    union = left_area + right_area - intersection
    return intersection / union if union else 0.0


def _ground_truth(path: Path, width: int, height: int) -> list[tuple[int, BoundingBox]]:
    boxes = []
    if not path.is_file():
        return boxes
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        class_id, x, y, w, h = map(float, line.split())
        boxes.append(
            (
                int(class_id),
                BoundingBox(
                    x1=(x - w / 2) * width,
                    y1=(y - h / 2) * height,
                    x2=(x + w / 2) * width,
                    y2=(y + h / 2) * height,
                ),
            )
        )
    return boxes


def export_error_cases(
    checkpoint: Path,
    dataset_yaml: Path,
    output_dir: Path,
    *,
    split: str = "val",
    device: str = "auto",
    iou_threshold: float = 0.5,
    low_confidence: float = 0.4,
    high_confidence: float = 0.8,
) -> Path:
    dataset = load_dataset_config(dataset_yaml)
    relative = getattr(dataset, split)
    if relative is None:
        raise ValueError(f"dataset does not define split: {split}")
    config = DetectionConfig(
        classes_file=dataset.yaml_path,
        class_names=tuple(dataset.names.values()),
        model_path=checkpoint,
        conf_threshold=0.01,
        iou_threshold=0.45,
        max_det=300,
        image_size=640,
        device=device,
        half_precision=True,
        warmup_enabled=False,
        class_name_mapping={},
    )
    detector = YOLODetector(config)
    output_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    label_dir = _label_dir(dataset.root, relative)
    for image_path in _images(dataset.root / relative):
        image = load_image(image_path)
        result = detector.predict(image)
        ground_truth = _ground_truth(
            label_dir / f"{image_path.stem}.txt", result.image_width, result.image_height
        )
        matched_gt: set[int] = set()
        image_types: set[str] = set()
        for prediction in result.detections:
            candidates = [
                (index, box_iou(prediction.bbox, box))
                for index, (class_id, box) in enumerate(ground_truth)
                if class_id == prediction.class_id and index not in matched_gt
            ]
            best_index, best_iou = max(candidates, key=lambda item: item[1], default=(-1, 0.0))
            if best_iou >= iou_threshold:
                matched_gt.add(best_index)
            error_type = None
            if prediction.confidence < low_confidence:
                error_type = "low_confidence"
            elif best_iou < iou_threshold and prediction.confidence >= high_confidence:
                error_type = "false_positive"
            if error_type:
                image_types.add(error_type)
                records.append(
                    {
                        "image_path": str(image_path),
                        "error_type": error_type,
                        "class_name": prediction.class_name,
                        "confidence": prediction.confidence,
                        "pred_bbox": prediction.bbox.model_dump(),
                        "gt_bbox": ground_truth[best_index][1].model_dump()
                        if best_index >= 0
                        else None,
                        "iou": best_iou,
                    }
                )
        for index, (class_id, gt_box) in enumerate(ground_truth):
            if index not in matched_gt:
                image_types.add("false_negative")
                records.append(
                    {
                        "image_path": str(image_path),
                        "error_type": "false_negative",
                        "class_name": dataset.names[class_id],
                        "confidence": 0.0,
                        "pred_bbox": None,
                        "gt_bbox": gt_box.model_dump(),
                        "iou": 0.0,
                    }
                )
        if len(result.detections) > 1:
            image_types.add("multi_conflict")
        for error_type in image_types:
            save_visualization(image, result.detections, output_dir / error_type / image_path.name)
    manifest = output_dir / "error_cases.jsonl"
    manifest.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    return manifest
