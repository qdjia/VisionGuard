# Resume-ready Project Description

Use only the version that fits the resume layout. Keep the evidence qualifiers when discussing metrics.

## Version A: compact (3–4 bullets)

**VisionGuard — Multimodal Publishing Content Moderation System**  
Python, PyTorch, Ultralytics YOLO, PaddleOCR, Transformers/Qwen-VL, scikit-learn, FastAPI

- Built a typed multimodal moderation pipeline combining YOLO detection, full/ROI OCR, a TF-IDF+GBDT baseline and a provider-neutral VLM adapter; standardized cross-stage results with Pydantic and configuration-driven policies.
- Designed conservative cascaded routing and explainable risk fusion with signal provenance, offline replay and ablation; on a three-sample engineering experiment, reduced VLM calls from 100% to 66.7% and observed mean latency by 35.2% without unsafe fast passes.
- Implemented reproducible training/evaluation, stage-level profiling, batch-size benchmarks and a nine-stage/84-code failure taxonomy with hard-case regression artifacts.
- Served the single-load pipeline through FastAPI with warmup, bounded concurrency, timeout separation, batch partial-failure semantics, health checks and metrics; maintained 144 passing automated tests at Phase 12 validation.

## Version B: detailed (6–8 bullets)

**VisionGuard — Multimodal Publishing Content Moderation System**

- Architected an end-to-end AI/CV review system for publishing images, separating detection, OCR, lexical baseline, VLM reasoning, routing and final risk fusion into independently replaceable modules.
- Wrapped Ultralytics YOLO training/validation/inference with configurable class metadata, dataset validation, checkpoints, precision/recall/mAP reporting and visual error exports.
- Implemented PaddleOCR full-image and ROI inference with quadrilateral preservation, safe crop validation, ROI-to-global coordinate remapping, confidence filtering, visualization and CER evaluation.
- Trained a TF-IDF+GBDT text baseline as a low-cost comparison and routing signal; recorded validation F1 0.857 on an eight-item synthetic split, explicitly treated as engineering evidence rather than production quality.
- Built a provider-neutral VLM adapter that bounds multimodal context and validates untrusted model text into strict Pydantic JSON with retry, normalization and explicit failure states.
- Separated dynamic routing from risk fusion, enabling conservative VLM skipping, traceable evidence, threshold sweeps, strategy comparison, ablation and offline replay without rerunning expensive models.
- Developed latency/throughput/GPU-memory profiling and systematic error attribution across nine stages and 84 failure codes; exported verified hard cases and regression candidates for iterative improvement.
- Exposed single and batch inference through a production-style, single-load FastAPI service with lifespan warmup, bounded GPU concurrency, layered timeouts, Prometheus metrics and partial batch results.

## Interview accuracy note

Do not describe the synthetic smoke metrics as production accuracy. Say: “I validated the engineering and evaluation workflow on small synthetic fixtures; the next requirement for a quality claim is representative, rights-cleared data and held-out calibration.”

