# Configuration Reference

All tracked configurations use YAML and are validated before model or pipeline construction. Paths
are generally resolved relative to the YAML file that contains them. Unknown keys are rejected by
the corresponding strict Pydantic model unless a third-party format requires otherwise.

## Configuration map

| File | Responsibility | Important fields |
|---|---|---|
| `configs/default.yaml` | Combined Phase 1 application defaults | project paths, detector, OCR, mock VLM, legacy cascade settings |
| `configs/detector.yaml` | Single-image detector | classes file, checkpoint, device, confidence/IoU, image size, warmup |
| `configs/train_detector.yaml` | Full detector training | dataset, epochs, batch, optimizer, LR, augmentation, seed, artifacts |
| `configs/train_detector_smoke.yaml` | Tiny synthetic training run | one-epoch smoke configuration |
| `configs/datasets/visionguard.yaml` | User dataset layout | train/val/test directories and class map |
| `configs/datasets/visionguard_smoke.yaml` | Tracked synthetic dataset layout | small generated train/val/test data |
| `configs/ocr.yaml` | OCR runtime | provider, language, device, confidence, max side, orientation, preprocessing |
| `configs/baseline_text.yaml` | Text baseline train/eval | splits, TF-IDF, GBDT, threshold, seed, artifacts |
| `configs/vlm.yaml` | VLM provider | model, device/dtype, token/retry/deadline limits, prompt version, caches |
| `configs/moderation_policy.yaml` | VLM output policy | allowed categories, risk levels, policy version |
| `configs/pipeline.yaml` | Full pipeline | module toggles, artifact behavior, failure mode, pipeline version |
| `configs/pipeline_cascaded.yaml` | Cascaded pipeline | same pipeline contract with a separate artifact root/versioned mode |
| `configs/routing.yaml` | Dynamic routing | safety classes, thresholds, OCR reliability, failure/conflict policies |
| `configs/fusion.yaml` | Final decision fusion | strategy, weights, severity maps, risk boundaries, review policies |
| `configs/benchmark.yaml` | Repeated benchmark | runs, batches, percentiles, CUDA sync, memory, seed, output root |
| `configs/benchmark_smoke.yaml` | Quick benchmark | small batch/run counts only |
| `configs/error_analysis.yaml` | Failure analysis | taxonomy thresholds, boundary margins, severity, hard-case policy |
| `configs/api.yaml` | Public API defaults | endpoint limits, timeout, concurrency, warmup, service config references |

## Detector

`conf_threshold` filters candidate detections; it is not a training accuracy target. `iou_threshold`
controls overlap suppression during inference. Lower confidence thresholds can increase recall and
false positives. Evaluation should report Precision, Recall, mAP@0.5, and mAP@0.5:0.95 together.

The public config expects `checkpoints/yolo26.pt`, which is ignored. A user must supply a compatible
checkpoint or create an ignored local override.

## OCR

OCR defaults to the original image with preprocessing disabled. Strong denoise, sharpening, or
contrast changes are experimental because they can reduce PaddleOCR quality. ROI output polygons
and axis-aligned boxes are returned in full-image coordinates after clamping and offset mapping.

`confidence_threshold` changes which blocks appear in `full_text`; raw and filtered counts remain
available for analysis.

## Text baseline

The baseline uses character TF-IDF and a Gradient Boosting classifier. Train, validation, and test
files are separate; test data is not used for model or threshold selection. A threshold sweep writes
analysis but does not silently replace the configured formal threshold.

Saved joblib files must be treated as trusted local artifacts and loaded with a compatible
scikit-learn version.

## VLM and moderation policy

The VLM config selects a provider and controls image size, context limits, generation length,
deadline, retries, prompt version, and artifact directory. `moderation_policy.yaml` independently
defines allowed output categories and policy version.

Changing prompt semantics should create a new prompt version rather than modifying a historical
snapshot. Temperature 0 improves repeatability but is not a determinism guarantee.

## Pipeline

Pipeline module switches support testing and ablation; they are not routing decisions. The full
pipeline always requests the VLM when enabled. The cascaded pipeline uses `RoutingPolicy` after
Stage 1 signals. `fail_fast=false` isolates module failures and can return a conservative partial
result; image loading remains fatal.

`save_input_copy=false` is the privacy-preserving default. Structured intermediate files and
visualizations can still be written under the run ID.

## Routing

Routing thresholds represent conservative engineering rules. They were not learned from a large
dataset. Key groups cover:

- high-risk detector classes and confidence thresholds;
- baseline safe/risky boundaries;
- OCR text length and mean confidence;
- module failure, evidence conflict, and insufficient evidence behavior;
- policy version and explanation codes.

Every threshold change used for comparison should receive a new output directory and, for formal
policy changes, a new policy version.

## Fusion

Fusion maps visual, text, and VLM evidence to comparable engineering scores. It normalizes weights
only over available sources and applies conflicts, failure handling, risk boundaries, and manual
review rules. VLM confidence scaling is disabled by default because it is not calibrated.

The final `risk_score` must never be documented as a calibrated probability.

## Benchmark

`synchronize_cuda=true` brackets timed regions so asynchronous kernels complete before timing is
read. It belongs only in the benchmark layer. Cold start, warmup, steady-state runs, throughput,
percentiles, module shares, and GPU memory are kept separate.

`dataset_kind: engineering` prevents a performance workload from being presented as an accuracy
benchmark. `save_pipeline_artifacts=false` excludes artifact I/O from the default measurement.

## Error analysis

Error-analysis config defines CER/IoU/confidence thresholds, routing/fusion boundary margins,
severity mapping, and hard-case eligibility. Missing GT fields disable unsupported claims; for
example, absent object boxes prevent detector FP/FN attribution.

## API

The public API config references tracked configs. It is portable but still requires the user to
supply detector weights and obtain a VLM. `max_concurrent_inference=1` is the safe default for the
single consumer GPU. Upload bytes, decoded dimensions, timeouts, artifact behavior, warmup, and docs
exposure are configurable.

## Local configuration

`configs/local*.yaml` is ignored. Recommended workflow:

```text
configs/detector.yaml       -> configs/local_detector.yaml
configs/vlm.yaml            -> configs/local_vlm.yaml
configs/api.yaml            -> configs/api.local.yaml
```

Edit only the local copies with machine-specific model locations. Do not put secrets into tracked
YAML. The API local copy can reference `local_detector.yaml` and `local_vlm.yaml` while the public
default remains usable as documentation in a clean clone.

