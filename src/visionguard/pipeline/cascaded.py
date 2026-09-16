"""Phase 8 policy-routed pipeline sharing the complete Phase 7 execution template."""

from visionguard.pipeline.review import MultimodalReviewPipeline
from visionguard.routing.policy import RoutingPolicy


class CascadedReviewPipeline(MultimodalReviewPipeline):
    def __init__(self, *args, routing_policy: RoutingPolicy, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.routing_policy = routing_policy

    def _build_routing_signals(self, detection, ocr, baseline, statuses):
        signals = self.routing_policy.collect_signals(detection, ocr, baseline, statuses)
        return signals.model_copy(
            update={
                "ocr_text_truncated_for_baseline": bool(
                    ocr and len(ocr.full_text) > self.config.max_ocr_chars_for_baseline
                )
            }
        )

    def _decide_route(self, signals):
        return self.routing_policy.decide(signals)
