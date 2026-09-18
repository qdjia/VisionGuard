"""Hard-case and regression-set construction with content-hash deduplication."""

import json
from pathlib import Path

from visionguard.error_analysis.config import ErrorAnalysisConfig
from visionguard.error_analysis.schemas import AnnotationStatus, ErrorCase, HardCaseRecord
from visionguard.error_analysis.taxonomy import FailureType


def build_hard_cases(cases: list[ErrorCase], config: ErrorAnalysisConfig) -> list[HardCaseRecord]:
    selected: dict[str, HardCaseRecord] = {}
    for case in cases:
        include = case.severity in config.hard_cases.include_severities or (
            config.hard_cases.include_boundary_cases
            and FailureType.NEAR_DECISION_BOUNDARY in case.observed_failures
        )
        if not include:
            continue
        key = case.image_hash
        prioritized = (
            case.severity in config.hard_cases.regression_severities
            or FailureType.NEAR_DECISION_BOUNDARY in case.observed_failures
        )
        eligible = prioritized and (
            not config.hard_cases.require_verified_annotation
            or case.metadata.annotation_status == AnnotationStatus.VERIFIED
        )
        if key not in selected:
            selected[key] = HardCaseRecord(
                case_id=case.case_id,
                image=case.image,
                image_hash=case.image_hash,
                primary_failure=case.primary_failure,
                failure_types=case.observed_failures,
                severity=case.severity,
                ground_truth=case.ground_truth,
                annotation_status=case.metadata.annotation_status,
                difficulty=case.metadata.difficulty,
                notes=case.metadata.notes,
                eligible_for_regression=eligible,
                source_run_ids=[case.run_id] if case.run_id else [],
            )
        elif case.run_id and case.run_id not in selected[key].source_run_ids:
            selected[key].source_run_ids.append(case.run_id)
            selected[key].failure_types = list(
                dict.fromkeys([*selected[key].failure_types, *case.observed_failures])
            )
    return list(selected.values())


def merge_hard_cases(
    existing: list[HardCaseRecord], incoming: list[HardCaseRecord]
) -> list[HardCaseRecord]:
    """Merge history by image hash without duplicating image content."""
    merged = {case.image_hash: case.model_copy(deep=True) for case in existing}
    for case in incoming:
        if case.image_hash not in merged:
            merged[case.image_hash] = case.model_copy(deep=True)
            continue
        current = merged[case.image_hash]
        current.failure_types = list(dict.fromkeys([*current.failure_types, *case.failure_types]))
        current.source_run_ids = list(
            dict.fromkeys([*current.source_run_ids, *case.source_run_ids])
        )
        current.eligible_for_regression |= case.eligible_for_regression
        if case.notes and case.notes != current.notes:
            current.notes = "; ".join(filter(None, (current.notes, case.notes)))
    return list(merged.values())


def write_hard_case_manifest(cases: list[HardCaseRecord], path: str | Path) -> Path:
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "".join(
            json.dumps(case.model_dump(mode="json"), ensure_ascii=False) + "\n" for case in cases
        ),
        encoding="utf-8",
    )
    return target
