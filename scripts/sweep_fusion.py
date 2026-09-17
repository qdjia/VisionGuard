"""Offline sweep of risk boundaries and weight sets; never edits fusion.yaml."""

import argparse
import csv
import json
from pathlib import Path

from visionguard.fusion import FusionConfig, RiskFusionEngine, load_fusion_config
from visionguard.fusion.evaluator import calculate_fusion_metrics, replay_records
from visionguard.fusion.replay import load_fusion_records


def _weight_set(value: str) -> tuple[float, float, float]:
    parts = tuple(float(item) for item in value.split(","))
    if len(parts) != 3 or any(item < 0 for item in parts) or sum(parts) <= 0:
        raise argparse.ArgumentTypeError("weight sets must be visual,text,vlm non-negative triples")
    return parts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fusion-config", type=Path, default=Path("configs/fusion.yaml"))
    parser.add_argument("--low-max-values", type=float, nargs="+", default=[0.25, 0.30, 0.35])
    parser.add_argument("--medium-max", type=float, default=0.70)
    parser.add_argument(
        "--weight-sets",
        type=_weight_set,
        nargs="+",
        default=[(0.25, 0.20, 0.55), (0.30, 0.25, 0.45)],
    )
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"fusion sweep output is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    records = load_fusion_records(args.records)
    base = load_fusion_config(args.fusion_config)
    reports = []
    for low_max in args.low_max_values:
        for visual, text, vlm in args.weight_sets:
            values = base.model_dump()
            values["risk_mapping"] = {"low_max": low_max, "medium_max": args.medium_max}
            values["weights"] = {"visual": visual, "text": text, "vlm": vlm}
            config = FusionConfig.model_validate(values)
            replayed = replay_records(records, RiskFusionEngine(config))
            reports.append(
                {
                    "low_max": low_max,
                    "medium_max": args.medium_max,
                    "visual_weight": visual,
                    "text_weight": text,
                    "vlm_weight": vlm,
                    "fusion_policy_version": base.version,
                    **calculate_fusion_metrics(replayed),
                }
            )
    with (output / "fusion_sweep.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(reports[0]))
        writer.writeheader()
        writer.writerows(reports)
    (output / "summary.json").write_text(
        json.dumps(
            {
                "analysis_only": True,
                "formal_config_modified": False,
                "fusion_policy_version": base.version,
                "results": reports,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps(reports, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
