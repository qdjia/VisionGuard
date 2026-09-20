# VisionGuard Project Report

## 1. Problem definition

Publishing moderation is a multimodal decision problem. A page can be risky because of an object, printed text, a symbol, or the relationship between image and text. A single detector misses semantics; OCR-only moderation misses visual evidence; sending every page to a VLM is expensive and hard to explain.

## 2. Project objectives

VisionGuard demonstrates an industry-style AI/CV workflow: configurable model adapters, typed interfaces, training and evaluation, reproducible inference, cascaded routing, explainable fusion, performance profiling, failure analysis and an inference-only service. It intentionally excludes account systems, databases and general CRUD.

## 3. System architecture

The system executes YOLO and OCR-derived text analysis before a routing decision. Clear low-risk cases may take a fast path; uncertain or conflicting evidence invokes a VLM. A separate fusion layer combines available evidence into the final typed moderation result. Every stage records status, timing and artifact provenance.

## 4. Module design

Each external model is hidden behind a provider or engine boundary. Pydantic schemas define data exchanged between modules. YAML configuration owns paths, thresholds and policies. CLIs call the same library components used by evaluation and API code, reducing behavior drift.

## 5. Object detection

The detection module wraps Ultralytics YOLO with configurable classes, confidence/IoU thresholds, device selection, warmup and visualization. Training validates dataset contracts and stores configuration, metrics and checkpoints per experiment. Validation reports precision, recall, mAP@0.5 and mAP@0.5:0.95.

The included detector experiment is only a synthetic smoke run: four training, two validation and two test images over one epoch. Its test mAP@0.5 is 0.0603, so it proves the workflow rather than useful model quality.

## 6. OCR

The OCR module supports paths and OpenCV arrays, full-image recognition and ROI recognition. It preserves the native quadrilateral polygon and derives an axis-aligned box. ROI-local coordinates are offset back into the original image coordinate system before being returned. Confidence filtering retains raw and filtered counts, while stable timing fields support later profiling. CER provides a lightweight text-recognition metric.

## 7. Traditional text baseline

OCR text can be scored by a TF-IDF + GBDT classifier. This model is deliberately simple: it creates a reproducible comparison and a cheap routing signal. On the synthetic eight-item validation split it achieved precision 1.0, recall 0.75 and F1 0.8571. That small result must not be read as real-world accuracy.

## 8. Vision-language model

The VLM layer is provider-neutral. The pipeline passes an image, bounded detection/OCR/baseline context and a versioned moderation policy. Returned text is treated as untrusted: JSON is extracted, normalized and validated into a strict Pydantic result, with bounded retry and explicit failure status. The recorded three-image smoke produced valid structures for all samples with mean latency 6.61 seconds.

## 9. Multimodal pipeline

The full pipeline loads an image once, runs its stages, records module-level success/failure/timing, builds bounded VLM context and produces a final result plus artifacts. Partial failures are represented rather than silently discarded. The three-image integration run completed without module failure, but the dataset is too small for a quality claim.

## 10. Dynamic routing

The router consumes normalized Stage 1 signals and decides `call_vlm`. Fast-path eligibility is conservative: only explicit, consistent low-risk evidence may bypass the VLM; conflicts, missing evidence or possible risk escalate. Routing policy and signals are stored for audit. In the three-sample Phase 8 comparison, VLM call rate dropped from 100% to 66.7% and observed mean latency dropped 35.2%, with no unsafe fast pass in that tiny set.

## 11. Risk fusion

Routing and fusion are separate concerns. Fusion normalizes detector, OCR/baseline, VLM and rule evidence; applies versioned weights and overrides; and produces a decision with evidence provenance. Offline replay, strategy comparison, threshold sweeps and ablation operate on saved records. The three-sample evaluation reached perfect recorded metrics, which validates mechanics only.

## 12. Benchmarking

The benchmark harness measures warmup separately, stage latency, end-to-end P50/P95, throughput, GPU peak memory and VLM call rate. Batch-size experiments have structured CSV/JSON output. The recorded Phase 10 two-sample, one-run profile found VLM responsible for about 91.2% of full-pipeline latency. Cascaded mode called the VLM for both samples and was about 1.0% slower, demonstrating why routing benefits depend on the input mix.

## 13. Error analysis

The unified analyzer compares prediction records with ground truth, attributes failures to typed stages and exports JSONL, visual evidence, hard cases and regression candidates. Its taxonomy contains 84 failure codes under nine top-level stages. Phase 11 validation produced two diagnostic cases and one eligible regression candidate from three labeled samples. This establishes traceability, not a population error rate.

## 14. Inference API

FastAPI exposes `POST /v1/review`, `GET /health/live`, `GET /health/ready`, `GET /meta`, and interactive `/docs`. Application lifespan initializes one shared pipeline and performs warmup before readiness. A bounded admission controller prevents unbounded GPU contention, while request and model timeouts remain distinct. Authentication and persistence remain deployment responsibilities.

## 15. Evaluation strategy

Metrics are stage-specific: detection precision/recall/mAP, OCR CER, text precision/recall/F1, VLM structural success and task agreement, routing VLM-call/skip/unsafe-fast-pass rates, fusion accuracy/category F1, and system latency/throughput/memory. Every headline number is paired with sample count and evidence level. Smoke results are never promoted to production claims.

## 16. Engineering decisions

The most important decisions are stable typed schemas, provider adapters, configuration-driven thresholds, separation of routing from fusion, conservative fast paths, saved intermediate artifacts, deterministic small fixtures and heavyweight-model isolation in tests. These choices optimize maintainability and experimental iteration rather than UI breadth.

## 17. Limitations

The public data is synthetic and extremely small; the detector is not trained to useful quality; OCR lacks full layout modeling; the baseline is lexical; the VLM is slow on consumer hardware; routing and fusion are not calibrated on representative data; and current benchmark percentiles lack repeated runs. The service is single-node and inference-only.

## 18. Future work

The next research steps are rights-cleared data curation, stronger annotations, held-out calibration, layout-aware OCR, smaller or quantized VLM comparison, repeated performance trials, asynchronous GPU scheduling, category-level hard-case regression and drift monitoring. Deployment controls should be added only for a real target environment.

## 19. Conclusion

VisionGuard's contribution is not a claim of production moderation accuracy. It is a coherent experimental system that makes multimodal decisions measurable, replaceable, explainable and testable. It demonstrates the full path from model components to evaluation, performance diagnosis, failure feedback and serving.
