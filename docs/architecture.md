# VisionGuard Architecture

VisionGuard is a modular engineering prototype for multimodal publishing-content moderation. It
combines visual detection, OCR, a lightweight text baseline, an optional vision-language model,
and an explainable fusion layer. The system is designed for experiments and portfolio review, not
as a claim of production moderation quality.

## System architecture

```mermaid
flowchart TD
    I[Input image] --> P[Image normalization]
    P --> D[YOLO detector]
    P --> O[PaddleOCR]
    O --> B[TF-IDF + GBDT baseline]
    D --> S[Stage 1 signals]
    O --> S
    B --> S
    S --> R[RoutingPolicy]
    R -->|Fast path candidate| G[Pre-fusion safety guard]
    R -->|VLM path| C[VLM context builder]
    G -->|Safe| F[RiskFusionEngine]
    G -->|Unsafe or uncertain| C
    C --> V[VLMProvider]
    V --> F
    D --> F
    O --> F
    B --> F
    F --> RR[Structured ReviewResult]
    RR --> API[FastAPI service]
    RR --> A[Versioned artifacts]
    RR --> E[Evaluation and error analysis]
```

YOLO and OCR operate on the same normalized image and are logically independent. The current
synchronous single-image pipeline executes them in a deterministic order for simpler failure
isolation. Batch benchmarking uses true batching only where the implementation supports it.

## Cascaded inference and routing

```mermaid
flowchart TD
    I[Image] --> Y[YOLO]
    I --> O[OCR]
    O --> B[Text baseline]
    Y --> S[RoutingSignals]
    O --> S
    B --> S
    S --> R{RoutingPolicy}
    R -->|High-confidence agreement| FP[Fast path candidate]
    R -->|Conflict, weak evidence, failure, or risk| VP[VLM path]
    FP --> SG{Fusion safety guard}
    SG -->|Stage 1 remains low risk| F[Final fusion]
    SG -->|Non-low or uncertain| VP
    VP --> V[VLM analysis]
    V --> F
    F --> M{Manual review required?}
    M -->|No| O1[Final decision]
    M -->|Yes| O2[Decision + review flag]
```

The VLM is deliberately optional rather than mandatory. A sample can skip it only when Stage 1
signals form a conservative low-risk consensus and the safety guard agrees. Missing evidence,
module failures, conflicts, or suspicious signals route to the VLM or manual review.

Routing and fusion have different responsibilities:

- Routing decides whether the expensive VLM should be called.
- Fusion decides the final risk level after all available evidence has been collected.
- A safety guard may override a proposed fast path before the final decision.

## Explainable fusion

```mermaid
flowchart TD
    V1[Visual score<br/>detection confidence × severity] --> N[Normalize weights over available evidence]
    T1[Text score<br/>baseline probability × OCR reliability] --> N
    L1[VLM score<br/>configured risk-level mapping] --> N
    N --> W[Weighted engineering risk score]
    W --> C{Conflict / failure / boundary checks}
    C --> R[Risk level mapping]
    C --> M[Manual-review decision]
    R --> P[Evidence provenance and reason codes]
    M --> P
    P --> F[FusionDecision]
```

`risk_score` is an engineering fusion score, **not a calibrated probability**. When a source is
unavailable, its weight is removed and the remaining weights are normalized. A failed module is
not treated as zero-risk evidence. Explicit conflicts, near-boundary decisions, and insufficient
evidence can force manual review.

## Training and experiment flow

```mermaid
flowchart LR
    DATA[Versioned configs and manifests] --> TRAIN[Detector / baseline training]
    DATA --> LIVE[Live model evaluation]
    TRAIN --> CKPT[Ignored local checkpoints]
    CKPT --> LIVE
    LIVE --> REC[Structured records and summaries]
    REC --> REPLAY[Offline routing / fusion replay]
    REC --> BENCH[Benchmark and profiling]
    REC --> ERR[Error attribution]
    ERR --> HARD[Hard-case manifest]
    HARD --> REG[Regression run]
    REPLAY --> REPORT[Reports]
    BENCH --> REPORT
    REG --> REPORT
```

Large models, generated artifacts, and local overrides are not tracked. Public manifests and small
synthetic fixtures are tracked so that a clean clone can inspect and regenerate the engineering
workflow. Experiment output directories reject non-empty targets to avoid silently overwriting a
previous run.

## Component ownership

| Component | Owns | Does not own |
|---|---|---|
| Detector | YOLO loading, preprocessing, detection parsing | OCR or moderation policy |
| OCR engine | OCR provider, confidence filtering, ROI coordinate remapping | Text moderation |
| Text baseline | Text normalization, TF-IDF, GBDT, thresholding | OCR execution |
| VLM provider | Prompt construction, generation, parsing, schema validation | Upstream models |
| RoutingPolicy | VLM-call decision and reason codes | Final risk decision |
| RiskFusionEngine | Final score, risk mapping, conflicts, review flag | Model execution |
| Pipeline | Orchestration, module isolation, timing, artifacts | Model construction |
| API | HTTP validation, concurrency, lifecycle, public schemas | Concrete model logic |

## Runtime lifecycle

The FastAPI application factory does not load models at import time. Lifespan startup builds one
shared Full/Cascaded pipeline pair, performs optional warmup, and marks the service ready. Requests
reuse the same model instances. The default semaphore permits one full inference at a time on the
single RTX 4060-class GPU. Shutdown stops new requests, waits for active work within a grace period,
then releases references and clears the CUDA allocator cache.

