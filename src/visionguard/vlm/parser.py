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
        result = ModerationResult.model_validate(candidates[0])
        normalized = sum(
            isinstance(item.get("bbox"), list)
            for item in candidates[0].get("evidence", [])
            if isinstance(item, dict)
        )
        if any(c.name not in policy.categories for c in result.categories):
            raise ValueError("category not defined in policy")
        result.metadata = {"bbox_format_normalized": normalized}
        return result
    except (ValidationError, ValueError) as exc:
        raise VLMValidationError("moderation schema/policy validation failed") from exc
