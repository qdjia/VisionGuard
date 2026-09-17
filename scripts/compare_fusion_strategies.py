"""Replay identical model outputs through VLM-only, hard-rule, and weighted fusion."""

import argparse
import csv
import json
from pathlib import Path

from visionguard.fusion import FusionConfig, RiskFusionEngine, load_fusion_config
from visionguard.fusion.evaluator import calculate_fusion_metrics, replay_records
from visionguard.fusion.replay import load_fusion_records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fusion-config", type=Path, default=Path("configs/fusion.yaml"))
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"strategy comparison output is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    records = load_fusion_records(args.records)
    base = load_fusion_config(args.fusion_config)
    reports = []
    for strategy in ("vlm_only", "hard_rule", "weighted"):
        config = FusionConfig.model_validate({**base.model_dump(), "strategy": strategy})
        replayed = replay_records(
            records,
            RiskFusionEngine(config),
            profile="vlm_only" if strategy == "vlm_only" else "full",
        )
        metrics = calculate_fusion_metrics(replayed)
        reports.append({"strategy": strategy, "fusion_policy_version": base.version, **metrics})
        (output / f"{strategy}.jsonl").write_text(
            "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in replayed),
            encoding="utf-8",
        )
    (output / "comparison.json").write_text(
        json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (output / "comparison.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(reports[0]))
        writer.writeheader()
        writer.writerows(reports)
    print(json.dumps(reports, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
