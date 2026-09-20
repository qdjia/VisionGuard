# Experiments and Evidence

This document explains how VisionGuard results were obtained and how strongly they can be used.
Raw experiment directories are generated locally under `artifacts/` and are intentionally ignored
by Git. The tables preserve the relevant values so the repository does not depend on ignored files
being present.

## Evidence levels

| Level | Meaning | Use in this project |
|---|---|---|
| A | Repeated engineering evaluation on a sufficiently sized, independently annotated set | No moderation-quality result currently qualifies |
| B | Small engineering validation of behavior, metrics, and data flow | Baseline, Pipeline, Routing, Fusion, Error Analysis |
| C | Smoke test for integration, latency, or one-off execution | Detector, OCR, VLM latency, Benchmark, API |

An evidence level applies to a result, not to the sophistication of the implementation. A module
can be fully engineered while its available evaluation remains Level B or C.

## Detection

**Purpose:** verify dataset validation, YOLO training, validation/test metrics, checkpoints,
TensorBoard-compatible Ultralytics logs, inference, and error-case export.

| Field | Value |
|---|---|
| Evidence | Level C — one-epoch smoke |
| Dataset | Script-generated rectangles, one class (`synthetic_risk_region`) |
| Split | 4 train / 2 validation / 2 test images |
| Training | 1 epoch, seed 42, CUDA |
| Validation | Precision 0.0033, Recall 1.0, mAP@0.5 0.0406, mAP@0.5:0.95 0.0366 |
| Test | Precision 0.0033, Recall 1.0, mAP@0.5 0.0603, mAP@0.5:0.95 0.0498 |
| Recorded stack | Python 3.11.16, PyTorch 2.11.0+cu128, Ultralytics 8.4.151 |

The deliberately tiny one-epoch run has very poor precision and is not a usable moderation
detector. It proves that the configured training/evaluation path records the requested metrics and
produces loadable checkpoints. Real detection claims require a substantially larger, class-balanced,
annotated dataset.

## OCR

**Purpose:** validate full-image OCR, ROI coordinate offsetting, confidence filtering, visualization,
timing, and CER evaluation.

| Field | Value |
|---|---|
| Evidence | Level C — one synthetic image |
| Dataset | One script-generated Chinese/English text image for CER; separate smoke images |
| Result | CER 0.0 on the single Chinese evaluation sample |
| Provider | PaddleOCR |

CER 0.0 on one clean rendered image is an integration check, not evidence of robust OCR on scans,
curved text, degradation, dense layouts, or diverse typography.

## TF-IDF + GBDT text baseline

**Purpose:** provide a lightweight comparison point for VLM experiments and validate training,
persistence, batched inference, evaluation, error export, and threshold sweep.

| Field | Value |
|---|---|
| Evidence | Level B — small synthetic validation |
| Dataset | 36 self-authored text samples |
| Split | 20 train / 8 validation / 8 test |
| Features | Character TF-IDF 2–4 grams, 390 features |
| Model | GradientBoostingClassifier |
| Validation at threshold 0.5 | Precision 1.0, Recall 0.75, F1 0.8571, Accuracy 0.875 |
| Validation confusion matrix | TN=4, FP=0, FN=1, TP=3 |
| Test at threshold 0.5 | Precision/Recall/F1 1.0 on 8 samples |
| Threshold sweep | Best validation F1 threshold 0.1; formal threshold intentionally unchanged |

The validation result is the primary reported baseline value because it exposes one false negative.
The perfect eight-sample test result is retained for completeness but is too small and synthetic to
support a quality claim. The classifier probability is not calibrated.

## VLM structured moderation

**Purpose:** validate local Qwen3-VL loading, provider abstraction, structured output parsing,
Pydantic/policy validation, retry accounting, bbox normalization, and prompt-injection boundaries.

| Field | Value |
|---|---|
| Evidence | Level B for schema behavior; Level C for latency |
| Dataset | 3 synthetic images: 2 low-risk, 1 high-risk text image |
| Model | Local Qwen3-VL-2B-Instruct |
| Hardware | RTX 4060 Laptop GPU, BF16 |
| First-try valid | 3/3 |
| Structured success | 3/3 |
| Final failures | 0/3 |
| Mean latency | 6608.31 ms |
| Manual review | 1/3 |

Seven additional smoke contexts completed in approximately 5.9–14.5 seconds each. A single
conflict-injection case asked the model, through OCR content, to downgrade a risky image; the output
remained high risk and required manual review. This is one observed case, not proof of universal
prompt-injection resistance. Model-reported confidence and bbox estimates are uncalibrated.

## Full multimodal pipeline

**Purpose:** validate end-to-end data flow, module failure isolation, partial results, run IDs,
timing, structured artifacts, and evaluation metrics.

| Field | Value |
|---|---|
| Evidence | Level B — 3-sample engineering validation |
| Dataset | Same 3 synthetic VLM evaluation images |
| Hardware | RTX 4060 Laptop GPU; PaddleOCR on CPU |
| Mean total latency | 15479.49 ms |
| P50 / P95 | 16788.03 / 21174.29 ms |
| Mean VLM latency | 14153.03 ms |
| Failure / partial rate | 0 / 0 |

Risk/category metrics were 1.0 on these three samples, but they are intentionally not promoted as
model-quality results. The meaningful result is that the complete structured path and failure
semantics executed successfully.

## Cascaded routing

**Purpose:** compare always-VLM and rule-based cascaded execution over the same initialized models
and samples.

| Metric | Full | Cascaded |
|---|---:|---:|
| Samples | 3 | 3 |
| VLM call rate | 100.0% | 66.7% |
| VLM skip rate | 0.0% | 33.3% |
| Mean latency | 20132.14 ms | 13054.70 ms |
| P50 latency | 22248.11 ms | 9468.03 ms |
| P95 latency | 27358.02 ms | 25949.08 ms |
| Unsafe fast pass | 0 | 0 |

The mean latency reduction, computed from the stored comparison, is **35.15%**. This is Level B
behavioral evidence and Level C performance evidence because there are only three synthetic samples.
The 0 unsafe-fast-pass count is not a bound on real-world false negatives.

## Risk fusion

**Purpose:** validate separate routing/fusion responsibilities, dynamic normalization over available
sources, conflicts, safety overrides, replay, ablation, and parameter sweep.

| Field | Value |
|---|---|
| Evidence | Level B — 3 synthetic samples |
| Strategy | `weighted`, policy `fusion_v1` |
| Risk accuracy | 1.0 |
| Category micro F1 | 1.0 |
| Manual-review rate | 33.3% |
| Near-boundary rate | 33.3% |
| Unsafe fused low | 0 |

Five ablation settings, six threshold/weight combinations, strategy comparison, and historical
artifact replay were exercised. These experiments validate the analysis tooling; three samples
cannot establish that weighted fusion outperforms a VLM on real publishing data.

## Batch benchmark and profiling

**Purpose:** measure cold start, synchronized steady-state latency, throughput, module shares, and
GPU memory while making true/sequential/mixed batching explicit.

Recorded environment: Windows 10, Python 3.11.16, PyTorch 2.11.0+cu128, CUDA 12.8,
Transformers 4.57.6, Ultralytics 8.4.151, PaddleOCR 3.7.0, RTX 4060 Laptop GPU with
8187.5 MiB.

| Mode | Batch | Samples | Measured runs | Batch latency | Throughput | VLM rate | Peak GPU |
|---|---:|---:|---:|---:|---:|---:|---:|
| Cascaded smoke | 1 | 1 | 1 | 7849.80 ms | 0.127 images/s | 100% | 6309.1 MiB |
| Cascaded smoke | 2 | 2 | 1 | 17398.41 ms | 0.115 images/s | 100% | 4588.7 MiB |
| Full comparison | 2 | 2 | 1 | 16218.14 ms | 0.123 images/s | 100% | 4593.4 MiB |
| Cascaded comparison | 2 | 2 | 1 | 16383.42 ms | 0.122 images/s | 100% | 4593.4 MiB |

For the fair batch-2 comparison, Full module shares were YOLO 0.08%, OCR 8.69%, Baseline 0.01%,
VLM 91.21%, and Fusion below 0.01%. Cascaded VLM share was 90.57%. All samples used the VLM, so
cascading did not reduce calls and was 1.02% slower within ordinary one-run variation. Batch 2 did
not improve throughput because OCR and VLM remain sequential. These are Level C smoke results;
P50/P95/P99 are identical when only one measured run exists.

## Systematic error analysis

**Purpose:** attribute observable failures without claiming causality, retain partial ground truth,
build hard cases, and replay policies without model execution.

| Field | Value |
|---|---|
| Evidence | Level B/C — 3 GT records |
| Taxonomy | 84 failure types across 9 top-level stages |
| Diagnostic cases | 2 |
| Hard cases | 2 |
| Regression candidates | 1 |
| Offline replay | 3 unchanged; `models_executed=false` |
| Live hard-case regression | 2 total: 1 still failing, 1 not evaluable |

The three GT records produced no end-to-end classification errors, but that rate is deliberately not
used as a headline. The useful deliverable is the attribution, replay, reporting, and regression
framework. OCR/detector-specific FP/FN claims are disabled when their ground truth is absent.

## FastAPI service

**Purpose:** validate production-style lifecycle and transport semantics without claiming production
deployment.

| Field | Value |
|---|---|
| Evidence | Level C real-model smoke + automated engineering tests |
| Initialization | One shared model initialization per application lifespan |
| Smoke | live, ready, meta, safe cascaded, risky cascaded, safe full, invalid upload |
| Observed HTTP results | Valid reviews 200; invalid image 400 |
| Concurrency | Default semaphore capacity 1 |
| Traceability | Separate request ID and run ID |

The smoke used the same RTX 4060/local model stack. API timing varies by input and generation; the
service is documented as production-style rather than production-ready. It has no authentication,
rate limiting, distributed queue, multi-GPU scheduler, or hard CUDA cancellation.

## What can be stated publicly

Safe statements:

- The repository implements and tests the complete modular multimodal pipeline.
- The small routing experiment observed a 33.3% VLM skip rate and 35.15% lower mean latency.
- The synchronized benchmark identified the VLM as the dominant latency bottleneck.
- The project includes replayable fusion experiments and systematic error attribution.
- The API initializes models once and bounds GPU inference concurrency.

Unsupported statements:

- Production accuracy, production readiness, or large-scale deployment.
- A statistically reliable false-negative rate.
- A general 35% performance improvement on publishing content.
- Calibrated probabilities from VLM confidence or fusion score.
- Prompt-injection immunity.

