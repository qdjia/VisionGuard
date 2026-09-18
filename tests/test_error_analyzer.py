import json
from pathlib import Path
from uuid import uuid4

import pytest

from visionguard.error_analysis import ErrorAnalyzer, load_error_analysis_config


def test_report_generation_partial_gt_and_no_overwrite() -> None:
    root = Path("artifacts/error_analysis/test_runs") / uuid4().hex
    root.mkdir(parents=True)
    records = root / "records.jsonl"
    records.write_text(
        json.dumps(
            {
                "image": "sample.png",
                "ground_truth": {"risk_level": "high"},
                "decision": {
                    "risk_level": "low",
                    "categories": [],
                    "requires_manual_review": False,
                },
                "result": {
                    "run_id": "a" * 32,
                    "review_status": "completed",
                    "module_status": {},
                    "routing": {"route": "fast_path", "reason_codes": []},
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output = root / "analysis"
    analyzer = ErrorAnalyzer(load_error_analysis_config("configs/error_analysis.yaml"))
    analyzer.analyze(records, output_dir=output)
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["false_low_count"] == 1
    assert summary["hard_case_count"] == 1
    assert (output / "error_analysis_report.md").is_file()
    assert (output / "top_errors.md").is_file()
    with pytest.raises(FileExistsError):
        analyzer.analyze(records, output_dir=output)
