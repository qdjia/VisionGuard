"""Orchestrate systematic analysis without re-running any model."""

import json
from datetime import UTC, datetime
from pathlib import Path

import yaml

from visionguard.error_analysis.attribution import build_error_case, load_jsonl
from visionguard.error_analysis.config import ErrorAnalysisConfig
from visionguard.error_analysis.hard_cases import build_hard_cases, write_hard_case_manifest
from visionguard.error_analysis.recommendations import generate_recommendations
from visionguard.error_analysis.report import (
    render_case,
    render_report,
    render_top_errors,
    write_taxonomy_csv,
)
from visionguard.error_analysis.schemas import AnnotationStatus, GroundTruth, SampleMetadata
from visionguard.error_analysis.statistics import calculate_statistics
from visionguard.error_analysis.visualization import save_error_visualization


class ErrorAnalyzer:
    def __init__(self, config: ErrorAnalysisConfig) -> None:
        self.config = config

    def analyze(
        self,
        records_path: str | Path,
        *,
        manifest_path: str | Path | None = None,
        output_dir: str | Path | None = None,
    ) -> Path:
        records = self._records(records_path)
        labels = self._labels(manifest_path) if manifest_path else {}
        cases = []
        for record in records:
            label = labels.get(str(record.get("image")), {})
            raw_gt = (
                label.get("ground_truth")
                or {
                    key: label.get(key)
                    for key in (
                        "risk_level",
                        "categories",
                        "text",
                        "objects",
                        "requires_manual_review",
                    )
                    if key in label
                }
                or record.get("ground_truth", {})
            )
            ground_truth = GroundTruth.model_validate(raw_gt)
            raw_metadata = label.get("metadata", {})
            if not raw_metadata and record.get("ground_truth"):
                raw_metadata = {"annotation_status": AnnotationStatus.VERIFIED}
            metadata = SampleMetadata.model_validate(raw_metadata)
            record["ground_truth"] = ground_truth.model_dump(mode="json")
            case = build_error_case(record, ground_truth, metadata, self.config)
            if case:
                cases.append(case)
        output = self._output(output_dir)
        summary = calculate_statistics(records, cases, self.config)
        recommendations = generate_recommendations(cases)
        hard_cases = build_hard_cases(cases, self.config)
        summary["hard_case_count"] = len(hard_cases)
        summary["regression_set_count"] = sum(case.eligible_for_regression for case in hard_cases)
        self._write_json(output / "summary.json", summary)
        self._write_json(output / "recommendations.json", recommendations)
        self._write_jsonl(
            output / "error_cases.jsonl", [case.model_dump(mode="json") for case in cases]
        )
        write_hard_case_manifest(hard_cases, output / "hard_cases.jsonl")
        write_taxonomy_csv(cases, output / "failure_taxonomy.csv")
        (output / "top_errors.md").write_text(
            render_top_errors(cases, self.config.report.top_error_count), encoding="utf-8"
        )
        (output / "error_analysis_report.md").write_text(
            render_report(
                summary, cases, recommendations, self.config.report.low_sample_warning_threshold
            ),
            encoding="utf-8",
        )
        (output / "config.yaml").write_text(
            yaml.safe_dump(
                {"error_analysis": self.config.model_dump(mode="json")}, sort_keys=False
            ),
            encoding="utf-8",
        )
        for case in cases:
            directory = output / "cases" / case.case_id
            directory.mkdir(parents=True)
            self._write_json(directory / "trace.json", case.model_dump(mode="json"))
            (directory / "case.md").write_text(render_case(case), encoding="utf-8")
            save_error_visualization(case, directory / "visualization.jpg")
        return output

    @staticmethod
    def _labels(path: str | Path) -> dict[str, dict]:
        source = Path(path).expanduser().resolve()
        labels = {}
        for row in load_jsonl(source):
            labels[str(row["image"])] = row
            labels[Path(str(row["image"])).name] = row
        return labels

    @staticmethod
    def _records(path: str | Path) -> list[dict]:
        source = Path(path).expanduser().resolve()
        if source.is_file():
            return load_jsonl(source)
        records = []
        for artifact in sorted(source.rglob("review_result.json")):
            result = json.loads(artifact.read_text(encoding="utf-8"))
            image = result.get("image", {}).get("source_path") or artifact.parent.name
            records.append(
                {
                    "image": Path(str(image)).name,
                    "image_path": image,
                    "result": result,
                    "artifact": str(artifact),
                }
            )
        if not records:
            raise ValueError(f"no JSONL file or review_result.json artifacts found: {source}")
        return records

    def _output(self, requested: str | Path | None) -> Path:
        if requested:
            output = Path(requested).expanduser().resolve()
        else:
            name = f"{self.config.experiment_name}_{datetime.now(UTC):%Y%m%dT%H%M%SZ}"
            output = self.config.output_root.expanduser().resolve() / name
        if output.exists() and any(output.iterdir()):
            raise FileExistsError(f"error-analysis output is not empty: {output}")
        output.mkdir(parents=True, exist_ok=True)
        return output

    @staticmethod
    def _write_json(path: Path, value) -> None:
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _write_jsonl(path: Path, values: list[dict]) -> None:
        path.write_text(
            "".join(json.dumps(value, ensure_ascii=False) + "\n" for value in values),
            encoding="utf-8",
        )
