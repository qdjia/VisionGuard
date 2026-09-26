from __future__ import annotations

import argparse
import json
from pathlib import Path

from .manager import BootstrapError, BootstrapManager


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Install the managed VisionGuard Advanced AI environment"
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--status-file", required=True, type=Path)
    parser.add_argument("--wheel", required=True, type=Path)
    parser.add_argument("--prompts", required=True, type=Path)
    parser.add_argument("--cancel-file", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = BootstrapManager(
            args.manifest,
            args.data_dir,
            args.status_file,
            args.wheel,
            args.prompts,
            args.cancel_file,
        ).install()
    except BootstrapError as exc:
        print(json.dumps({"error_code": exc.code, "message": str(exc)}))
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0
