# Phase 17 Release Slimming Report

Audit date: 2026-09-23. Sizes below are unpacked bytes. Phase 16 artifacts were retained; no release, tag, push, or public upload was performed.

## Decision and size KPI

Adopt the **CPU Core Runtime architecture** as the release-engineering baseline, but do not publish v1.0 yet. Detector ONNX deployment and the core/VLM model split passed. The independent VLM runtime/transport, quantized VLM, signed installer, clean-machine acceptance, and redistribution clearance remain release gates.

| Artifact | Before | After | Change |
|---|---:|---:|---:|
| Python runtime | 5,311,923,777 B (4.947 GiB) | 748,413,790 B (0.697 GiB) | -85.91% |
| Core model bundle | 4,418,141,986 B combined | 156,803,606 B (0.146 GiB) | -96.45% |
| VLM model bundle | embedded | 4,266,642,763 B (3.974 GiB) | split only; not quantized |
| Core-only installed | unavailable | 905,217,396 B (0.843 GiB) | new profile |
| Phase 16 full installed | 9,730,065,763 B (9.062 GiB) | unchanged reference | retained |

An independent VLM runtime was not built, so an optimized full-install number is not claimed. Adding Core assets to the unchanged Phase 16 runtime would duplicate dependencies and is not a valid optimization result.

## Runtime and dependency audit

The 4.947 GiB reference runtime was dominated by CUDA/cuDNN (2,985.773 MiB, 58.94%) and PyTorch (1,116.117 MiB, 22.03%). Paddle was 307.709 MiB, Polars 167.737 MiB, OpenCV 110.847 MiB, SciPy 72.060 MiB, Transformers/Hugging Face 60.418 MiB, and scikit-learn 12.350 MiB. Full tables are in `runtime_size_audit.md`.

The final Core Runtime contains no Ultralytics, Transformers package, PyTorch package, CUDA provider, TensorRT provider, Polars, or Matplotlib. Its largest retained components are Paddle (307.709 MiB), OpenCV (110.847 MiB), SciPy (67.471 MiB), NumPy (26.869 MiB), and scikit-learn (12.350 MiB). PaddleX itself is 0.656 MiB, but its import graph requires pandas. The audit's Hugging Face bucket includes transitive `tokenizers`/`hf_xet` binaries; the `transformers` package is absent.

## Detector ONNX gate

- Export: opset 18, simplified, dynamic batch axes, embedded NMS, `[batch,max_det,6]` output.
- Model: 10,685,076 B; SHA-256 `82dccb397dd39113542731e574001241bcadd2ec4a22e8c31b4592815a5b24d6`.
- Regression: 13 images at confidence 0.01; 307/307 detections matched, zero missing/extra, class match 1.0, minimum IoU 0.889982, maximum confidence delta 0.000019922.
- Acceptance passed at empirical gates: class match 1.0, IoU >= 0.88, confidence delta <= 0.001. The lower IoU cases were tiny/clipped boxes.
- Mean CPU latency was about 180.06 ms for PyTorch/Ultralytics and 23.43 ms for ONNX; load time was about 2,038 ms versus 441 ms.
- Deployment removes Ultralytics and detector PyTorch from Core. Training remains unchanged. ONNX export does not resolve detector-weight licensing.

## OCR slimming gate

PaddleOCR was retained to avoid changing backend and model simultaneously. The experiment removed Torch/CUDA, Polars, and unrelated training/visualization packages, but found two genuine closure requirements: CPU OCR must not unconditionally import Torch, while PaddleX requires pandas during import. After restoring only the required dependency, packaged OCR initialized and performed real inference.

The OCR schema, models, and Paddle inference path are unchanged; this is dependency-closure slimming, not OCR model conversion. Paddle plus PaddleX occupies 323,343,519 B and the Paddle portion did not shrink. An ONNX OCR provider remains a later, separately gated experiment.

## Core/VLM contract and smoke result

- Manifest schema v2 supports `core`, `vlm`, and `full` bundle types; schema v1 remains readable.
- Core validates detector/OCR/baseline as ready and VLM as missing without failing readiness.
- `/v1/meta` exposes `core_ready`, `vlm_available`, `fast_review`, and `deep_review`.
- Full/deep review still semantically requires VLM. Without the pack it returns `partial`, risk at least `medium`, and `requires_manual_review=true`.
- A packaged real-image request routed to VLM returned `partial/medium/manual`; no unsafe low-risk fallback occurred.
- Safe-consensus Fast Path logic is unchanged and covered by routing/fusion tests.

Packaged CPU Core cold readiness was 4,890.98 ms: detector 594.55 ms, OCR 4,155.65 ms, baseline 32.31 ms, policy 2.01 ms, fusion 4.30 ms. The first Core request took about 1.38 s; eight later smoke requests took about 1.03-1.09 s. VLM load is eliminated from Core startup.

## VLM quantization gate

The BF16 reference has 4,255,140,312 B of main weights and a 4,266,642,763 B bundle. The existing three-case evaluation recorded 100% structured-output success, 100% risk accuracy, category precision/recall/F1 of 1.0, and 6,608.31 ms mean latency. This is a smoke set, not a quality claim.

No quantized model was selected: bitsandbytes was unavailable and not assumed stable in a frozen Windows runtime; AutoAWQ's documented Transformers downgrade to 4.47.1 conflicts with the tested Qwen3-VL path on 4.57.6; GPTQ/AWQ/GGUF candidates were not locally available to pass the required structured-output regression. Estimated INT4 size is not reported as a built result. Quantized size, VRAM, load, latency, structured-output, and risk/category comparisons are therefore **not measured**. BF16 remains the tested optional model fallback, not a slim VLM pack.

## Distribution, licenses, and open gates

Core Runtime (0.697 GiB) and Core Models (0.146 GiB) are plausible separate assets. The 3.974 GiB VLM model exceeds GitHub Free/Pro's 2 GiB Git LFS per-file limit and requires splitting or external hosting. Actual compressed assets were not produced.

ONNX Runtime is now a Core dependency. Ultralytics code is absent from Core, but the ONNX weight retains unresolved provenance/derived-weight licensing. Exact frozen SBOM/notices, NVIDIA terms for a future GPU edition, signing, and clean-machine tests remain mandatory.

Validation completed: detector regression; offline Core manifest validation; packaged Core startup and API readiness without Torch/Ultralytics/Transformers/VLM; real-image fail-safe inference; 160 full-suite Python tests plus the new manifest regression; Ruff; compileall; 39 frontend tests; ESLint; TypeScript; Vite build; 19 Rust tests; Cargo fmt/check. The desktop now shows Advanced AI availability and returns an unavailable Deep Review selection to Fast Review. A complete VLM import/install UI and independent VLM service were intentionally not claimed.

## Reproduction

```powershell
python scripts/export_detector_onnx.py --model models/models-v1/detector/model.pt --output artifacts/phase17/detector/model.onnx
python scripts/compare_detector_backends.py --pytorch-model models/models-v1/detector/model.pt --onnx-model artifacts/phase17/detector/model.onnx --images <images...> --output artifacts/phase17/detector/regression.json --conf-threshold 0.01 --minimum-iou 0.88 --maximum-confidence-delta 0.001
python scripts/build_model_bundle.py --profile core --bundle-version core-models-v1 --output models/core-models-v1 --detector artifacts/phase17/detector/model.onnx
python scripts/build_runtime.py --profile core
```

## Current limitations

CPU Core is the only validated slim profile. OCR is now the size/latency bottleneck. GPU ONNX worked only by borrowing CUDA DLLs from PyTorch in development and is not a standalone release proof. The VLM model is separated, but its runtime/transport and component-aware desktop installation are unfinished; Phase 16 installer assumptions therefore remain until that lifecycle is implemented.
