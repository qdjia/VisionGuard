"""Bounded JSON extraction; ambiguous objects are rejected, not guessed."""

import json

from pydantic import ValidationError

from visionguard.moderation.policy import ModerationPolicy
from visionguard.moderation.schemas import ModerationResult
from visionguard.vlm.exceptions import VLMParseError, VLMValidationError


def parse_result(raw: str, policy: ModerationPolicy) -> ModerationResult:
    decoder = json.JSONDecoder()
    candidates = []
    index = 0
    while index < len(raw):
        if raw[index] != "{":
            index += 1
            continue
        try:
            value, end = decoder.raw_decode(raw[index:])
        except json.JSONDecodeError:
            index += 1
            continue
        candidates.append(value)
        index += end
    if len(candidates) != 1:
        raise VLMParseError("expected exactly one valid JSON object")
    try:
        payload = candidates[0]
        category_string_normalized = 0
        conservative_risk_normalized = 0
        evidence_type_normalized = 0
        if isinstance(payload, dict) and isinstance(payload.get("categories"), list):
            confidence = payload.get("confidence_score", 0.5)
            normalized_categories = []
            for category in payload["categories"]:
                if isinstance(category, str):
                    normalized_categories.append({"name": category, "score": confidence})
                    category_string_normalized += 1
                else:
                    normalized_categories.append(category)
            payload = {**payload, "categories": normalized_categories}
        if isinstance(payload, dict):
            categories = payload.get("categories")
            manual_review = payload.get("requires_manual_review")
            risk_level = payload.get("risk_level")
            if risk_level == "low" and (categories or manual_review is True):
                payload = {**payload, "risk_level": "medium", "requires_manual_review": True}
                conservative_risk_normalized += 1
            elif risk_level in {"medium", "high"} and manual_review is False:
                payload = {**payload, "requires_manual_review": True}
                conservative_risk_normalized += 1
            evidence = payload.get("evidence")
            if isinstance(evidence, list):
                normalized_evidence = []
                for item in evidence:
                    if (
                        isinstance(item, dict)
                        and item.get("type") in policy.categories
                    ):
                        normalized_evidence.append({**item, "type": "visual"})
                        evidence_type_normalized += 1
                    else:
                        normalized_evidence.append(item)
                payload = {**payload, "evidence": normalized_evidence}
        result = ModerationResult.model_validate(payload)
        normalized = sum(
            isinstance(item.get("bbox"), list)
            for item in payload.get("evidence", [])
            if isinstance(item, dict)
        )
        if any(c.name not in policy.categories for c in result.categories):
            raise ValueError("category not defined in policy")
        result.metadata = {
            "bbox_format_normalized": normalized,
            "category_string_normalized": category_string_normalized,
            "conservative_risk_normalized": conservative_risk_normalized,
            "evidence_type_normalized": evidence_type_normalized,
        }
        return result
    except (ValidationError, ValueError) as exc:
        raise VLMValidationError("moderation schema/policy validation failed") from exc
