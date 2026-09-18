#!/usr/bin/env python
"""Regenerate a Markdown report from machine-readable benchmark summaries."""

import argparse

from visionguard.benchmarking import generate_performance_report, load_summaries


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input", required=True, help="Benchmark root containing summary.json files"
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = generate_performance_report(load_summaries(args.input), args.output)
    print(report)


if __name__ == "__main__":
    main()
