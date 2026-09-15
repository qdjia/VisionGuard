"""Trusted-local joblib persistence. Never load untrusted pickle artifacts."""

from pathlib import Path

import joblib
import sklearn
import yaml

from visionguard.baseline.config import BaselineConfig


def save_models(directory: Path, vectorizer, model, config: BaselineConfig) -> None:
    joblib.dump(vectorizer, directory / "tfidf.joblib")
    joblib.dump(model, directory / "gbdt.joblib")
    (directory / "config.yaml").write_text(
        yaml.safe_dump({"baseline": config.model_dump(mode="json")}, sort_keys=False),
        encoding="utf-8",
    )
    (directory / "sklearn_version.txt").write_text(sklearn.__version__, encoding="utf-8")


def load_models(directory: Path):
    saved = (directory / "sklearn_version.txt").read_text(encoding="utf-8").strip()
    if saved != sklearn.__version__:
        raise ValueError(f"sklearn version mismatch: saved={saved} runtime={sklearn.__version__}")
    vectorizer = joblib.load(directory / "tfidf.joblib")
    model = joblib.load(directory / "gbdt.joblib")
    if list(model.classes_) != [0, 1]:
        raise ValueError("baseline model must contain normal=0 and sensitive=1 classes")
    if len(vectorizer.get_feature_names_out()) != model.n_features_in_:
        raise ValueError("vectorizer/model feature dimension mismatch")
    return vectorizer, model
