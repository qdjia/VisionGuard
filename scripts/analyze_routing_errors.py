"""Export structured routing error buckets from evaluation predictions."""

import argparse
import json
from pathlib import Path

from visionguard.routing.analysis import analyze_routing_errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--no-copy-images", action="store_true")
    args = parser.parse_args()
    summary = analyze_routing_errors(
        args.predictions, args.output, copy_images=not args.no_copy_images
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
