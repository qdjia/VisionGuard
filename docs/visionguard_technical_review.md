# VisionGuard Technical Review: Phases 1–12

This document is a phase-by-phase review for project defense and interviews. Metrics and limitations are intentionally conservative.

## Phase 1 — Architecture, configuration and schemas

- **Goal:** establish boundaries before model code.
- **Implementation:** `src/visionguard` package layout, YAML loading, logging, shared Pydantic models, error hierarchy and public defaults.
- **Design:** configuration owns environment-specific values; schemas own cross-module contracts.
- **Concepts:** dependency inversion, validation at boundaries, reproducible configuration.
- **Problem encountered:** model libraries expose inconsistent data shapes and naming.
- **Solution:** normalize external outputs at adapter boundaries and never pass vendor objects upstream.
- **Interview Q:** Why start with schemas? **A:** They make components replaceable and tests deterministic before heavyweight dependencies exist.
- **Follow-up:** Why Pydantic rather than dictionaries? **A:** runtime validation, generated JSON schema, serialization and explicit optionality.
- **Current limit:** configuration composition is file-based; there is no remote registry or experiment database.

## Phase 2 — YOLO single-model inference

- **Goal:** provide stable detector inference independent of Ultralytics result objects.
- **Implementation:** one-time model load, device/precision selection, warmup, thresholds, typed boxes/detections/timing and visualization.
- **Design:** class names come from `classes.yaml`; business code does not hard-code categories.
- **Concepts:** letterboxing/model preprocessing, confidence, IoU/NMS, device synchronization and inference timing.
- **Problem encountered:** paths, ndarrays and color formats need one predictable contract.
- **Solution:** centralized image loading and validation returns BGR arrays.
- **Interview Q:** What does confidence threshold change? **A:** precision/recall balance before/around NMS; it does not improve learned features.
- **Follow-up:** Why warm up? **A:** lazy kernel allocation and caches distort the first measured inference.
- **Current limit:** public repository does not ship a useful trained checkpoint.

## Phase 3 — Detection dataset, training and evaluation

- **Goal:** make detector experiments repeatable rather than notebook-only.
- **Implementation:** dataset validation, train/validation/test configuration, experiment directories, metric extraction, checkpoint retention and error export.
- **Design:** every experiment stores resolved configuration and metrics next to weights.
- **Concepts:** split isolation, mAP@0.5 versus mAP@0.5:0.95, seed control and leakage prevention.
- **Problem encountered:** smoke data can verify code while producing misleading metrics.
- **Solution:** tag it as synthetic smoke evidence and report sample counts and limitations.
- **Interview Q:** Why use both mAP variants? **A:** mAP@0.5 measures coarse localization; the 0.5:0.95 average penalizes inaccurate boxes.
- **Follow-up:** Why not tune on test? **A:** it leaks selection decisions and invalidates the final estimate.
- **Current limit:** the eight-image smoke dataset cannot establish detector quality.

## Phase 4 — OCR

- **Goal:** produce reusable text and geometry for text review and multimodal reasoning.
- **Implementation:** PaddleOCR provider, full/ROI inference, polygon and bbox schemas, confidence filtering, reading-order approximation, timing, visualization and CER.
- **Design:** the engine is provider-neutral and initialized once.
- **Concepts:** quadrilateral geometry, edit distance, coordinate systems and OCR detection/recognition separation.
- **Problem encountered:** ROI OCR returns local coordinates that are unsafe for downstream fusion.
- **Solution:** sanitize the crop, add `(roi_x1, roi_y1)` to every polygon point, then derive the global bbox.
- **Interview Q:** Why retain polygon and bbox? **A:** polygon preserves rotation/layout; bbox simplifies intersection, ROI and visualization logic.
- **Follow-up:** Why not apply aggressive preprocessing by default? **A:** PaddleOCR has learned preprocessing and strong transforms can remove useful strokes.
- **Current limit:** reading order is heuristic and CER smoke evidence has one synthetic sample.

## Phase 5 — TF-IDF + GBDT baseline

- **Goal:** create a cheap, interpretable comparison for VLM-based review.
- **Implementation:** text normalization, TF-IDF features, gradient-boosted classifier, train/evaluate/infer CLIs, threshold sweep and error export.
- **Design:** model and vectorizer are persisted as a versioned bundle with metadata.
- **Concepts:** sparse lexical features, class probability thresholding, precision/recall/F1 and stratified splits.
- **Problem encountered:** tiny data makes perfect test metrics unstable.
- **Solution:** use validation F1 0.8571 as the primary small-experiment result and disclose eight samples.
- **Interview Q:** Why keep a weaker baseline? **A:** it quantifies the marginal value and cost of semantic modeling.
- **Follow-up:** What does TF-IDF miss? **A:** word order, visual semantics, paraphrase and cross-modal context.
- **Current limit:** sample data is synthetic and not representative of publishing language.

## Phase 6 — VLM adapter and structured review

- **Goal:** add semantic image-text analysis without coupling business code to one model.
- **Implementation:** provider protocol, local and mock providers, context builder, prompt versions, Pydantic moderation result, JSON repair/retry and evaluation.
- **Design:** bound image size, detection count, OCR blocks and characters before prompting.
- **Concepts:** multimodal prompting, constrained contracts, failure handling and prompt injection resistance.
- **Problem encountered:** generative models can wrap JSON, omit fields or repeat untrusted OCR instructions.
- **Solution:** label OCR as evidence, extract/normalize candidates and validate with bounded retries.
- **Interview Q:** Is Pydantic enough to guarantee correct semantics? **A:** no; it guarantees shape, while evaluation and fusion policies address meaning.
- **Follow-up:** Why a mock provider? **A:** deterministic contract tests without model download, GPU memory or long latency.
- **Current limit:** the local provider is slow and the three-image smoke set is too small for quality assessment.

## Phase 7 — Multimodal review pipeline

- **Goal:** orchestrate detector, OCR, baseline and VLM into one traceable run.
- **Implementation:** component factory, module statuses, bounded context, artifact store, timing and final result assembly.
- **Design:** modules return typed empty results or explicit failures; initialization is outside per-image inference.
- **Concepts:** orchestration, partial failure, idempotent artifacts and latency decomposition.
- **Problem encountered:** a failure in one module should not erase successful evidence from others.
- **Solution:** record per-stage status/error and allow policy-controlled degradation.
- **Interview Q:** Why store intermediate output? **A:** auditability, error attribution, replay and cheaper downstream experiments.
- **Follow-up:** What must not be stored blindly? **A:** private images, secrets and unrestricted model prompts/responses.
- **Current limit:** pipeline execution is mostly sequential after initial feature extraction and targets one host.

## Phase 8 — Cascaded inference and dynamic routing

- **Goal:** reduce expensive VLM calls while preserving safety.
- **Implementation:** typed routing signals, conservative policy, fast path, full/cascaded comparison, threshold sweep and routing-error export.
- **Design:** uncertainty or disagreement escalates; only consistent low-risk evidence skips.
- **Concepts:** selective prediction, cost-sensitive classification, coverage-risk trade-off and unsafe fast pass.
- **Problem encountered:** maximizing skip rate alone can hide dangerous false negatives.
- **Solution:** make unsafe-fast-pass rate a first-class metric and keep safety overrides.
- **Interview Q:** What determines expected latency benefit? **A:** skip probability times avoided VLM cost minus routing overhead.
- **Follow-up:** Why did another benchmark show no gain? **A:** both benchmark images invoked VLM, so there was no expensive stage to skip.
- **Current limit:** observed 35.2% latency reduction comes from only three samples.

## Phase 9 — Risk fusion

- **Goal:** transform heterogeneous evidence into an explainable final decision.
- **Implementation:** evidence normalization, configured weights, risk thresholds, overrides, provenance, strategy comparison, ablation, sweep and replay.
- **Design:** final decision logic is independent from the decision to call VLM.
- **Concepts:** score calibration, late fusion, decision boundaries and evidence conflict.
- **Problem encountered:** confidence values from different models are not naturally comparable.
- **Solution:** normalize by source semantics, keep source-specific rules and expose rather than hide conflict.
- **Interview Q:** Why not let the VLM make the final decision? **A:** deterministic policy, auditability and safe degradation would be weaker.
- **Follow-up:** When should weights be learned? **A:** after collecting a representative calibrated validation set and defining the cost function.
- **Current limit:** current weights are policy-engineered and the evaluation has three samples.

## Phase 10 — Batch benchmark and profiling

- **Goal:** locate system bottlenecks and quantify workload-dependent performance.
- **Implementation:** warmup and measured runs, batch-size sweep, module/end-to-end timing, P50/P95, throughput, GPU peak memory and CSV/JSON reports.
- **Design:** initialization is excluded from inference latency and GPU synchronization surrounds timing where required.
- **Concepts:** latency versus throughput, warmup, percentile stability, batching and memory pressure.
- **Problem encountered:** tiny one-run benchmarks make percentiles degenerate.
- **Solution:** label results as smoke and document that repeated runs are required.
- **Interview Q:** What did profiling reveal? **A:** VLM consumed about 91.2% of full-pipeline latency in the recorded two-sample run.
- **Follow-up:** Why can batch size hurt? **A:** longer padding/generation, memory contention and sequential internal stages can outweigh parallelism.
- **Current limit:** no statistically stable batch 1/4/8/16 production benchmark is claimed.

## Phase 11 — Systematic error analysis

- **Goal:** convert failures into actionable data and regression tests.
- **Implementation:** ground-truth comparison, cross-stage attribution, 84-code taxonomy, visual/error exports, hard-case manifest, replay and live regression.
- **Design:** distinguish prediction errors from insufficient evidence, system failure and non-evaluable cases.
- **Concepts:** failure taxonomy, root-cause attribution, data flywheel and regression curation.
- **Problem encountered:** the final wrong label does not reveal which upstream stage caused it.
- **Solution:** preserve stage evidence/status and apply deterministic attribution rules with manual-verification state.
- **Interview Q:** Why not store only false positives and false negatives? **A:** it loses localization, OCR, routing, schema and system failure modes.
- **Follow-up:** What makes a good hard case? **A:** verified annotation, stable input hash, clear failure rationale and future regression value.
- **Current limit:** Phase 11 validation had only three ground-truth samples and two diagnostic cases.

## Phase 12 — FastAPI inference service

- **Goal:** expose the pipeline with production-style lifecycle and failure semantics.
- **Implementation:** single-image review, liveness/readiness/meta endpoints, interactive OpenAPI docs, lifespan load/warmup, bounded concurrency, timeouts, request validation and structured errors.
- **Design:** one process owns one model set on a single GPU; library pipeline remains independent from HTTP.
- **Concepts:** application lifecycle, backpressure, readiness, observability and partial batch failure.
- **Problem encountered:** multiple workers or unbounded requests duplicate/exhaust GPU memory.
- **Solution:** one worker plus an in-process admission limit, with overload surfaced explicitly.
- **Interview Q:** Why separate request and model timeouts? **A:** queueing/upload time and inference execution fail for different reasons and need different metrics.
- **Follow-up:** Why can a batch return HTTP 200 with item errors? **A:** the transport succeeded and useful per-item results remain; each item carries its own status.
- **Current limit:** no authentication, distributed queue, persistent audit store or multi-node scheduling is included.

## Cross-phase lessons

1. Stable schemas matter more than vendor-specific convenience objects.
2. A fast path must be evaluated by selective risk, not call reduction alone.
3. Routing, fusion and serving are distinct layers with different objectives.
4. Saved evidence makes experiments cheaper and failures explainable.
5. Every metric needs its data size, protocol and limitation beside it.

## Cross-cutting concept anchors

- **Preprocess / inference / postprocess:** measure them separately because image decoding and result parsing can dominate small-model latency even when GPU inference is fast.
- **Fail-open versus fail-closed:** VisionGuard does not convert missing evidence into low risk. A handled module failure becomes partial/manual review or escalation; fatal input failure stops the run.
- **Dependency injection:** factories construct providers once and inject interfaces into pipeline/API code, enabling mocks and avoiding import-time model loading.
- **Run ID versus request ID:** run ID identifies model execution/artifacts; request ID identifies HTTP tracing. A batch request can own multiple model runs.
- **Dynamic weight normalization:** when an evidence source is absent, its configured weight is removed and remaining available weights are renormalized; absence is not a zero-risk vote.
- **CUDA synchronization:** benchmark timing synchronizes asynchronous kernels before reading the clock; production inference should not add synchronization blindly.
- **P95/P99:** tail percentiles need many measured observations. A one-run smoke cannot estimate them even if a report field exists.
- **Semaphore and `queue_wait_ms`:** the semaphore bounds active full inference; queue wait is measured separately so overload is not mistaken for model latency.
- **HTTP partial semantics:** a handled partial result can be HTTP 200 with explicit item/module status; malformed input is 4xx and unhandled service failure is 5xx.
