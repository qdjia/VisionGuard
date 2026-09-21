"""Versioned public API schemas isolated from internal pipeline contracts."""

from typing import Any, Literal

from pydantic import ConfigDict, Field

from visionguard.schemas.common import BoundingBox, SchemaModel


class APIErrorBody(SchemaModel):
    code: str
    message: str
    request_id: str
    run_id: str | None = None
    details: dict[str, Any] | None = None


class APIErrorResponse(SchemaModel):
    error: APIErrorBody


class APICategory(SchemaModel):
    name: str
    score: float = Field(ge=0, le=1)


class APIReviewDecision(SchemaModel):
    risk_level: Literal["low", "medium", "high"] | None
    risk_score: float | None = Field(default=None, ge=0, le=1)
    categories: list[APICategory]
    requires_manual_review: bool
    reason: str
    decision_source: str


class APIRoutingSummary(SchemaModel):
    route: str
    call_vlm: bool
    reason_codes: list[str]


class APITiming(SchemaModel):
    request_total_ms: float = Field(ge=0)
    queue_wait_ms: float = Field(ge=0)
    inference_ms: float = Field(ge=0)
    response_serialization_ms: float = Field(ge=0)
    pipeline_total_ms: float = Field(ge=0)
    detector_ms: float = Field(ge=0)
    ocr_ms: float = Field(ge=0)
    baseline_ms: float = Field(ge=0)
    routing_ms: float = Field(ge=0)
    vlm_ms: float = Field(ge=0)
    fusion_ms: float = Field(ge=0)


class APIResponseMetadata(SchemaModel):
    pipeline_mode: Literal["full", "cascaded"]
    pipeline_version: str
    routing_policy_version: str | None
    fusion_policy_version: str | None
    prompt_version: str | None


class APIDetectionDetail(SchemaModel):
    class_name: str
    confidence: float = Field(ge=0, le=1)
    bbox: BoundingBox


class APIOCRBlockDetail(SchemaModel):
    text: str
    confidence: float = Field(ge=0, le=1)
    polygon: list[tuple[float, float]] = Field(min_length=4)
    bbox: BoundingBox


class APIVLMEvidenceDetail(SchemaModel):
    type: str
    description: str
    bbox: BoundingBox | None = None
    text: str | None = None


class APIFusionEvidenceDetail(SchemaModel):
    source: str
    description: str
    score: float | None = Field(default=None, ge=0, le=1)
    category: str | None = None


class APIFusionValues(SchemaModel):
    visual: float | None = Field(default=None, ge=0, le=1)
    text: float | None = Field(default=None, ge=0, le=1)
    vlm: float | None = Field(default=None, ge=0, le=1)


class APIDetails(SchemaModel):
    image_width: int = Field(gt=0)
    image_height: int = Field(gt=0)
    detections: list[APIDetectionDetail] = Field(default_factory=list)
    ocr_block_count: int = Field(ge=0)
    ocr_text_length: int = Field(ge=0)
    mean_ocr_confidence: float | None = Field(default=None, ge=0, le=1)
    ocr_blocks: list[APIOCRBlockDetail] = Field(default_factory=list)
    ocr_full_text: str = ""
    baseline_label: str | None = None
    baseline_probability: float | None = Field(default=None, ge=0, le=1)
    vlm_risk_level: str | None = None
    vlm_categories: list[str] = Field(default_factory=list)
    vlm_confidence: float | None = Field(default=None, ge=0, le=1)
    vlm_reason: str | None = None
    vlm_evidence: list[APIVLMEvidenceDetail] = Field(default_factory=list)
    fusion_scores: APIFusionValues | None = None
    fusion_weights: APIFusionValues | None = None
    fusion_reason_codes: list[str] = Field(default_factory=list)
    fusion_evidence: list[APIFusionEvidenceDetail] = Field(default_factory=list)
    fusion_sources: list[str] = Field(default_factory=list)


class APIReviewResponse(SchemaModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "api_version": "v1",
                    "request_id": "8b4f53cb4ab1438ea399a27667a98ec4",
                    "run_id": "d8ef86ef445b4f0d91ac31e3bff8fd3e",
                    "status": "completed",
                    "result": {
                        "risk_level": "low",
                        "risk_score": 0.12,
                        "categories": [],
                        "requires_manual_review": False,
                        "reason": "No material risk evidence was found.",
                        "decision_source": "fusion",
                    },
                    "routing": {
                        "route": "fast_path",
                        "call_vlm": False,
                        "reason_codes": ["safe_consensus"],
                    },
                    "modules": {
                        "detector": "success",
                        "ocr": "success",
                        "baseline": "success",
                        "vlm": "skipped",
                    },
                    "timing": {
                        "request_total_ms": 412.2,
                        "queue_wait_ms": 0.1,
                        "inference_ms": 408.0,
                        "response_serialization_ms": 0.4,
                        "pipeline_total_ms": 407.0,
                        "detector_ms": 32.0,
                        "ocr_ms": 350.0,
                        "baseline_ms": 2.0,
                        "routing_ms": 0.5,
                        "vlm_ms": 0.0,
                        "fusion_ms": 0.6,
                    },
                    "metadata": {
                        "pipeline_mode": "cascaded",
                        "pipeline_version": "v2",
                        "routing_policy_version": "routing_v1",
                        "fusion_policy_version": "fusion_v1",
                        "prompt_version": "v1",
                    },
                    "artifact_saved": True,
                    "artifact_id": "d8ef86ef445b4f0d91ac31e3bff8fd3e",
                    "details": None,
                }
            ]
        },
    )

    api_version: Literal["v1"] = "v1"
    request_id: str
    run_id: str
    status: Literal["completed", "partial", "failed"]
    result: APIReviewDecision
    routing: APIRoutingSummary | None
    modules: dict[str, Literal["success", "failed", "skipped"]]
    timing: APITiming
    metadata: APIResponseMetadata
    artifact_saved: bool
    artifact_id: str | None = None
    details: APIDetails | None = None


class LiveResponse(SchemaModel):
    status: Literal["ok"] = "ok"


class ReadyResponse(SchemaModel):
    status: Literal["ready"] = "ready"
    components: dict[str, bool]


class MetaResponse(SchemaModel):
    api_version: str
    service_version: str
    pipeline_versions: dict[str, str]
    routing_policy_version: str | None
    fusion_policy_version: str | None
    prompt_version: str | None
    model_identifiers: dict[str, str | None]
    max_concurrent_inference: int
