"""CSV validation and reproducible leakage-free stratified splitting."""

import csv
import logging
from pathlib import Path

from sklearn.model_selection import train_test_split

from visionguard.baseline.preprocessing import clean_text

LOGGER = logging.getLogger(__name__)


def load_dataset(path: str | Path, *, lowercase: bool = False) -> tuple[list[str], list[int]]:
    unique: dict[str, int] = {}
    skipped = 0
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not {"text", "label"}.issubset(reader.fieldnames or []):
            raise ValueError("CSV requires text,label columns")
        for row in reader:
            if row["label"] not in {"0", "1"}:
                raise ValueError(f"invalid label: {row['label']!r}")
            try:
                text = clean_text(row["text"], lowercase=lowercase)
            except ValueError:
                skipped += 1
                continue
            label = int(row["label"])
            if text in unique and unique[text] != label:
                raise ValueError("duplicate text has conflicting labels")
            if text in unique:
                skipped += 1
            unique[text] = label
    if not unique:
        raise ValueError("dataset contains no valid samples")
    LOGGER.info("Dataset %s samples=%d skipped=%d", path, len(unique), skipped)
    return list(unique), list(unique.values())


def validate_splits(splits: dict[str, tuple[list[str], list[int]]]) -> None:
    seen: set[str] = set()
    for name, (texts, labels) in splits.items():
        if set(labels) != {0, 1}:
            raise ValueError(f"{name} must contain both classes")
        if seen.intersection(texts):
            raise ValueError(f"text leakage across dataset splits: {name}")
        seen.update(texts)


def split_dataset(path: Path, output: Path, seed: int = 42) -> None:
    texts, labels = load_dataset(path)
    train_x, rest_x, train_y, rest_y = train_test_split(
        texts, labels, test_size=0.3, stratify=labels, random_state=seed
    )
    val_x, test_x, val_y, test_y = train_test_split(
        rest_x, rest_y, test_size=0.5, stratify=rest_y, random_state=seed
    )
    output.mkdir(parents=True, exist_ok=True)
    for name in ("train", "val", "test"):
        if (output / f"{name}.csv").exists():
            raise FileExistsError(output / f"{name}.csv")
    for name, xs, ys in (
        ("train", train_x, train_y),
        ("val", val_x, val_y),
        ("test", test_x, test_y),
    ):
        target = output / f"{name}.csv"
        if target.exists():
            raise FileExistsError(target)
        with target.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["text", "label"])
            writer.writerows(zip(xs, ys, strict=True))
