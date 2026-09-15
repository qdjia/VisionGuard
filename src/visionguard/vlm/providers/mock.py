import json

from visionguard.vlm.exceptions import VLMTimeoutError
from visionguard.vlm.retry import StructuredProvider


class MockVLMProvider(StructuredProvider):
    def __init__(self, config) -> None:
        super().__init__(config)
        self.calls = 0

    def generate(self, image, prompt, deadline):
        self.calls += 1
        mode = self.config.mock_mode
        if mode == "timeout":
            raise VLMTimeoutError("simulated timeout")
        if mode == "malformed" and self.calls == 1:
            return '{"risk_level":', {}
        sensitive = mode == "sensitive"
        return json.dumps(
            {
                "risk_level": "high" if sensitive else "low",
                "categories": [{"name": "sensitive_text", "score": 0.9}] if sensitive else [],
                "reason": "Fixed mock result; not a real model judgement.",
                "evidence": [{"type": "semantic", "description": "Synthetic mock evidence"}]
                if sensitive
                else [],
                "confidence_score": 0.8,
                "requires_manual_review": sensitive,
            }
        ), {}
