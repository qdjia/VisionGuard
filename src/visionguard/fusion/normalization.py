"""Flatten model outputs into deterministic FusionSignals."""

from visionguard.fusion.config import FusionConfig, FusionWeights
from visionguard.fusion.schemas import FusionDetectionEvidence, FusionSignals, FusionWeightsUsed


def normalize_available_weights(
    weights: FusionWeights,
    available_sources: set[str],
) -> FusionWeightsUsed:
    """Renormalize configured weights over available evidence only."""

    raw = {
        "visual": weights.visual if "visual" in available_sources else 0.0,
        "text": weights.text if "text" in available_sources else 0.0,
        "vlm": weights.vlm if "vlm" in available_sources else 0.0,
    }
    total = sum(raw.values())
    if total <= 0:
        return FusionWeightsUsed()
    return FusionWeightsUsed(**{name: value / total for name, value in raw.items()})


def _status_value(statuses, name: str) -> str:
    value = statuses.get(name)
    return str(value.status) if value is not None else "unknown"


def build_fusion_signals(
    detection,
    ocr,
    baseline,
    vlm,
    routing,
    statuses,
    config: FusionConfig,
) -> FusionSignals:
    """Extract flat, replayable inputs; the engine never traverses model objects."""

    detections = detection.detections if detection else []
    confidences = [item.confidence for item in detections]
    evidence: list[FusionDetectionEvidence] = []
    high_risk_classes: list[str] = []
    for item in detections:
        severity = config.detector.class_severity.get(item.class_name, 0.0)
        evidence.append(
            FusionDetectionEvidence(
                class_name=item.class_name,
                confidence=item.confidence,
                severity=severity,
                adjusted_score=item.confidence * severity,
            )
        )
        if severity > 0 and item.confidence >= config.detector.high_risk_conf_threshold:
            high_risk_classes.append(item.class_name)

    ocr_confidences = [block.confidence for block in ocr.blocks] if ocr else []
    mean_ocr = sum(ocr_confidences) / len(ocr_confidences) if ocr_confidences else None
    detector_status = _status_value(statuses, "detector")
    ocr_status = _status_value(statuses, "ocr")
    baseline_status = _status_value(statuses, "baseline")
    vlm_status = _status_value(statuses, "vlm")
    failures = [
        name
        for name, status in (
            ("detector", detector_status),
            ("ocr", ocr_status),
            ("baseline", baseline_status),
            ("vlm", vlm_status),
        )
        if status == "failed"
    ]
    route = str(routing.route) if routing else "unknown"
    routing_reasons = [str(reason) for reason in routing.reason_codes] if routing else []
    baseline_probability = baseline.probability if baseline else None
    visual_high = bool(high_risk_classes)
    baseline_high = bool(
        baseline_probability is not None and baseline_probability >= config.baseline.risky_threshold
    )
    vlm_low = bool(vlm and str(vlm.risk_level) == "low")
    vlm_high = bool(vlm and str(vlm.risk_level) == "high")
    visual_safe = not any(
        item.confidence >= config.detector.suspicious_conf_threshold and item.severity > 0
        for item in evidence
    )
    text_safe = bool(
        baseline_probability is not None
        and baseline_probability <= config.baseline.safe_threshold
        and mean_ocr is not None
        and mean_ocr >= config.baseline.min_ocr_reliability
    )
    evidence_conflict = bool(
        (visual_high and vlm_low)
        or (baseline_high and vlm_low)
        or (vlm_high and visual_safe and text_safe)
        or (baseline_high and (mean_ocr is None or mean_ocr < config.baseline.min_ocr_reliability))
    )
    text_available = bool(
        baseline is not None and baseline_status == "success" and ocr_status == "success"
    )
    visual_available = detection is not None and detector_status == "success"
    vlm_available = vlm is not None and vlm_status == "success"
    insufficient = not any((visual_available, text_available, vlm_available)) or bool(
        not vlm_available and not text_available and not detections
    )
    return FusionSignals(
        detection_count=len(detections),
        max_detection_confidence=max(confidences, default=None),
        mean_detection_confidence=(sum(confidences) / len(confidences) if confidences else None),
        high_risk_detection_count=len(high_risk_classes),
        high_risk_classes=sorted(set(high_risk_classes)),
        detection_evidence=evidence,
        detector_status=detector_status,
        ocr_block_count=len(ocr_confidences),
        mean_ocr_confidence=mean_ocr,
        ocr_text_length=len(ocr.full_text.strip()) if ocr else 0,
        ocr_status=ocr_status,
        baseline_label=baseline.label if baseline else None,
        baseline_probability=baseline_probability,
        baseline_status=baseline_status,
        vlm_available=vlm_available,
        vlm_risk_level=vlm.risk_level if vlm else None,
        vlm_categories=[category.name for category in vlm.categories] if vlm else [],
        vlm_confidence_score=vlm.confidence_score if vlm else None,
        vlm_requires_manual_review=vlm.requires_manual_review if vlm else None,
        vlm_has_evidence=bool(vlm and vlm.evidence),
        vlm_status=vlm_status,
        route=route,
        call_vlm=bool(routing and routing.call_vlm),
        routing_reason_codes=routing_reasons,
        routing_policy_version=routing.policy_version if routing else None,
        routing_overridden_by_fusion=bool(routing and routing.routing_overridden_by_fusion),
        module_failures=failures,
        evidence_conflict=evidence_conflict,
        insufficient_evidence=insufficient,
    )
