import hashlib
from pathlib import Path

from scripts.run_historical_real_image_regression import classify, summarize_results
from visionguard.evaluation.historical import (
    HistoricalImageRecord,
    HistoricalImageSource,
    coverage,
    load_jsonl,
    validate_resolved,
    validate_sources,
)


def _source(case_id: str, scenario: str, title: str | None = None) -> HistoricalImageSource:
    return HistoricalImageSource(
        case_id=case_id,
        commons_title=title or f"File:{case_id}.jpg",
        scenario=scenario,
        ground_truth={"risk_level": "low", "categories": []},
        notes="test record",
    )


def test_tracked_source_manifest_has_required_real_image_coverage() -> None:
    records = load_jsonl(
        Path("data/regression/real_image_sources.jsonl"), HistoricalImageSource
    )
    assert len(records) == 27
    assert validate_sources(records) == []
    assert all(record.annotation_status == "verified" for record in records)


def test_source_validation_rejects_duplicates_and_missing_scenarios() -> None:
    records = [_source("real-001", "safe_publishing"), _source("real-001", "qr_code")]
    errors = validate_sources(records)
    assert "case_id values must be unique" in errors
    assert any(error.startswith("required scenarios missing:") for error in errors)


def test_resolved_manifest_checks_asset_hash(tmp_path: Path) -> None:
    image = tmp_path / "real-001.jpg"
    image.write_bytes(b"real image bytes")
    payload = {
        **_source("real-001", "safe_publishing").model_dump(mode="json"),
        "filename": image.name,
        "source_page_url": "https://commons.wikimedia.org/wiki/File:real-001.jpg",
        "download_url": "https://upload.wikimedia.org/real-001.jpg",
        "license_name": "CC0",
        "artist": "Tester",
        "attribution_required": False,
        "commons_page_id": 1,
        "commons_revision_id": 2,
        "commons_sha1": "a" * 40,
        "sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
        "size_bytes": image.stat().st_size,
        "width": 10,
        "height": 10,
        "mime_type": "image/jpeg",
    }
    record = HistoricalImageRecord.model_validate(payload)
    assert validate_resolved([record], tmp_path, minimum_cases=1) == [
        "required scenarios missing: blood, multilingual_text, prohibited_symbol, qr_code, "
        "violence, watermark, weapon"
    ]
    image.write_bytes(b"tampered")
    errors = validate_resolved([record], tmp_path, minimum_cases=1)
    assert "real-001: image size mismatch" in errors
    assert "real-001: image SHA-256 mismatch" in errors


def test_coverage_counts_verified_annotations() -> None:
    source = _source("real-001", "safe_publishing")
    payload = {
        **source.model_dump(mode="json"),
        "annotation_status": "verified",
        "filename": "real-001.jpg",
        "source_page_url": "https://commons.wikimedia.org/wiki/File:real-001.jpg",
        "download_url": "https://upload.wikimedia.org/real-001.jpg",
        "license_name": "Public domain",
        "artist": "Unknown",
        "attribution_required": False,
        "commons_page_id": 1,
        "commons_revision_id": 2,
        "commons_sha1": "a" * 40,
        "sha256": "b" * 64,
        "size_bytes": 10,
        "width": 10,
        "height": 10,
        "mime_type": "image/jpeg",
    }
    report = coverage([HistoricalImageRecord.model_validate(payload)])
    assert report["verified_annotations"] == 1
    assert report["scenario_counts"] == {"safe_publishing": 1}


def test_real_image_classification_blocks_unsafe_downgrade() -> None:
    source = HistoricalImageSource(
        case_id="real-001",
        commons_title="File:real-001.jpg",
        scenario="weapon",
        ground_truth={
            "risk_level": "medium",
            "categories": ["weapon"],
            "requires_manual_review": True,
        },
        annotation_status="verified",
        notes="test record",
    )
    record = HistoricalImageRecord.model_validate(
        {
            **source.model_dump(mode="json"),
            "filename": "real-001.jpg",
            "source_page_url": "https://commons.wikimedia.org/wiki/File:real-001.jpg",
            "download_url": "https://upload.wikimedia.org/real-001.jpg",
            "license_name": "CC0",
            "artist": "Tester",
            "attribution_required": False,
            "commons_page_id": 1,
            "commons_revision_id": 2,
            "commons_sha1": "a" * 40,
            "sha256": "b" * 64,
            "size_bytes": 10,
            "width": 10,
            "height": 10,
            "mime_type": "image/jpeg",
        }
    )
    classification, reasons = classify(
        record,
        {
            "status": "completed",
            "result": {
                "risk_level": "low",
                "categories": [],
                "requires_manual_review": False,
            },
        },
    )
    assert classification == "CONFIRMED_REGRESSION"
    assert "required manual review was lost" in reasons


def test_result_summary_counts_unsafe_fast_paths_and_vlm_usage() -> None:
    results = [
        {
            "classification": "CONFIRMED_REGRESSION",
            "actual": {"route": "fast_path", "vlm_called": False},
        },
        {
            "classification": "CONFIRMED_REGRESSION",
            "actual": {"route": "vlm_path", "vlm_called": True},
        },
        {
            "classification": "EQUIVALENT",
            "actual": {"route": "vlm_path", "vlm_called": True},
        },
    ]

    assert summarize_results(results) == {
        "classification_counts": {"CONFIRMED_REGRESSION": 2, "EQUIVALENT": 1},
        "confirmed_regression_count": 2,
        "potential_regression_count": 0,
        "unsafe_fast_path_count": 1,
        "vlm_called_count": 2,
        "vlm_call_rate": 0.666667,
    }
