#!/usr/bin/env python
"""Replay routing and fusion from stored signals; no models are loaded."""

import argparse
import json
from pathlib import Path

from visionguard.error_analysis.replay import replay_from_files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--routing-config", type=Path, default=Path("configs/routing.yaml"))
    parser.add_argument("--fusion-config", type=Path, default=Path("configs/fusion.yaml"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            replay_from_files(args.records, args.routing_config, args.fusion_config, args.output),
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
