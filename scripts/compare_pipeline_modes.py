"""Compare full and cascaded modes over one manifest and one shared model set."""

import argparse
import csv
import json
from pathlib import Path

from visionguard.core.logging import configure_logging
from visionguard.pipeline import build_pipeline_pair
from visionguard.routing.evaluator import evaluate_routing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--full-config", type=Path, default=Path("configs/pipeline.yaml"))
    parser.add_argument(
        "--cascaded-config", type=Path, default=Path("configs/pipeline_cascaded.yaml")
    )
    parser.add_argument("--routing-config", type=Path, default=Path("configs/routing.yaml"))
    parser.add_argument("--detector-config", type=Path, default=Path("configs/detector.yaml"))
    parser.add_argument("--ocr-config", type=Path, default=Path("configs/ocr.yaml"))
    parser.add_argument("--baseline-config", type=Path, default=Path("configs/baseline_text.yaml"))
    parser.add_argument("--vlm-config", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=Path("configs/moderation_policy.yaml"))
    parser.add_argument("--fusion-config", type=Path, default=Path("configs/fusion.yaml"))
    args = parser.parse_args()
    configure_logging()
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"comparison output is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    full, cascaded = build_pipeline_pair(
        full_pipeline_config=args.full_config,
        cascaded_pipeline_config=args.cascaded_config,
        routing_config=args.routing_config,
        detector_config=args.detector_config,
        ocr_config=args.ocr_config,
        baseline_config=args.baseline_config,
        vlm_config=args.vlm_config,
        policy=args.policy,
        fusion_config=args.fusion_config,
    )
    summaries = {
        "full": evaluate_routing(full, args.manifest, output / "full"),
        "cascaded": evaluate_routing(cascaded, args.manifest, output / "cascaded"),
    }
    comparison = {mode: summary["metrics"] for mode, summary in summaries.items()}
    (output / "comparison.json").write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    fields = ["mode", *next(iter(comparison.values())).keys()]
    with (output / "comparison.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for mode, metrics in comparison.items():
            writer.writerow({"mode": mode, **metrics})
    print(json.dumps(comparison, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
