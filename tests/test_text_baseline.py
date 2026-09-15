import csv
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from visionguard.baseline import TextBaselineTrainer, TextModerationBaseline, load_baseline_config
from visionguard.baseline.dataset import load_dataset, validate_splits
from visionguard.baseline.evaluator import (
    evaluate_probabilities,
    evaluate_thresholds,
    export_errors,
)
from visionguard.baseline.preprocessing import clean_text
from visionguard.baseline.schemas import TextModerationPrediction
from visionguard.schemas import OCRResult, OCRTiming


def test_text_cleaning_and_empty() -> None:
    assert clean_text("  ＡＢＣ\n 中文\u200b  ", lowercase=True) == "abc 中文"
    with pytest.raises(ValueError, match="empty"):
        clean_text(" \n\u200b")


def test_prediction_schema() -> None:
    with pytest.raises(ValidationError):
        TextModerationPrediction(text="a", label="unknown", probability=2, threshold=0.5)


def write_csv(path: Path, rows) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["text", "label"])
        writer.writerows(rows)


def test_dataset_duplicates_invalid_labels_and_conflicts(tmp_path) -> None:
    path = tmp_path / "dataset.csv"
    write_csv(path, [("正常文本", 0), ("正常文本", 0), ("", 1), ("危险文本", 1)])
    assert load_dataset(path) == (["正常文本", "危险文本"], [0, 1])
    write_csv(path, [("文本", 2)])
    with pytest.raises(ValueError, match="invalid label"):
        load_dataset(path)
    write_csv(path, [("文本", 0), ("文本", 1)])
    with pytest.raises(ValueError, match="conflicting"):
        load_dataset(path)


def test_split_leakage_rejected() -> None:
    with pytest.raises(ValueError, match="leakage"):
        validate_splits({"train": (["a", "b"], [0, 1]), "val": (["a", "c"], [0, 1])})


def test_metrics_threshold_sweep_and_errors(tmp_path) -> None:
    metrics = evaluate_probabilities([0, 1], [0.5, 0.5], 0.5)
    assert metrics["confusion_matrix"] == {"TN": 0, "FP": 1, "FN": 0, "TP": 1}
    assert json.loads(json.dumps(metrics))["recall"] == 1
    summary = evaluate_thresholds([0, 1], [0.2, 0.8], tmp_path / "threshold.csv")
    assert summary["formal_threshold_unchanged"]
    assert export_errors(["a", "b"], [0, 1], [0.9, 0.1], 0.5, tmp_path / "errors.jsonl") == 2


def test_small_train_save_load_batch_threshold_and_ocr(tmp_path) -> None:
    config = load_baseline_config("configs/baseline_text.yaml").model_copy(
        update={"artifacts_dir": tmp_path}
    )
    classifier = TextBaselineTrainer(config).train()
    loaded = TextModerationBaseline.load(tmp_path / config.experiment_name)
    texts = ["正常教材知识", "危险暴力伤害"]
    assert [p.probability for p in classifier.predict_batch(texts).predictions] == [
        p.probability for p in loaded.predict_batch(texts).predictions
    ]
    assert loaded.predict_batch(texts, threshold=0).sensitive_count == 2
    assert loaded.predict_batch([]).total == 0
    calls = {"transform": 0, "predict": 0}
    transform = loaded.vectorizer.transform
    predict_proba = loaded.model.predict_proba

    def counted_transform(batch):
        calls["transform"] += 1
        return transform(batch)

    def counted_predict(features):
        calls["predict"] += 1
        assert hasattr(features, "nnz")
        return predict_proba(features)

    loaded.vectorizer.transform = counted_transform
    loaded.model.predict_proba = counted_predict
    loaded.predict_batch(texts)
    assert calls == {"transform": 1, "predict": 1}
    with pytest.raises(ValueError, match="threshold"):
        loaded.predict("text", threshold=1.1)
    with pytest.raises(ValueError, match="empty"):
        loaded.predict(" ")
    ocr = OCRResult(
        image_width=100,
        image_height=100,
        full_text="正常教材知识",
        timing=OCRTiming(),
        device="cpu",
        engine_name="fake",
    )
    assert loaded.predict_ocr(ocr).source == "ocr"
    with pytest.raises(FileExistsError):
        TextBaselineTrainer(config).train()


def test_stratified_split_is_reproducible(tmp_path) -> None:
    from visionguard.baseline.dataset import split_dataset

    source = tmp_path / "all.csv"
    write_csv(
        source, [(f"正常文本{i}", 0) for i in range(20)] + [(f"危险文本{i}", 1) for i in range(20)]
    )
    split_dataset(source, tmp_path / "first", seed=42)
    split_dataset(source, tmp_path / "second", seed=42)
    for name in ("train", "val", "test"):
        first, second = tmp_path / "first" / f"{name}.csv", tmp_path / "second" / f"{name}.csv"
        assert first.read_bytes() == second.read_bytes()
        assert set(load_dataset(first)[1]) == {0, 1}
