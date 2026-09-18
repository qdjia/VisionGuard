#!/usr/bin/env python
"""Build a content-hash-deduplicated hard-case manifest."""

import argparse
import json
from pathlib import Path

from visionguard.error_analysis.attribution import load_jsonl
from visionguard.error_analysis.config import load_error_analysis_config
from visionguard.error_analysis.hard_cases import (
    build_hard_cases,
    merge_hard_cases,
    write_hard_case_manifest,
)
from visionguard.error_analysis.schemas import ErrorCase, HardCaseRecord


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--errors", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/error_analysis.yaml"))
    parser.add_argument("--output", type=Path, default=Path("data/hard_cases/manifest.jsonl"))
    args = parser.parse_args()
    cases = [ErrorCase.model_validate(item) for item in load_jsonl(args.errors)]
    hard_cases = build_hard_cases(cases, load_error_analysis_config(args.config))
    if args.output.is_file():
        existing = [HardCaseRecord.model_validate(item) for item in load_jsonl(args.output)]
        hard_cases = merge_hard_cases(existing, hard_cases)
    output = write_hard_case_manifest(hard_cases, args.output)
    print(json.dumps({"hard_cases": len(hard_cases), "output": str(output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
