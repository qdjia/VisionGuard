"""Replay one evidence set through the five Phase 9 ablation profiles."""

import argparse
import csv
import json
from pathlib import Path

from visionguard.fusion import RiskFusionEngine, load_fusion_config
from visionguard.fusion.evaluator import calculate_fusion_metrics, replay_records
from visionguard.fusion.replay import ABLATION_PROFILES, load_fusion_records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fusion-config", type=Path, default=Path("configs/fusion.yaml"))
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"ablation output is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    records = load_fusion_records(args.records)
    engine = RiskFusionEngine(load_fusion_config(args.fusion_config))
    reports = []
    for profile in ABLATION_PROFILES:
        replayed = replay_records(records, engine, profile=profile)
        reports.append(
            {
                "profile": profile,
                "fusion_policy_version": engine.version,
                **calculate_fusion_metrics(replayed),
            }
        )
    (output / "ablation.json").write_text(
        json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (output / "ablation.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(reports[0]))
        writer.writeheader()
        writer.writerows(reports)
    print(json.dumps(reports, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
