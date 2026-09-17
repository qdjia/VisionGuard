"""Export false-low, conflict, boundary, failure, and routing-override fusion cases."""

import argparse
import json
from pathlib import Path

from visionguard.fusion.analysis import analyze_fusion_errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--no-copy-images", action="store_true")
    args = parser.parse_args()
    summary = analyze_fusion_errors(args.records, args.output, copy_images=not args.no_copy_images)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
