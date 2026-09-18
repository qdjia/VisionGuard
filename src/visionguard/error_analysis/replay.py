"""Offline replay of stored routing and fusion signals under current policies."""

import json
from pathlib import Path

from visionguard.fusion import RiskFusionEngine, load_fusion_config
from visionguard.fusion.replay import signals_from_record
from visionguard.routing import RoutingPolicy, load_routing_config
from visionguard.routing.schemas import RoutingSignals


def replay_error_records(
    records: list[dict], routing_policy: RoutingPolicy, fusion_engine: RiskFusionEngine
) -> list[dict]:
    replayed = []
    for record in records:
        result = record.get("result", {})
        raw_routing = result.get("routing_signals") or (result.get("routing") or {}).get("signals")
        if raw_routing is None:
            raise ValueError("record does not contain routing signals")
        route = routing_policy.decide(RoutingSignals.model_validate(raw_routing))
        fusion_signals = signals_from_record(record).model_copy(
            update={
                "route": route.route.value,
                "call_vlm": route.call_vlm,
                "routing_reason_codes": [item.value for item in route.reason_codes],
                "routing_policy_version": route.policy_version,
            }
        )
        decision = fusion_engine.decide(fusion_signals)
        old = record.get("decision") or result.get("fusion") or result.get("final") or {}
        expected = (record.get("ground_truth") or {}).get("risk_level")
        before_correct = bool(expected and old.get("risk_level") == expected)
        after_correct = bool(expected and decision.risk_level == expected)
        comparison = (
            "fixed"
            if not before_correct and after_correct
            else "regressed"
            if before_correct and not after_correct
            else "unchanged"
        )
        replayed.append(
            {
                "image": record.get("image"),
                "ground_truth": record.get("ground_truth"),
                "before": {
                    "route": (result.get("routing") or {}).get("route"),
                    "risk_level": old.get("risk_level"),
                },
                "after": {
                    "routing": route.model_dump(mode="json"),
                    "fusion": decision.model_dump(mode="json"),
                },
                "changed": bool(
                    (result.get("routing") or {}).get("route") != route.route.value
                    or old.get("risk_level") != decision.risk_level
                ),
                "comparison": comparison,
                "fixed_false_low": bool(
                    expected in {"medium", "high"}
                    and old.get("risk_level") == "low"
                    and decision.risk_level != "low"
                ),
                "new_false_low": bool(
                    expected in {"medium", "high"}
                    and old.get("risk_level") != "low"
                    and decision.risk_level == "low"
                ),
            }
        )
    return replayed


def replay_from_files(
    records_path: str | Path,
    routing_config: str | Path,
    fusion_config: str | Path,
    output: str | Path,
) -> dict:
    source = Path(records_path).resolve()
    records = [
        json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    replayed = replay_error_records(
        records,
        RoutingPolicy(load_routing_config(routing_config)),
        RiskFusionEngine(load_fusion_config(fusion_config)),
    )
    target = Path(output).resolve()
    if target.exists():
        raise FileExistsError(f"replay output already exists: {target}")
    target.mkdir(parents=True)
    (target / "replay_records.jsonl").write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in replayed), encoding="utf-8"
    )
    summary = {
        "total": len(replayed),
        "changed": sum(item["changed"] for item in replayed),
        "fixed": sum(item["comparison"] == "fixed" for item in replayed),
        "regressed": sum(item["comparison"] == "regressed" for item in replayed),
        "unchanged": sum(item["comparison"] == "unchanged" for item in replayed),
        "fixed_false_low": sum(item["fixed_false_low"] for item in replayed),
        "new_false_low": sum(item["new_false_low"] for item in replayed),
        "models_executed": False,
    }
    (target / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
