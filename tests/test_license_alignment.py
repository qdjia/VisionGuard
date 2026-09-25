from pathlib import Path

from scripts.validate_license_alignment import PROJECT_LICENSE, validate_alignment


def test_repository_license_metadata_is_consistent() -> None:
    assert validate_alignment(Path.cwd()) == []


def test_dependency_mit_licenses_are_not_treated_as_project_drift() -> None:
    lockfile = (Path.cwd() / "desktop/package-lock.json").read_text(encoding="utf-8")
    assert '"license": "MIT"' in lockfile
    assert PROJECT_LICENSE == "AGPL-3.0-only"
