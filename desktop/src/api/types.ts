export type RiskLevel = "low" | "medium" | "high";
export type PipelineMode = "cascaded" | "full";
export type ReviewStatus = "completed" | "partial" | "failed";
export type ModuleState = "success" | "failed" | "skipped";

export interface BoundingBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface Category {
  name: string;
  score: number;
}

export interface ReviewDecision {
  risk_level: RiskLevel | null;
  risk_score: number | null;
  categories: Category[];
  requires_manual_review: boolean;
  reason: string;
  decision_source: string;
}

export interface RoutingSummary {
  route: string;
  call_vlm: boolean;
  reason_codes: string[];
}

export interface ReviewTiming {
  request_total_ms: number;
  queue_wait_ms: number;
  inference_ms: number;
  response_serialization_ms: number;
  pipeline_total_ms: number;
  detector_ms: number;
  ocr_ms: number;
  baseline_ms: number;
  routing_ms: number;
  vlm_ms: number;
  fusion_ms: number;
}

export interface ReviewMetadata {
  pipeline_mode: PipelineMode;
  pipeline_version: string;
  routing_policy_version: string | null;
  fusion_policy_version: string | null;
  prompt_version: string | null;
}

export interface DetectionDetail {
  class_name: string;
  confidence: number;
  bbox: BoundingBox;
}

export interface OCRBlockDetail {
  text: string;
  confidence: number;
  polygon: [number, number][];
  bbox: BoundingBox;
}

export interface VLMEvidenceDetail {
  type: string;
  description: string;
  bbox: BoundingBox | null;
  text: string | null;
}

export interface FusionEvidenceDetail {
  source: string;
  description: string;
  score: number | null;
  category: string | null;
}

export interface FusionValues {
  visual: number | null;
  text: number | null;
  vlm: number | null;
}

export interface ReviewDetails {
  image_width: number;
  image_height: number;
  detections: DetectionDetail[];
  ocr_block_count: number;
  ocr_text_length: number;
  mean_ocr_confidence: number | null;
  ocr_blocks: OCRBlockDetail[];
  ocr_full_text: string;
  baseline_label: string | null;
  baseline_probability: number | null;
  vlm_risk_level: string | null;
  vlm_categories: string[];
  vlm_confidence: number | null;
  vlm_reason: string | null;
  vlm_evidence: VLMEvidenceDetail[];
  fusion_scores: FusionValues | null;
  fusion_weights: FusionValues | null;
  fusion_reason_codes: string[];
  fusion_evidence: FusionEvidenceDetail[];
  fusion_sources: string[];
}

export interface ReviewResponse {
  api_version: "v1";
  request_id: string;
  run_id: string;
  status: ReviewStatus;
  result: ReviewDecision;
  routing: RoutingSummary | null;
  modules: Record<string, ModuleState>;
  timing: ReviewTiming;
  metadata: ReviewMetadata;
  artifact_saved: boolean;
  artifact_id: string | null;
  details: ReviewDetails | null;
}

export interface APIErrorBody {
  code: string;
  message: string;
  request_id: string;
  run_id: string | null;
  details: Record<string, unknown> | null;
}

export interface APIErrorResponse {
  error: APIErrorBody;
}

export interface LiveResponse {
  status: "ok";
}

export interface ReadyResponse {
  status: "ready";
  components: Record<string, boolean>;
}

export interface MetaResponse {
  api_version: string;
  service_version: string;
  pipeline_versions: Record<string, string>;
  routing_policy_version: string | null;
  fusion_policy_version: string | null;
  prompt_version: string | null;
  model_identifiers: Record<string, string | null>;
  max_concurrent_inference: number;
  model_bundle_version?: string | null;
  runtime_version?: string | null;
}

export interface SelectedImage {
  file: File;
  name: string;
  mimeType: string;
  size: number;
  width: number;
  height: number;
  previewUrl: string;
  sourcePath?: string;
}

export interface ReviewInput {
  image: SelectedImage;
  mode: PipelineMode;
  includeDetails?: boolean;
  saveArtifacts?: boolean;
}

export interface BackendHealth {
  status: "ready";
  components: Record<string, boolean>;
}

export interface VisionGuardBackend {
  health(signal?: AbortSignal): Promise<BackendHealth>;
  meta(signal?: AbortSignal): Promise<MetaResponse>;
  review(input: ReviewInput, signal?: AbortSignal): Promise<ReviewResponse>;
}
