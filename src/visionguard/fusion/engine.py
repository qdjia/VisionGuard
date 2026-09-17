"""Explainable rule and weighted multimodal risk fusion."""

from collections import defaultdict

from visionguard.fusion.config import FusionConfig
from visionguard.fusion.normalization import normalize_available_weights
from visionguard.fusion.schemas import (
    FusedCategory,
    FusedEvidence,
    FusionDecision,
    FusionMetadata,
    FusionReasonCode,
    FusionScores,
    FusionSignals,
    FusionWeightsUsed,
)


class RiskFusionEngine:
    """Fuse flat evidence without invoking or owning any upstream model."""

    def __init__(self, config: FusionConfig) -> None:
        self.config = config

    @property
    def version(self) -> str:
        return self.config.version

    def decide(self, signals: FusionSignals) -> FusionDecision:
        scores = self._scores(signals)
        available = {
            name
            for name, value in (
                ("visual", scores.visual),
                ("text", scores.text),
                ("vlm", scores.vlm),
            )
            if value is not None
        }
        weights, risk_score = self._combine(scores, available, signals)
        reasons: list[FusionReasonCode] = []

        def add(reason: FusionReasonCode) -> None:
            if reason not in reasons:
                reasons.append(reason)

        if scores.visual is not None and scores.visual >= self.config.risk_mapping.low_max:
            add(FusionReasonCode.VISUAL_RISK)
        if scores.text is not None and scores.text >= self.config.risk_mapping.low_max:
            add(FusionReasonCode.TEXT_RISK)
        if signals.vlm_risk_level in {"medium", "high"}:
            add(FusionReasonCode.VLM_RISK)
        if signals.evidence_conflict:
            add(FusionReasonCode.EVIDENCE_CONFLICT)
        if signals.module_failures:
            add(FusionReasonCode.MODULE_FAILURE)
        if (
            signals.ocr_text_length > 0
            and signals.mean_ocr_confidence is not None
            and signals.mean_ocr_confidence < self.config.baseline.min_ocr_reliability
        ):
            add(FusionReasonCode.OCR_LOW_RELIABILITY)
        if signals.insufficient_evidence:
            add(FusionReasonCode.INSUFFICIENT_EVIDENCE)
        if signals.routing_overridden_by_fusion:
            add(FusionReasonCode.ROUTING_OVERRIDE)

        hard_override = False
        if signals.high_risk_detection_count >= self.config.detector.hard_override_min_count:
            risk_score = max(risk_score, self.config.risk_mapping.low_max + 1e-6)
            hard_override = True
        if signals.vlm_risk_level == "high" and self._vlm_is_corroborated(signals):
            risk_score = max(risk_score, self.config.risk_mapping.medium_max + 1e-6)
            hard_override = True
        if signals.module_failures and self.config.conservative_mode:
            risk_score = max(risk_score, self.config.risk_mapping.low_max + 1e-6)
            hard_override = True
        if signals.insufficient_evidence and self.config.conservative_mode:
            risk_score = max(risk_score, self.config.risk_mapping.low_max + 1e-6)
            hard_override = True
        risk_score = min(risk_score, 1.0)
        if hard_override:
            add(FusionReasonCode.HARD_SAFETY_OVERRIDE)

        risk_level = self._map_risk(risk_score)
        near_boundary = self._near_boundary(risk_score)
        if near_boundary:
            add(FusionReasonCode.NEAR_DECISION_BOUNDARY)

        manual = bool(
            (signals.evidence_conflict and self.config.conflict.force_manual_review)
            or (signals.module_failures and self.config.failure.force_manual_review)
            or FusionReasonCode.OCR_LOW_RELIABILITY in reasons
            or signals.vlm_requires_manual_review
            or near_boundary
            or signals.routing_overridden_by_fusion
            or signals.insufficient_evidence
        )
        if not reasons:
            add(FusionReasonCode.ALL_EVIDENCE_SAFE)
        categories, evidence = self._provenance(signals, scores)
        explanation = self._explain(risk_level, risk_score, reasons, available)
        return FusionDecision(
            risk_level=risk_level,
            risk_score=risk_score,
            categories=categories,
            requires_manual_review=manual,
            reason=explanation,
            reason_codes=reasons,
            explanation=explanation,
            evidence_summary=evidence,
            signals=signals,
            scores=scores,
            weights=weights,
            policy_version=self.config.version,
            metadata=FusionMetadata(
                strategy=self.config.strategy,
                vlm_used=signals.vlm_available,
                available_sources=sorted(available),
                routing_policy_version=signals.routing_policy_version,
                fusion_policy_version=self.config.version,
                routing_overridden_by_fusion=signals.routing_overridden_by_fusion,
            ),
        )

    def _scores(self, signals: FusionSignals) -> FusionScores:
        visual = None
        if signals.detector_status == "success":
            visual = max((item.adjusted_score for item in signals.detection_evidence), default=0.0)
        text = None
        if (
            signals.baseline_status == "success"
            and signals.ocr_status == "success"
            and signals.baseline_probability is not None
            and signals.mean_ocr_confidence is not None
        ):
            text = signals.baseline_probability * signals.mean_ocr_confidence
        vlm = None
        if (
            self.config.vlm.trust_enabled
            and signals.vlm_available
            and signals.vlm_risk_level is not None
        ):
            vlm = self.config.vlm.level_scores[str(signals.vlm_risk_level)]
            if self.config.vlm.use_confidence_scaling and signals.vlm_confidence_score is not None:
                vlm *= 0.5 + 0.5 * signals.vlm_confidence_score
        return FusionScores(visual=visual, text=text, vlm=vlm)

    def _combine(self, scores, available, signals) -> tuple[FusionWeightsUsed, float]:
        if self.config.strategy == "vlm_only":
            if scores.vlm is None:
                return FusionWeightsUsed(), 0.5
            return FusionWeightsUsed(vlm=1.0), scores.vlm
        if self.config.strategy == "hard_rule":
            weights = normalize_available_weights(self.config.weights, available)
            high = bool(
                signals.high_risk_detection_count
                or (
                    signals.baseline_probability is not None
                    and signals.baseline_probability >= self.config.baseline.risky_threshold
                )
                or signals.vlm_risk_level == "high"
            )
            medium = bool(
                high
                or (scores.visual is not None and scores.visual >= self.config.risk_mapping.low_max)
                or (scores.text is not None and scores.text >= self.config.risk_mapping.low_max)
                or signals.vlm_risk_level == "medium"
            )
            if high:
                return weights, self.config.vlm.level_scores["high"]
            if medium:
                return weights, self.config.vlm.level_scores["medium"]
            return weights, self.config.vlm.level_scores["low"]
        weights = normalize_available_weights(self.config.weights, available)
        score = sum(
            value * getattr(weights, name)
            for name, value in (
                ("visual", scores.visual),
                ("text", scores.text),
                ("vlm", scores.vlm),
            )
            if value is not None
        )
        return weights, score

    def _map_risk(self, score: float) -> str:
        if score <= self.config.risk_mapping.low_max:
            return "low"
        if score <= self.config.risk_mapping.medium_max:
            return "medium"
        return "high"

    def _near_boundary(self, score: float) -> bool:
        return any(
            abs(score - boundary) < self.config.uncertainty_margin
            for boundary in (
                self.config.risk_mapping.low_max,
                self.config.risk_mapping.medium_max,
            )
        )

    def _vlm_is_corroborated(self, signals: FusionSignals) -> bool:
        visual = set(signals.high_risk_classes) & set(signals.vlm_categories)
        text = bool(
            "sensitive_text" in signals.vlm_categories
            and signals.baseline_probability is not None
            and signals.baseline_probability >= self.config.baseline.risky_threshold
        )
        return bool(visual or text)

    def _provenance(self, signals, scores):
        category_sources: dict[str, set[str]] = defaultdict(set)
        category_scores: dict[str, float] = defaultdict(float)
        evidence: list[FusedEvidence] = []
        for item in signals.detection_evidence:
            if item.confidence < self.config.detector.suspicious_conf_threshold:
                continue
            category_sources[item.class_name].add("detector")
            category_scores[item.class_name] = max(
                category_scores[item.class_name], item.adjusted_score
            )
            evidence.append(
                FusedEvidence(
                    source="detector",
                    category=item.class_name,
                    score=item.adjusted_score,
                    description=(
                        f"{item.class_name} confidence={item.confidence:.3f}, "
                        f"severity={item.severity:.3f}"
                    ),
                )
            )
        if signals.baseline_label == "sensitive" and scores.text is not None:
            category_sources["sensitive_text"].add("baseline")
            category_scores["sensitive_text"] = max(category_scores["sensitive_text"], scores.text)
            evidence.append(
                FusedEvidence(
                    source="baseline",
                    category="sensitive_text",
                    score=scores.text,
                    description=(
                        f"baseline probability={signals.baseline_probability:.3f}, "
                        f"OCR reliability={signals.mean_ocr_confidence:.3f}"
                    ),
                )
            )
        for name in signals.vlm_categories:
            category_sources[name].add("vlm")
            category_scores[name] = max(category_scores[name], scores.vlm or 0.0)
            evidence.append(
                FusedEvidence(
                    source="vlm",
                    category=name,
                    score=scores.vlm,
                    description=f"VLM risk={signals.vlm_risk_level}, category={name}",
                )
            )
        categories = [
            FusedCategory(
                name=name,
                score=category_scores[name],
                sources=sorted(sources),
            )
            for name, sources in sorted(category_sources.items())
        ]
        return categories, evidence

    @staticmethod
    def _explain(risk_level, score, reasons, available) -> str:
        reason_text = ", ".join(str(reason) for reason in reasons)
        source_text = ", ".join(sorted(available)) or "none"
        return (
            f"Fusion classified risk as {risk_level} with engineering score {score:.3f}; "
            f"available evidence: {source_text}; reasons: {reason_text}."
        )
