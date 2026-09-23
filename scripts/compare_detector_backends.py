"""Compare Ultralytics/PyTorch and native ONNX detector outputs and latency."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from time import perf_counter

from visionguard.config import load_config
from visionguard.detection import OnnxYoloDetector, YOLODetector
from visionguard.schemas import BoundingBox, Detection


def iou(left: BoundingBox, right: BoundingBox) -> float:
    x1 = max(left.x1, right.x1)
    y1 = max(left.y1, right.y1)
    x2 = min(left.x2, right.x2)
    y2 = min(left.y2, right.y2)
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    left_area = (left.x2 - left.x1) * (left.y2 - left.y1)
    right_area = (right.x2 - right.x1) * (right.y2 - right.y1)
    union = left_area + right_area - intersection
    return intersection / union if union else 0.0


def match_detections(
    reference: list[Detection], candidate: list[Detection]
) -> tuple[list[dict], int, int]:
    unmatched = set(range(len(candidate)))
    matches = []
    for expected in reference:
        options = [
            (iou(expected.bbox, candidate[index].bbox), index)
            for index in unmatched
            if candidate[index].class_id == expected.class_id
        ]
        if not options:
            continue
        overlap, index = max(options)
        unmatched.remove(index)
        actual = candidate[index]
        matches.append(
            {
                "class_id": expected.class_id,
                "iou": overlap,
                "confidence_delta": abs(expected.confidence - actual.confidence),
            }
        )
    return matches, len(reference) - len(matches), len(unmatched)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/detector.yaml"))
    parser.add_argument("--pytorch-model", type=Path, required=True)
    parser.add_argument("--onnx-model", type=Path, required=True)
    parser.add_argument("--images", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--conf-threshold", type=float, default=0.25)
    parser.add_argument("--onnx-provider", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--minimum-class-match", type=float, default=1.0)
    parser.add_argument("--minimum-iou", type=float, default=0.99)
    parser.add_argument("--maximum-confidence-delta", type=float, default=0.001)
    args = parser.parse_args()

    base = load_config(args.config).detection.model_copy(
        update={
            "model_path": args.pytorch_model.resolve(strict=True),
            "device": "cpu",
            "half_precision": False,
            "warmup_enabled": False,
            "conf_threshold": args.conf_threshold,
        }
    )
    started = perf_counter()
    reference = YOLODetector(base)
    reference_load_ms = (perf_counter() - started) * 1000
    started = perf_counter()
    candidate = OnnxYoloDetector(
        base.model_copy(
            update={
                "provider": "onnx",
                "model_path": args.onnx_model.resolve(strict=True),
                "onnx_execution_provider": args.onnx_provider,
            }
        )
    )
    candidate_load_ms = (perf_counter() - started) * 1000

    samples = []
    all_matches = []
    reference_latency = []
    candidate_latency = []
    missing = extra = reference_count = candidate_count = 0
    for image in args.images:
        expected = reference.predict(image)
        actual = candidate.predict(image)
        matches, sample_missing, sample_extra = match_detections(
            expected.detections, actual.detections
        )
        all_matches.extend(matches)
        missing += sample_missing
        extra += sample_extra
        reference_count += len(expected.detections)
        candidate_count += len(actual.detections)
        reference_latency.append(expected.timing.total_ms)
        candidate_latency.append(actual.timing.total_ms)
        samples.append(
            {
                "image": image.as_posix(),
                "reference_count": len(expected.detections),
                "candidate_count": len(actual.detections),
                "matched": len(matches),
                "missing": sample_missing,
                "extra": sample_extra,
                "minimum_iou": min((item["iou"] for item in matches), default=None),
                "maximum_confidence_delta": max(
                    (item["confidence_delta"] for item in matches), default=None
                ),
                "reference_latency_ms": expected.timing.total_ms,
                "candidate_latency_ms": actual.timing.total_ms,
            }
        )
    denominator = max(reference_count, candidate_count)
    class_match_rate = len(all_matches) / denominator if denominator else 1.0
    minimum_iou = min((item["iou"] for item in all_matches), default=None)
    maximum_confidence_delta = max((item["confidence_delta"] for item in all_matches), default=None)
    acceptance = {
        "class_match_rate": class_match_rate >= args.minimum_class_match,
        "bbox_iou": minimum_iou is None or minimum_iou >= args.minimum_iou,
        "confidence_delta": (
            maximum_confidence_delta is None
            or maximum_confidence_delta <= args.maximum_confidence_delta
        ),
    }
    report = {
        "thresholds": {
            "confidence": args.conf_threshold,
            "minimum_class_match": args.minimum_class_match,
            "minimum_iou": args.minimum_iou,
            "maximum_confidence_delta": args.maximum_confidence_delta,
        },
        "load_ms": {"pytorch": reference_load_ms, "onnx": candidate_load_ms},
        "latency_ms": {
            "pytorch_mean": mean(reference_latency),
            "onnx_mean": mean(candidate_latency),
        },
        "summary": {
            "samples": len(samples),
            "reference_detections": reference_count,
            "candidate_detections": candidate_count,
            "matched": len(all_matches),
            "missing": missing,
            "extra": extra,
            "class_match_rate": class_match_rate,
            "minimum_iou": minimum_iou,
            "maximum_confidence_delta": maximum_confidence_delta,
            "non_empty_evidence": bool(all_matches),
            "accepted": all(acceptance.values()),
            "acceptance": acceptance,
        },
        "samples": samples,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
