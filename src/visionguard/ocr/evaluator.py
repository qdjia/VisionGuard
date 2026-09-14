"""Lightweight OCR Character Error Rate evaluation."""

import json
import shutil
from pathlib import Path

from pydantic import Field

from visionguard.ocr.engine import OCREngine
from visionguard.schemas.common import SchemaModel


def levenshtein_distance(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for row, left_char in enumerate(left, 1):
        current = [row]
        for column, right_char in enumerate(right, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[column] + 1,
                    previous[column - 1] + (left_char != right_char),
                )
            )
        previous = current
    return previous[-1]


def character_error_rate(prediction: str, ground_truth: str) -> float:
    if not ground_truth:
        return 0.0 if not prediction else 1.0
    return levenshtein_distance(prediction, ground_truth) / len(ground_truth)


class OCRSampleMetric(SchemaModel):
    image: Path
    ground_truth: str
    prediction: str
    cer: float = Field(ge=0)


class OCREvaluationResult(SchemaModel):
    total_samples: int = Field(ge=0)
    average_cer: float = Field(ge=0)
    per_sample: list[OCRSampleMetric]


class OCREvaluator:
    def __init__(self, engine: OCREngine) -> None:
        self.engine = engine

    def evaluate_jsonl(
        self,
        manifest: str | Path,
        output_path: str | Path,
        *,
        error_threshold: float = 0.3,
    ) -> OCREvaluationResult:
        manifest_path = Path(manifest).expanduser().resolve()
        samples: list[OCRSampleMetric] = []
        error_dir = Path(output_path).expanduser().resolve().parent / "error_cases"
        for line in manifest_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            image = Path(item["image"])
            image = image if image.is_absolute() else (manifest_path.parent / image).resolve()
            prediction = self.engine.recognize(image).full_text
            metric = OCRSampleMetric(
                image=image,
                ground_truth=str(item["text"]),
                prediction=prediction,
                cer=character_error_rate(prediction, str(item["text"])),
            )
            samples.append(metric)
            if metric.cer >= error_threshold:
                error_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(image, error_dir / image.name)
                (error_dir / f"{image.stem}.json").write_text(
                    metric.model_dump_json(indent=2), encoding="utf-8"
                )
        result = OCREvaluationResult(
            total_samples=len(samples),
            average_cer=sum(sample.cer for sample in samples) / len(samples) if samples else 0,
            per_sample=samples,
        )
        target = Path(output_path).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        return result
