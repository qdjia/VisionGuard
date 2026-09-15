"""Fit train-only features and GBDT, preserve reproducible experiment artifacts."""

import logging
from time import perf_counter

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.feature_extraction.text import TfidfVectorizer

from visionguard.baseline.classifier import TextModerationBaseline
from visionguard.baseline.config import BaselineConfig
from visionguard.baseline.dataset import load_dataset, validate_splits
from visionguard.baseline.evaluator import (
    evaluate_probabilities,
    evaluate_thresholds,
    export_errors,
)
from visionguard.baseline.persistence import save_models
from visionguard.training.experiment import ExperimentManager

LOGGER = logging.getLogger(__name__)


class TextBaselineTrainer:
    def __init__(self, config: BaselineConfig) -> None:
        self.config = config

    def train(self) -> TextModerationBaseline:
        config = self.config
        splits = {
            name: load_dataset(getattr(config, name), lowercase=config.preprocessing.lowercase)
            for name in ("train", "val", "test")
        }
        validate_splits(splits)
        experiment = ExperimentManager(config)
        directory = experiment.prepare()
        start = perf_counter()
        vectorizer = TfidfVectorizer(**config.tfidf.model_dump(), dtype=np.float32)
        features = vectorizer.fit_transform(splits["train"][0])
        model = GradientBoostingClassifier(**config.model.model_dump(), random_state=config.seed)
        model.fit(features, splits["train"][1])
        classifier = TextModerationBaseline(vectorizer, model, config)
        val_texts, val_labels = splits["val"]
        probabilities = [p.probability for p in classifier.predict_batch(val_texts).predictions]
        metrics = evaluate_probabilities(val_labels, probabilities, config.decision_threshold)
        save_models(directory, vectorizer, model, config)
        experiment.save_json("metrics.json", {"split": "val", **metrics})
        experiment.save_json("confusion_matrix.json", metrics["confusion_matrix"])
        sweep = evaluate_thresholds(
            val_labels, probabilities, directory / "threshold_metrics.csv", config.recall_target
        )
        experiment.save_json("threshold_summary.json", sweep)
        export_errors(
            val_texts,
            val_labels,
            probabilities,
            config.decision_threshold,
            directory / "error_cases.jsonl",
        )
        experiment.save_json(
            "training_summary.json",
            {
                "train_samples": len(splits["train"][0]),
                "val_samples": len(val_texts),
                "test_samples": len(splits["test"][0]),
                "test_not_used_for_selection": True,
                "feature_count": features.shape[1],
                "nnz": features.nnz,
                "sparse_bytes": features.data.nbytes
                + features.indices.nbytes
                + features.indptr.nbytes,
                "dense_float32_estimated_bytes": features.shape[0] * features.shape[1] * 4,
                "training_seconds": perf_counter() - start,
            },
        )
        experiment.save_json(
            "feature_importance.json",
            sorted(
                [
                    {"feature": str(f), "importance": float(i)}
                    for f, i in zip(
                        vectorizer.get_feature_names_out(), model.feature_importances_, strict=True
                    )
                ],
                key=lambda row: row["importance"],
                reverse=True,
            )[:30],
        )
        LOGGER.info("Baseline saved to %s; sensitive recall=%.4f", directory, metrics["recall"])
        return classifier
