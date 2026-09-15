import html
import json

from visionguard.moderation.policy import ModerationPolicy
from visionguard.moderation.schemas import ModerationResult
from visionguard.vlm.config import VLMConfig
from visionguard.vlm.schemas import VLMContext


class PromptBuilder:
    def __init__(self, config: VLMConfig) -> None:
        self.config = config
        self.system = (config.prompts_dir / f"system_{config.prompt_version}.txt").read_text(
            encoding="utf-8"
        )
        self.template = (config.prompts_dir / f"moderation_{config.prompt_version}.txt").read_text(
            encoding="utf-8"
        )

    def build(self, context: VLMContext, policy: ModerationPolicy) -> tuple[str, dict]:
        config = self.config
        detections = sorted(context.detections, key=lambda d: d.confidence, reverse=True)
        blocks = sorted(context.ocr_blocks, key=lambda b: b.confidence, reverse=True)
        chosen = blocks[: config.max_ocr_blocks]
        chosen.sort(key=lambda b: (round(b.bbox.y1 / 10), b.bbox.x1))
        remaining = config.max_ocr_chars
        ocr = []
        for block in chosen:
            text = block.text[:remaining]
            remaining -= len(text)
            if text:
                ocr.append(
                    {"text": text, "confidence": block.confidence, "bbox": block.bbox.model_dump()}
                )
        # Full text is omitted when blocks exist: avoid duplicate unbounded context.
        full = context.ocr_full_text[:remaining] if not context.ocr_blocks else ""
        baseline = context.baseline_prediction
        payload = {
            "detector": [
                {"class": d.class_name, "confidence": d.confidence, "bbox": d.bbox.model_dump()}
                for d in detections[: config.max_detections]
            ],
            "ocr": {"blocks": ocr, "full_text": full},
            "baseline": {"label": baseline.label, "probability": baseline.probability}
            if baseline
            else None,
        }
        schema = ModerationResult.model_json_schema()
        schema["properties"].pop("confidence", None)
        schema["properties"].pop("metadata", None)
        data = html.escape(json.dumps(payload, ensure_ascii=False), quote=False)
        prompt = (
            self.template
            + "\nPolicy:\n"
            + policy.model_dump_json()
            + ("\n<untrusted_evidence>\n" + data + "\n</untrusted_evidence>\nOutput schema:\n")
            + json.dumps(schema, ensure_ascii=False)
        )
        return prompt, {
            "detections_truncated": len(detections) > config.max_detections,
            "ocr_truncated": len(blocks) > len(chosen)
            or sum(len(b.text) for b in blocks) > config.max_ocr_chars
            or (not blocks and len(context.ocr_full_text) > len(full)),
            "input_chars": len(prompt),
        }
