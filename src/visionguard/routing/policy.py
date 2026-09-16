"""Conservative, explainable, deterministic Phase 8 routing policy."""

from visionguard.routing.config import RoutingConfig
from visionguard.routing.schemas import (
    Route,
    RoutingDecision,
    RoutingReasonCode,
    RoutingSignals,
)


class RoutingPolicy:
    def __init__(self, config: RoutingConfig) -> None:
        self.config = config

    @property
    def version(self) -> str:
        return self.config.version

    def collect_signals(self, detection, ocr, baseline, statuses, vlm=None) -> RoutingSignals:
        detections = detection.detections if detection else []
        detection_confidences = [item.confidence for item in detections]
        high_risk_classes = set(self.config.high_risk_classes)
        high_risk = [
            item
            for item in detections
            if item.class_name in high_risk_classes
            and item.confidence >= self.config.detector.high_risk_conf_threshold
        ]
        suspicious = [
            item
            for item in detections
            if item.class_name in high_risk_classes
            and item.confidence >= self.config.detector.suspicious_conf_threshold
        ]
        ocr_confidences = [item.confidence for item in ocr.blocks] if ocr else []
        text_length = len(ocr.full_text.strip()) if ocr else 0
        probability = baseline.probability if baseline else None
        mean_ocr = sum(ocr_confidences) / len(ocr_confidences) if ocr_confidences else None
        conflict = bool(
            (
                suspicious
                and probability is not None
                and probability <= self.config.baseline.safe_threshold
            )
            or (
                probability is not None
                and probability >= self.config.baseline.risky_threshold
                and (mean_ocr is None or mean_ocr < self.config.ocr.min_mean_confidence)
            )
        )
        insufficient = bool(
            text_length < self.config.ocr.min_text_length or probability is None or mean_ocr is None
        )
        return RoutingSignals(
            detection_count=len(detections),
            max_detection_confidence=max(detection_confidences, default=None),
            mean_detection_confidence=(
                sum(detection_confidences) / len(detection_confidences)
                if detection_confidences
                else None
            ),
            high_risk_detection_count=len(high_risk),
            suspicious_high_risk_detection_count=len(suspicious),
            has_high_risk_class=bool(suspicious),
            ocr_block_count=len(ocr_confidences),
            mean_ocr_confidence=mean_ocr,
            ocr_text_length=text_length,
            baseline_probability=probability,
            detector_status=str(statuses["detector"].status),
            ocr_status=str(statuses["ocr"].status),
            baseline_status=str(statuses["baseline"].status),
            evidence_conflict=conflict,
            insufficient_evidence=insufficient,
            vlm_confidence=vlm.confidence_score if vlm else None,
            vlm_requires_manual_review=vlm.requires_manual_review if vlm else None,
            baseline_input_chars=len(baseline.text) if baseline else 0,
        )

    def decide(self, signals: RoutingSignals) -> RoutingDecision:
        reasons: list[RoutingReasonCode] = []

        def add(reason: RoutingReasonCode) -> None:
            if reason not in reasons:
                reasons.append(reason)

        failed = any(
            status == "failed"
            for status in (
                signals.detector_status,
                signals.ocr_status,
                signals.baseline_status,
            )
        )
        if failed and self.config.failure.route_to_vlm:
            add(RoutingReasonCode.MODULE_FAILURE)
        if signals.high_risk_detection_count:
            add(RoutingReasonCode.HIGH_RISK_DETECTION)

        probability = signals.baseline_probability
        if probability is not None:
            if probability >= self.config.baseline.risky_threshold:
                add(RoutingReasonCode.BASELINE_HIGH_RISK)
            elif probability > self.config.baseline.safe_threshold:
                add(RoutingReasonCode.BASELINE_UNCERTAIN)

        if signals.ocr_text_length == 0:
            add(RoutingReasonCode.NO_TEXT)
        if (
            signals.ocr_text_length > 0
            and signals.mean_ocr_confidence is not None
            and signals.mean_ocr_confidence < self.config.ocr.min_mean_confidence
        ):
            add(RoutingReasonCode.OCR_LOW_CONFIDENCE)
        if signals.evidence_conflict:
            add(RoutingReasonCode.EVIDENCE_CONFLICT)
        if signals.insufficient_evidence and self.config.conservative_mode:
            add(RoutingReasonCode.INSUFFICIENT_EVIDENCE)
        if signals.detection_count == 0:
            add(RoutingReasonCode.NO_DETECTION)

        blocking = {
            RoutingReasonCode.HIGH_RISK_DETECTION,
            RoutingReasonCode.BASELINE_HIGH_RISK,
            RoutingReasonCode.BASELINE_UNCERTAIN,
            RoutingReasonCode.OCR_LOW_CONFIDENCE,
            RoutingReasonCode.EVIDENCE_CONFLICT,
            RoutingReasonCode.MODULE_FAILURE,
            RoutingReasonCode.INSUFFICIENT_EVIDENCE,
        }
        stage_one_success = all(
            status == "success"
            for status in (
                signals.detector_status,
                signals.ocr_status,
                signals.baseline_status,
            )
        )
        safe_consensus = bool(
            stage_one_success
            and probability is not None
            and probability <= self.config.baseline.safe_threshold
            and signals.ocr_text_length >= self.config.ocr.min_text_length
            and signals.mean_ocr_confidence is not None
            and signals.mean_ocr_confidence >= self.config.ocr.min_mean_confidence
            and signals.high_risk_detection_count == 0
            and not signals.evidence_conflict
        )
        call_vlm = any(reason in blocking for reason in reasons) or not safe_consensus
        if call_vlm and not any(reason in blocking for reason in reasons):
            add(RoutingReasonCode.INSUFFICIENT_EVIDENCE)
        if not call_vlm:
            add(RoutingReasonCode.SAFE_CONSENSUS)
        return RoutingDecision(
            route=Route.VLM_PATH if call_vlm else Route.FAST_PATH,
            call_vlm=call_vlm,
            reason_codes=reasons,
            explanation=(
                "VLM required because: " + ", ".join(reasons)
                if call_vlm
                else "Fast-path low risk allowed by conservative safe consensus."
            ),
            signals=signals,
            policy_version=self.config.version,
        )
