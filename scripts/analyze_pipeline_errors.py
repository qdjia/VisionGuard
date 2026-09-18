#!/usr/bin/env python
"""Analyze stored VisionGuard records without running models."""

import argparse
from pathlib import Path

from visionguard.error_analysis import ErrorAnalyzer, load_error_analysis_config


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--config", type=Path, default=Path("configs/error_analysis.yaml"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = ErrorAnalyzer(load_error_analysis_config(args.config)).analyze(
        args.records, manifest_path=args.manifest, output_dir=args.output
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
