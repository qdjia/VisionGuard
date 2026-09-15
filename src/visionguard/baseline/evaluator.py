"""Binary metrics, validation-only threshold analysis, and FP/FN exports."""

import csv
import json
from pathlib import Path

from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
    roc_auc_score,
)


def evaluate_probabilities(labels: list[int], probabilities, threshold: float) -> dict:
    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be within [0,1]")
    if not labels or len(labels) != len(probabilities) or not set(labels).issubset({0, 1}):
        raise ValueError("nonempty aligned binary labels/probabilities required")
    predicted = [int(p >= threshold) for p in probabilities]
    precision, recall, f1, _ = precision_recall_fscore_support(
        labels, predicted, average="binary", zero_division=0
    )
    tn, fp, fn, tp = confusion_matrix(labels, predicted, labels=[0, 1]).ravel()
    return {
        "threshold": threshold,
        "accuracy": float(accuracy_score(labels, predicted)),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "roc_auc": float(roc_auc_score(labels, probabilities)) if len(set(labels)) == 2 else None,
        "pr_auc_average_precision": (
            float(average_precision_score(labels, probabilities)) if 1 in labels else None
        ),
        "confusion_matrix": dict(
            zip(["TN", "FP", "FN", "TP"], map(int, [tn, fp, fn, tp]), strict=True)
        ),
        "per_class": classification_report(
            labels,
            predicted,
            labels=[0, 1],
            target_names=["normal", "sensitive"],
            output_dict=True,
            zero_division=0,
        ),
    }


def evaluate_thresholds(labels, probabilities, output: Path, recall_target: float = 0.9) -> dict:
    rows = [
        {key: metrics[key] for key in ("threshold", "precision", "recall", "f1")}
        for metrics in (
            evaluate_probabilities(labels, probabilities, step / 100) for step in range(10, 91, 5)
        )
    ]
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    eligible = [row for row in rows if row["recall"] >= recall_target]
    return {
        "best_f1_threshold": max(rows, key=lambda row: row["f1"])["threshold"],
        "recall_target": recall_target,
        "best_precision_at_recall_target": max(eligible, key=lambda r: r["precision"])
        if eligible
        else None,
        "formal_threshold_unchanged": True,
    }


def export_errors(texts, labels, probabilities, threshold: float, output: Path) -> int:
    count = 0
    with output.open("w", encoding="utf-8") as stream:
        for text, label, probability in zip(texts, labels, probabilities, strict=True):
            prediction = int(probability >= threshold)
            if prediction != label:
                count += 1
                stream.write(
                    json.dumps(
                        {
                            "text": text,
                            "ground_truth": label,
                            "prediction": prediction,
                            "probability": float(probability),
                            "error_type": "false_negative" if label else "false_positive",
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
    return count
