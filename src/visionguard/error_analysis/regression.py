"""Live hard-case regression runner; unlike replay, this deliberately executes models."""

import json
from pathlib import Path

from visionguard.error_analysis.attribution import attribute_record
from visionguard.error_analysis.config import ErrorAnalysisConfig
from visionguard.error_analysis.schemas import (
    AnnotationStatus,
    HardCaseRecord,
    RegressionOutcome,
    RegressionRecord,
    SampleMetadata,
)


def run_hard_case_regression(
    pipeline, cases: list[HardCaseRecord], config: ErrorAnalysisConfig
) -> list[RegressionRecord]:
    results = []
    for case in cases:
        if not case.eligible_for_regression:
            results.append(
                RegressionRecord(
                    case_id=case.case_id,
                    image=case.image,
                    outcome=RegressionOutcome.NOT_EVALUABLE,
                    historical_failure=case.primary_failure,
                    message="case is not verified/eligible",
                )
            )
            continue
        try:
            current = pipeline.run(case.image).model_dump(mode="json")
            record = {
                "image": case.image,
                "ground_truth": case.ground_truth.model_dump(mode="json"),
                "result": current,
            }
            attribution = attribute_record(
                record,
                case.ground_truth,
                SampleMetadata(annotation_status=AnnotationStatus.VERIFIED),
                config,
            )
            failures = attribution.observed_failures if attribution else []
            outcome = (
                RegressionOutcome.FIXED
                if not failures
                else RegressionOutcome.STILL_FAILING
                if case.primary_failure in failures
                else RegressionOutcome.NEW_FAILURE
            )
            results.append(
                RegressionRecord(
                    case_id=case.case_id,
                    image=case.image,
                    outcome=outcome,
                    historical_failure=case.primary_failure,
                    current_failures=failures,
                    current_result=current,
                )
            )
        except Exception as exc:  # boundary converts provider errors to a regression record
            results.append(
                RegressionRecord(
                    case_id=case.case_id,
                    image=case.image,
                    outcome=RegressionOutcome.NEW_FAILURE,
                    historical_failure=case.primary_failure,
                    message=f"{type(exc).__name__}: {exc}",
                )
            )
    return results


def load_hard_cases(path: str | Path) -> list[HardCaseRecord]:
    source = Path(path).resolve()
    cases = [
        HardCaseRecord.model_validate(json.loads(line))
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    for case in cases:
        image = Path(case.image)
        if not image.is_absolute():
            case.image = str((source.parent / image).resolve())
    return cases


def save_regression(results: list[RegressionRecord], output: str | Path) -> dict:
    target = Path(output).resolve()
    if target.exists():
        raise FileExistsError(f"regression output already exists: {target}")
    target.mkdir(parents=True)
    (target / "regression_results.jsonl").write_text(
        "".join(item.model_dump_json() + "\n" for item in results), encoding="utf-8"
    )
    counts = {
        outcome.value: sum(item.outcome == outcome for item in results)
        for outcome in RegressionOutcome
    }
    summary = {"total": len(results), "outcomes": counts, "models_executed": True}
    (target / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
