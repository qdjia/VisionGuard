#!/usr/bin/env python
"""Validate the locked real-image regression manifest and local image assets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from visionguard.evaluation.historical import (  # noqa: E402
    HistoricalImageRecord,
    coverage,
    load_jsonl,
    validate_resolved,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "data/regression/real_image_manifest.jsonl",
    )
    parser.add_argument("--asset-dir", type=Path, required=True)
    args = parser.parse_args()
    records = load_jsonl(args.manifest, HistoricalImageRecord)
    errors = validate_resolved(records, args.asset_dir)
    unverified = [item.case_id for item in records if item.annotation_status != "verified"]
    if unverified:
        errors.append(f"annotations not verified: {', '.join(unverified)}")
    report = {**coverage(records), "valid": not errors, "errors": errors}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
