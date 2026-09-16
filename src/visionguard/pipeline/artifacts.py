"""Per-run artifact persistence kept independent from inference orchestration."""

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from visionguard.detection.visualization import save_visualization
from visionguard.ocr.visualization import save_ocr_visualization
from visionguard.pipeline.config import PipelineConfig
from visionguard.pipeline.exceptions import ArtifactSaveError
from visionguard.pipeline.schemas import ReviewResult


def _json_value(value: Any) -> Any:
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else value


def _save_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(_json_value(value), ensure_ascii=False, indent=2), encoding="utf-8")


class PipelineArtifactStore:
    def __init__(self, config: PipelineConfig) -> None:
        self.config = config

    def directory_for(self, run_id: str) -> Path:
        return self.config.artifact_root / run_id

    def save(self, result: ReviewResult, image: np.ndarray) -> Path:
        directory = self.directory_for(result.run_id)
        try:
            directory.mkdir(parents=True, exist_ok=False)
            _save_json(directory / "input_metadata.json", result.image)
            if result.routing is not None:
                _save_json(directory / "routing.json", result.routing)
            if self.config.save_intermediate_json:
                for filename, value in (
                    ("detection.json", result.detection),
                    ("ocr.json", result.ocr),
                    ("baseline.json", result.baseline),
                    ("vlm.json", result.vlm),
                ):
                    if value is not None:
                        _save_json(directory / filename, value)
                failures = {
                    name: status.model_dump(mode="json")
                    for name, status in result.module_status.items()
                    if status.status == "failed"
                }
                if failures:
                    _save_json(directory / "error.json", {"run_id": result.run_id, **failures})
            if self.config.save_visualizations:
                visualizations = directory / "visualizations"
                if result.detection is not None:
                    save_visualization(
                        image,
                        result.detection.detections,
                        visualizations / "detection.jpg",
                    )
                if result.ocr is not None:
                    save_ocr_visualization(
                        image,
                        result.ocr.blocks,
                        visualizations / "ocr.jpg",
                    )
            if self.config.save_input_copy:
                if not cv2.imwrite(str(directory / "input.jpg"), image):
                    raise OSError("OpenCV failed to save the input copy")
            _save_json(directory / "timing.json", result.timing)
            _save_json(directory / "review_result.json", result)
            return directory.resolve()
        except Exception as exc:
            raise ArtifactSaveError(
                f"failed to save pipeline artifacts under {directory}",
                run_id=result.run_id,
                cause=exc,
            ) from exc

    @staticmethod
    def refresh_result(directory: Path, result: ReviewResult) -> None:
        """Refresh final summaries after measured artifact status/timing is known."""

        _save_json(directory / "timing.json", result.timing)
        _save_json(directory / "review_result.json", result)
