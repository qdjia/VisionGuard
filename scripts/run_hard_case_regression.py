#!/usr/bin/env python
"""Run live cascaded inference over verified hard cases."""

import argparse
import json
from pathlib import Path

from visionguard.benchmarking.bootstrap import add_model_arguments, build_one
from visionguard.error_analysis.config import load_error_analysis_config
from visionguard.error_analysis.regression import (
    load_hard_cases,
    run_hard_case_regression,
    save_regression,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/error_analysis.yaml"))
    parser.add_argument("--pipeline-mode", choices=("full", "cascaded"), default="cascaded")
    parser.add_argument("--output", type=Path, required=True)
    add_model_arguments(parser)
    args = parser.parse_args()
    pipeline, _, _ = build_one(args, args.pipeline_mode)
    results = run_hard_case_regression(
        pipeline, load_hard_cases(args.manifest), load_error_analysis_config(args.config)
    )
    print(json.dumps(save_regression(results, args.output), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
