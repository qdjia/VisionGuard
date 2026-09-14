"""Export lightweight IoU-matched detector error cases."""

import argparse
from pathlib import Path

from visionguard.detection.error_cases import export_error_cases


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--experiment-name", required=True)
    parser.add_argument("--split", choices=("val", "test"), default="val")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--output-root", type=Path, default=Path("artifacts/error_analysis"))
    args = parser.parse_args()
    manifest = export_error_cases(
        args.checkpoint,
        args.data,
        args.output_root / args.experiment_name,
        split=args.split,
        device=args.device,
    )
    print(f"saved error cases to {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
