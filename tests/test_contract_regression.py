from pathlib import Path

from scripts.run_contract_regression import REQUIRED_SCENARIOS, load_suite, validate_suite


def test_fixed_contract_suite_covers_every_required_scenario() -> None:
    root = Path(__file__).resolve().parents[1]
    cases = load_suite(root / "data/regression/contract_manifest.jsonl")
    assert validate_suite(cases) == []
    assert {str(item["scenario"]) for item in cases} == REQUIRED_SCENARIOS
    assert len(cases) == 16
