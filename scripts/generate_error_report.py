#!/usr/bin/env python
"""Regenerate a readable report from analysis JSON artifacts."""

import argparse
import json
from pathlib import Path

from visionguard.error_analysis.attribution import load_jsonl
from visionguard.error_analysis.report import render_report
from visionguard.error_analysis.schemas import ErrorCase


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"report output already exists: {args.output}")
    summary = json.loads((args.analysis / "summary.json").read_text(encoding="utf-8"))
    recommendations = json.loads(
        (args.analysis / "recommendations.json").read_text(encoding="utf-8")
    )
    cases = [
        ErrorCase.model_validate(item) for item in load_jsonl(args.analysis / "error_cases.jsonl")
    ]
    args.output.write_text(render_report(summary, cases, recommendations, 10), encoding="utf-8")
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
