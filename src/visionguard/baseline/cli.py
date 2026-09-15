"""Thin CLI entry points for standalone text experiments."""

import argparse
import json
from pathlib import Path

from visionguard.baseline.classifier import TextModerationBaseline
from visionguard.baseline.config import load_baseline_config
from visionguard.baseline.dataset import load_dataset, split_dataset
from visionguard.baseline.evaluator import (
    evaluate_probabilities,
    evaluate_thresholds,
    export_errors,
)
from visionguard.baseline.trainer import TextBaselineTrainer
from visionguard.core.logging import configure_logging


def main(action: str) -> int:
    configure_logging()
    parser = argparse.ArgumentParser(description=f"Text baseline: {action}")
    parser.add_argument("--config", type=Path, default=Path("configs/baseline_text.yaml"))
    parser.add_argument("--threshold", type=float)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--max-features", type=int)
    parser.add_argument("--experiment", type=Path)
    parser.add_argument("--text")
    parser.add_argument("--texts-json", type=Path, help="UTF-8 JSON array of texts")
    parser.add_argument("--data", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--threshold-sweep", action="store_true")
    args = parser.parse_args()
    if action == "split":
        if not args.data or not args.output:
            parser.error("--data and --output required")
        split_dataset(args.data, args.output, args.seed if args.seed is not None else 42)
        return 0
    config = load_baseline_config(args.config)
    raw = config.model_dump()
    for option, key in ((args.threshold, "decision_threshold"), (args.seed, "seed")):
        if option is not None:
            raw[key] = option
    if args.max_features is not None:
        raw["tfidf"]["max_features"] = args.max_features
    config = type(config).model_validate(raw)
    if action == "train":
        TextBaselineTrainer(config).train()
        return 0
    experiment = args.experiment or config.artifacts_dir / config.experiment_name
    classifier = TextModerationBaseline.load(experiment)
    if action == "infer":
        if args.texts_json:
            texts = json.loads(args.texts_json.read_text(encoding="utf-8"))
            if not isinstance(texts, list) or not all(isinstance(t, str) for t in texts):
                parser.error("--texts-json must contain a string array")
            result = classifier.predict_batch(texts, threshold=args.threshold)
        elif args.text is not None:
            result = classifier.predict(args.text, threshold=args.threshold)
        else:
            parser.error("--text or --texts-json required")
        print(result.model_dump_json(indent=2))
        return 0
    texts, labels = load_dataset(
        args.data or classifier.config.test, lowercase=classifier.config.preprocessing.lowercase
    )
    threshold = (
        args.threshold if args.threshold is not None else classifier.config.decision_threshold
    )
    probabilities = [p.probability for p in classifier.predict_batch(texts).predictions]
    target = args.output or experiment / (
        "test_metrics.json" if action == "evaluate" else "test_errors.jsonl"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    if action == "errors":
        print("error_count:", export_errors(texts, labels, probabilities, threshold, target))
    else:
        metrics = evaluate_probabilities(labels, probabilities, threshold)
        target.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(metrics, ensure_ascii=False, indent=2))
        if args.threshold_sweep:
            if args.data is None:
                parser.error("threshold sweep requires explicit --data (use validation split)")
            print(
                evaluate_thresholds(labels, probabilities, target.parent / "threshold_metrics.csv")
            )
    return 0
