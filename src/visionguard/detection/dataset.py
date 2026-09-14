"""Validation for standard YOLO detection datasets."""

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import cv2
import yaml
from pydantic import Field, ValidationError, field_validator

from visionguard.config import ConfigLoadError
from visionguard.schemas.common import SchemaModel

IMAGE_EXTENSIONS = {".bmp", ".jpeg", ".jpg", ".pgm", ".png", ".tif", ".tiff", ".webp"}


class DatasetConfig(SchemaModel):
    yaml_path: Path
    root: Path
    train: str
    val: str
    test: str | None = None
    names: dict[int, str]
    allow_empty_labels: bool = True

    @field_validator("names")
    @classmethod
    def contiguous_classes(cls, value: dict[int, str]) -> dict[int, str]:
        if sorted(value) != list(range(len(value))):
            raise ValueError("class ids must be contiguous and start at zero")
        if len(set(value.values())) != len(value):
            raise ValueError("class names must be unique")
        return value


class DatasetIssue(SchemaModel):
    code: str
    path: Path
    reason: str
    split: str | None = None


class DatasetReport(SchemaModel):
    valid: bool
    total_images: int
    total_boxes: int
    empty_label_images: int
    images_per_class: dict[str, int]
    boxes_per_class: dict[str, int]
    split_images: dict[str, int]
    issues: list[DatasetIssue] = Field(default_factory=list)


def load_dataset_config(path: str | Path) -> DatasetConfig:
    yaml_path = Path(path).expanduser().resolve()
    try:
        raw: Any = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigLoadError(f"failed to read dataset config: {yaml_path}") from exc
    if not isinstance(raw, dict):
        raise ConfigLoadError(f"dataset config root must be a mapping: {yaml_path}")
    root_value = Path(raw.get("path", ""))
    root = (
        root_value.resolve()
        if root_value.is_absolute()
        else (yaml_path.parent / root_value).resolve()
    )
    try:
        return DatasetConfig(
            yaml_path=yaml_path,
            root=root,
            train=raw["train"],
            val=raw["val"],
            test=raw.get("test"),
            names={int(key): str(value) for key, value in raw["names"].items()},
            allow_empty_labels=raw.get("allow_empty_labels", True),
        )
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        raise ConfigLoadError(f"invalid dataset configuration: {yaml_path}\n{exc}") from exc


def to_ultralytics_data(config: DatasetConfig) -> dict[str, object]:
    """Build a cwd-independent data mapping accepted by Ultralytics."""

    payload: dict[str, object] = {
        "path": str(config.root),
        "train": config.train,
        "val": config.val,
        "names": config.names,
    }
    if config.test is not None:
        payload["test"] = config.test
    return payload


def write_resolved_dataset_config(config: DatasetConfig, target: Path) -> Path:
    """Write a cwd-independent Ultralytics dataset YAML snapshot."""

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        yaml.safe_dump(to_ultralytics_data(config), sort_keys=False), encoding="utf-8"
    )
    return target


def _images(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(
        p for p in directory.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    )


def _label_dir(root: Path, image_relative: str) -> Path:
    parts = list(Path(image_relative).parts)
    if "images" not in parts:
        raise ConfigLoadError(
            f"image split path must contain an 'images' component: {image_relative}"
        )
    parts[parts.index("images")] = "labels"
    return root.joinpath(*parts)


class DatasetValidator:
    def __init__(self, config: DatasetConfig) -> None:
        self.config = config

    def validate(self) -> DatasetReport:
        issues: list[DatasetIssue] = []
        boxes = Counter[str]()
        class_images = Counter[str]()
        split_counts: dict[str, int] = {}
        stems_by_split: dict[str, set[str]] = defaultdict(set)
        total_images = total_boxes = empty_count = 0

        splits = {"train": self.config.train, "val": self.config.val, "test": self.config.test}
        for split, relative in splits.items():
            if relative is None:
                continue
            image_dir = self.config.root / relative
            try:
                label_dir = _label_dir(self.config.root, relative)
            except ConfigLoadError as exc:
                issues.append(
                    DatasetIssue(
                        code="invalid_split_path", path=image_dir, reason=str(exc), split=split
                    )
                )
                continue
            if not image_dir.is_dir():
                issues.append(
                    DatasetIssue(
                        code="missing_image_dir",
                        path=image_dir,
                        reason="image split directory does not exist",
                        split=split,
                    )
                )
            if not label_dir.is_dir():
                issues.append(
                    DatasetIssue(
                        code="missing_label_dir",
                        path=label_dir,
                        reason="label split directory does not exist",
                        split=split,
                    )
                )
            images = _images(image_dir)
            split_counts[split] = len(images)
            total_images += len(images)
            stem_counts = Counter(p.stem for p in images)
            for stem, count in stem_counts.items():
                if count > 1:
                    issues.append(
                        DatasetIssue(
                            code="duplicate_filename",
                            path=image_dir,
                            reason=f"stem '{stem}' occurs {count} times",
                            split=split,
                        )
                    )
            stems_by_split[split] = set(stem_counts)
            image_stems = set(stem_counts)
            for image_path in images:
                if cv2.imread(str(image_path)) is None:
                    issues.append(
                        DatasetIssue(
                            code="corrupt_image",
                            path=image_path,
                            reason="OpenCV cannot decode image",
                            split=split,
                        )
                    )
                label_path = label_dir / f"{image_path.stem}.txt"
                if not label_path.is_file():
                    issues.append(
                        DatasetIssue(
                            code="missing_label",
                            path=image_path,
                            reason=f"missing {label_path}",
                            split=split,
                        )
                    )
                    continue
                lines = [
                    line.strip()
                    for line in label_path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
                if not lines:
                    empty_count += 1
                    if not self.config.allow_empty_labels:
                        issues.append(
                            DatasetIssue(
                                code="empty_label",
                                path=label_path,
                                reason="empty labels are disabled",
                                split=split,
                            )
                        )
                    continue
                present_classes: set[int] = set()
                for number, line in enumerate(lines, 1):
                    parsed = self._parse_label(line, label_path, split, number, issues)
                    if parsed is not None:
                        class_id = parsed
                        boxes[self.config.names[class_id]] += 1
                        total_boxes += 1
                        present_classes.add(class_id)
                for class_id in present_classes:
                    class_images[self.config.names[class_id]] += 1
            if label_dir.is_dir():
                for label_path in label_dir.rglob("*.txt"):
                    if label_path.stem not in image_stems:
                        issues.append(
                            DatasetIssue(
                                code="missing_image",
                                path=label_path,
                                reason="label has no matching image",
                                split=split,
                            )
                        )

        split_names = list(stems_by_split)
        for index, left in enumerate(split_names):
            for right in split_names[index + 1 :]:
                for stem in sorted(stems_by_split[left] & stems_by_split[right]):
                    issues.append(
                        DatasetIssue(
                            code="cross_split_duplicate",
                            path=self.config.root,
                            reason=f"'{stem}' occurs in {left} and {right}",
                        )
                    )
        return DatasetReport(
            valid=not issues,
            total_images=total_images,
            total_boxes=total_boxes,
            empty_label_images=empty_count,
            images_per_class={name: class_images[name] for name in self.config.names.values()},
            boxes_per_class={name: boxes[name] for name in self.config.names.values()},
            split_images=split_counts,
            issues=issues,
        )

    def _parse_label(
        self, line: str, path: Path, split: str, number: int, issues: list[DatasetIssue]
    ) -> int | None:
        parts = line.split()
        reason: str | None = None
        class_id = -1
        try:
            if len(parts) != 5:
                raise ValueError("expected 5 fields")
            class_value, x, y, width, height = map(float, parts)
            if not class_value.is_integer():
                raise ValueError("class id must be an integer")
            class_id = int(class_value)
            if class_id not in self.config.names:
                raise ValueError(f"class id {class_id} is out of range")
            if not all(0 <= value <= 1 for value in (x, y, width, height)):
                raise ValueError("bbox values must be within [0, 1]")
            if width <= 0 or height <= 0:
                raise ValueError("bbox width and height must be positive")
        except ValueError as exc:
            reason = str(exc)
        if reason:
            issues.append(
                DatasetIssue(
                    code="invalid_label", path=path, reason=f"line {number}: {reason}", split=split
                )
            )
            return None
        return class_id
