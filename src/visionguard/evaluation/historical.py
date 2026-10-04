"""Contracts and validation for redistribution-safe real-image regression data."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator

from visionguard.error_analysis.schemas import GroundTruth
from visionguard.schemas.common import SchemaModel

HistoricalScenario = Literal[
    "safe_publishing",
    "multilingual_text",
    "qr_code",
    "weapon",
    "violence",
    "blood",
    "visual_sensitive_region",
    "prohibited_symbol",
    "watermark",
]

REQUIRED_SCENARIOS = {
    "safe_publishing",
    "multilingual_text",
    "qr_code",
    "weapon",
    "violence",
    "blood",
    "prohibited_symbol",
    "watermark",
}
ALLOWED_LICENSES = {
    "CC0",
    "CC BY 2.0",
    "CC BY 3.0",
    "CC BY 4.0",
    "CC BY-SA 2.0",
    "CC BY-SA 3.0",
    "CC BY-SA 4.0",
    "Public domain",
}


class HistoricalImageSource(SchemaModel):
    case_id: str = Field(pattern=r"^real-[0-9]{3}$")
    commons_title: str = Field(pattern=r"^File:.+")
    scenario: HistoricalScenario
    ground_truth: GroundTruth
    annotation_status: Literal["needs_review", "verified"] = "needs_review"
    notes: str = Field(min_length=1)


class HistoricalImageRecord(HistoricalImageSource):
    filename: str = Field(pattern=r"^real-[0-9]{3}\.[a-z0-9]+$")
    source_page_url: str = Field(pattern=r"^https://commons\.wikimedia\.org/")
    download_url: str = Field(pattern=r"^https://")
    license_name: str
    license_url: str | None = None
    artist: str
    attribution_required: bool
    commons_page_id: int = Field(gt=0)
    commons_revision_id: int = Field(gt=0)
    commons_sha1: str = Field(pattern=r"^[0-9a-f]{40}$")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    mime_type: Literal["image/jpeg", "image/png"]

    @field_validator("license_name")
    @classmethod
    def supported_license(cls, value: str) -> str:
        if value not in ALLOWED_LICENSES:
            raise ValueError(f"unsupported redistribution license: {value}")
        return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_jsonl(path: str | Path, model):
    source = Path(path)
    return [
        model.model_validate(json.loads(line))
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def validate_sources(records: list[HistoricalImageSource], minimum_cases: int = 20) -> list[str]:
    errors: list[str] = []
    if not minimum_cases <= len(records) <= 50:
        errors.append(f"real-image case count must be between {minimum_cases} and 50")
    ids = [item.case_id for item in records]
    titles = [item.commons_title for item in records]
    if len(ids) != len(set(ids)):
        errors.append("case_id values must be unique")
    if len(titles) != len(set(titles)):
        errors.append("Wikimedia Commons titles must be unique")
    missing = sorted(REQUIRED_SCENARIOS - {item.scenario for item in records})
    if missing:
        errors.append(f"required scenarios missing: {', '.join(missing)}")
    return errors


def validate_resolved(
    records: list[HistoricalImageRecord], asset_root: str | Path, minimum_cases: int = 20
) -> list[str]:
    errors = validate_sources(records, minimum_cases)
    root = Path(asset_root)
    for item in records:
        target = root / item.filename
        if not target.is_file():
            errors.append(f"{item.case_id}: image is missing")
            continue
        if target.stat().st_size != item.size_bytes:
            errors.append(f"{item.case_id}: image size mismatch")
        if sha256(target) != item.sha256:
            errors.append(f"{item.case_id}: image SHA-256 mismatch")
    return errors


def coverage(records: list[HistoricalImageRecord]) -> dict[str, object]:
    scenarios = Counter(item.scenario for item in records)
    licenses = Counter(item.license_name for item in records)
    return {
        "total": len(records),
        "verified_annotations": sum(item.annotation_status == "verified" for item in records),
        "scenario_counts": dict(sorted(scenarios.items())),
        "license_counts": dict(sorted(licenses.items())),
        "all_required_scenarios_present": REQUIRED_SCENARIOS <= set(scenarios),
    }
