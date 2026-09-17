"""Replay FusionEngine over saved Phase 7/8/9 review artifacts without model inference."""

import argparse
import json
from pathlib import Path

from visionguard.fusion import RiskFusionEngine, load_fusion_config
from visionguard.fusion.replay import replay_artifact_tree


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fusion-config", type=Path, default=Path("configs/fusion.yaml"))
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"fusion replay output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    engine = RiskFusionEngine(load_fusion_config(args.fusion_config))
    records = replay_artifact_tree(args.artifacts, engine)
    output.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in records),
        encoding="utf-8",
    )
    print(f"replayed={len(records)} policy={engine.version} output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
