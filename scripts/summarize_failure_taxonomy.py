#!/usr/bin/env python
"""Export the complete failure taxonomy with observed counts."""

import argparse
from pathlib import Path

from visionguard.error_analysis.attribution import load_jsonl
from visionguard.error_analysis.report import write_taxonomy_csv
from visionguard.error_analysis.schemas import ErrorCase


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--errors", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"taxonomy output already exists: {args.output}")
    cases = [ErrorCase.model_validate(item) for item in load_jsonl(args.errors)]
    print(write_taxonomy_csv(cases, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
