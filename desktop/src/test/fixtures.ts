import type { ReviewResponse, SelectedImage } from "../api/types";

export const selectedImage: SelectedImage = {
  file: new File(["image"], "sample.png", { type: "image/png" }), name: "sample.png", mimeType: "image/png", size: 5, width: 640, height: 480, previewUrl: "blob:preview",
};

export function reviewFixture(overrides: Partial<ReviewResponse> = {}): ReviewResponse {
  return {
    api_version: "v1", request_id: "req-1", run_id: "run-1", status: "completed",
    result: { risk_level: "low", risk_score: 0.12, categories: [], requires_manual_review: false, reason: "未发现实质风险证据。", decision_source: "fusion" },
    routing: { route: "fast_path", call_vlm: false, reason_codes: ["safe_consensus"] },
    modules: { detector: "success", ocr: "success", baseline: "success", vlm: "skipped", fusion: "success" },
    timing: { request_total_ms: 120, queue_wait_ms: 1, inference_ms: 110, response_serialization_ms: 2, pipeline_total_ms: 108, detector_ms: 20, ocr_ms: 50, baseline_ms: 4, routing_ms: 1, vlm_ms: 0, fusion_ms: 2 },
    metadata: { pipeline_mode: "cascaded", pipeline_version: "v2", routing_policy_version: "routing_v1", fusion_policy_version: "fusion_v1", prompt_version: "prompt_v1" },
    artifact_saved: false, artifact_id: null,
    details: { image_width: 640, image_height: 480, detections: [{ class_name: "weapon", confidence: .82, bbox: { x1: 10, y1: 20, x2: 100, y2: 120 } }], ocr_block_count: 1, ocr_text_length: 4, mean_ocr_confidence: .94, ocr_blocks: [{ text: "测试文本", confidence: .94, polygon: [[20, 30], [120, 30], [120, 60], [20, 60]], bbox: { x1: 20, y1: 30, x2: 120, y2: 60 } }], ocr_full_text: "测试文本", baseline_label: "safe", baseline_probability: .9, vlm_risk_level: null, vlm_categories: [], vlm_confidence: null, vlm_reason: null, vlm_evidence: [], fusion_scores: { visual: .3, text: .1, vlm: null }, fusion_weights: { visual: .5, text: .5, vlm: null }, fusion_reason_codes: ["safe_consensus"], fusion_evidence: [], fusion_sources: ["visual", "text"] },
    ...overrides,
  };
}

export const safeReview = reviewFixture();
export const fastPathReview = reviewFixture();
export const partialReview = reviewFixture({ status: "partial" });
export const riskyReview = reviewFixture({
  result: {
    risk_level: "high",
    risk_score: 0.91,
    categories: [{ name: "weapon", score: 0.88 }],
    requires_manual_review: true,
    reason: "视觉与语义证据表明内容需要复核。",
    decision_source: "fusion",
  },
  routing: { route: "full_pipeline", call_vlm: true, reason_codes: ["high_risk_visual"] },
});
