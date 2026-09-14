"""Sample prediction export built on the Phase 2 detector."""

from pathlib import Path

from visionguard.config.models import DetectionConfig
from visionguard.detection.dataset import _images, load_dataset_config
from visionguard.detection.detector import YOLODetector
from visionguard.detection.visualization import save_visualization
from visionguard.utils.image import load_image


def export_validation_predictions(
    checkpoint: Path,
    dataset_yaml: Path,
    output_dir: Path,
    *,
    sample_count: int,
    device: str,
    image_size: int,
) -> Path:
    dataset = load_dataset_config(dataset_yaml)
    config = DetectionConfig(
        classes_file=dataset.yaml_path,
        class_names=tuple(dataset.names.values()),
        model_path=checkpoint,
        conf_threshold=0.25,
        iou_threshold=0.45,
        max_det=300,
        image_size=image_size,
        device=device,
        half_precision=True,
        warmup_enabled=False,
        class_name_mapping={},
    )
    detector = YOLODetector(config)
    output_dir.mkdir(parents=True, exist_ok=True)
    for image_path in _images(dataset.root / dataset.val)[:sample_count]:
        image = load_image(image_path)
        result = detector.predict(image)
        save_visualization(image, result.detections, output_dir / image_path.name)
    return output_dir
