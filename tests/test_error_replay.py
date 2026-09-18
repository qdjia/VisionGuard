from visionguard.error_analysis.replay import replay_error_records
from visionguard.fusion import RiskFusionEngine, load_fusion_config
from visionguard.routing import RoutingPolicy, load_routing_config


def test_replay_uses_stored_signals_without_model_objects() -> None:
    routing_signals = {
        "detection_count": 0,
        "ocr_block_count": 1,
        "mean_ocr_confidence": 0.99,
        "ocr_text_length": 20,
        "baseline_probability": 0.01,
        "detector_status": "success",
        "ocr_status": "success",
        "baseline_status": "success",
    }
    fusion_signals = {
        "detector_status": "success",
        "ocr_block_count": 1,
        "mean_ocr_confidence": 0.99,
        "ocr_text_length": 20,
        "ocr_status": "success",
        "baseline_label": "safe",
        "baseline_probability": 0.01,
        "baseline_status": "success",
        "vlm_status": "skipped",
    }
    records = [
        {
            "image": "safe.png",
            "ground_truth": {"risk_level": "low", "categories": []},
            "signals": fusion_signals,
            "decision": {"risk_level": "low"},
            "result": {"routing_signals": routing_signals, "routing": {"route": "fast_path"}},
        }
    ]
    replayed = replay_error_records(
        records,
        RoutingPolicy(load_routing_config("configs/routing.yaml")),
        RiskFusionEngine(load_fusion_config("configs/fusion.yaml")),
    )
    assert replayed[0]["after"]["routing"]["route"] == "fast_path"
    assert replayed[0]["after"]["fusion"]["risk_level"] == "low"
    assert replayed[0]["comparison"] == "unchanged"
