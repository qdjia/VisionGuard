# CLI Reference

Run commands from the repository root after installing the package. Use `python <script> --help`
for the complete argument list. Output paths shown below are examples and should be new or empty.

## Fixture generation

| Command | Purpose |
|---|---|
| `python scripts/create_smoke_dataset.py` | Generate the tiny synthetic YOLO dataset |
| `python scripts/create_ocr_smoke_images.py` | Generate Chinese/English OCR images |
| `python scripts/create_vlm_eval_samples.py` | Generate three synthetic VLM images and manifest |

## Detection

```bash
python scripts/validate_dataset.py --data configs/datasets/visionguard_smoke.yaml
python scripts/train_detector.py --config configs/train_detector_smoke.yaml
python scripts/evaluate_detector.py \
  --checkpoint artifacts/experiments/<experiment>/weights/best.pt \
  --data configs/datasets/visionguard_smoke.yaml --split test
python scripts/infer_detector.py \
  --image data/visionguard_smoke/images/test/test_00.jpg \
  --config configs/local_detector.yaml \
  --output artifacts/inference/test_00.jpg
python scripts/export_error_cases.py \
  --checkpoint artifacts/experiments/<experiment>/weights/best.pt \
  --data configs/datasets/visionguard_smoke.yaml \
  --experiment-name detector_errors
python scripts/smoke_test_detector.py \
  --image data/visionguard_smoke/images/test/test_00.jpg \
  --config configs/local_detector.yaml
```

Key options: training `--epochs`, `--batch-size`, `--device`, `--resume`; evaluation `--split`,
`--image-size`, `--output`.

## OCR

```bash
python scripts/infer_ocr.py \
  --image data/ocr_smoke/chinese.png --output artifacts/ocr/chinese.jpg
python scripts/infer_ocr_roi.py \
  --image data/ocr_smoke/chinese.png --bbox 0 0 1000 180 \
  --output artifacts/ocr/chinese_roi.jpg
python scripts/evaluate_ocr.py \
  --manifest data/ocr_eval/ground_truth.jsonl \
  --output artifacts/ocr/evaluation.json
python scripts/smoke_test_ocr.py \
  --chinese-image data/ocr_smoke/chinese.png \
  --english-image data/ocr_smoke/english.png
```

Key options: `--config`, ROI `--bbox`, evaluation `--error-threshold`.

## Text baseline

```bash
python scripts/train_text_baseline.py --config configs/baseline_text.yaml
python scripts/infer_text_baseline.py --text "这是正常出版教材内容"
python scripts/evaluate_text_baseline.py \
  --data data/text_moderation/sample/val.csv --threshold-sweep
python scripts/export_text_errors.py --data data/text_moderation/sample/test.csv
python scripts/smoke_test_text_baseline.py
```

`split_text_dataset.py` creates deterministic train/validation/test CSV splits for a user-supplied
text dataset. Keep private data outside tracked paths.

## VLM

```bash
python scripts/infer_vlm.py \
  --image data/vlm_eval/risky.png --config configs/local_vlm.yaml
python scripts/infer_vlm.py --image data/vlm_eval/risky.png --mock
python scripts/evaluate_vlm.py \
  --manifest data/vlm_eval/manifest.jsonl --config configs/local_vlm.yaml
python scripts/smoke_test_vlm.py \
  --text-image data/vlm_eval/text.png --config configs/local_vlm.yaml
```

Key options: `--policy`, `--detection-json`, `--ocr-json`, `--baseline-json`, `--output`, `--mock`.

## Full and cascaded pipeline

```bash
python scripts/run_pipeline.py \
  --image data/vlm_eval/risky.png \
  --detector-config configs/local_detector.yaml \
  --vlm-config configs/local_vlm.yaml

python scripts/run_cascaded_pipeline.py \
  --image data/vlm_eval/risky.png \
  --detector-config configs/local_detector.yaml \
  --vlm-config configs/local_vlm.yaml

python scripts/smoke_test_pipeline.py \
  --images data/vlm_eval/safe.png data/vlm_eval/risky.png \
  --detector-config configs/local_detector.yaml \
  --vlm-config configs/local_vlm.yaml

python scripts/evaluate_pipeline.py \
  --manifest data/vlm_eval/manifest.jsonl \
  --detector-config configs/local_detector.yaml \
  --vlm-config configs/local_vlm.yaml \
  --output artifacts/pipeline/evaluation_new
```

All pipeline commands accept explicit OCR, Baseline, moderation-policy, and Fusion configs.

## Routing

```bash
python scripts/evaluate_routing.py \
  --manifest data/vlm_eval/manifest.jsonl \
  --vlm-config configs/local_vlm.yaml \
  --output artifacts/routing/evaluation_new

python scripts/compare_pipeline_modes.py \
  --manifest data/vlm_eval/manifest.jsonl \
  --vlm-config configs/local_vlm.yaml \
  --output artifacts/routing/comparison_new

python scripts/sweep_routing_thresholds.py \
  --manifest data/vlm_eval/manifest.jsonl \
  --vlm-config configs/local_vlm.yaml \
  --safe-thresholds 0.05 0.10 0.20 \
  --output artifacts/routing/sweep_new

python scripts/analyze_routing_errors.py \
  --predictions artifacts/routing/evaluation_new/predictions.jsonl \
  --output artifacts/routing/errors_new
```

Routing evaluation labels whether a sample needs the VLM and reports unsafe-fast-pass metrics.

## Fusion

```bash
python scripts/evaluate_fusion.py \
  --mode cascaded --manifest data/vlm_eval/manifest.jsonl \
  --detector-config configs/local_detector.yaml \
  --vlm-config configs/local_vlm.yaml \
  --output artifacts/fusion/evaluation_new

python scripts/compare_fusion_strategies.py \
  --records artifacts/fusion/evaluation_new/records.jsonl \
  --output artifacts/fusion/strategy_new
python scripts/run_fusion_ablation.py \
  --records artifacts/fusion/evaluation_new/records.jsonl \
  --output artifacts/fusion/ablation_new
python scripts/sweep_fusion.py \
  --records artifacts/fusion/evaluation_new/records.jsonl \
  --output artifacts/fusion/sweep_new
python scripts/replay_fusion.py \
  --artifacts artifacts/routing/cascaded_routing_v1 \
  --output artifacts/fusion/replay_new.jsonl
python scripts/analyze_fusion_errors.py \
  --records artifacts/fusion/evaluation_new/records.jsonl \
  --output artifacts/fusion/errors_new
```

Strategy comparison, ablation, and sweeps use saved records and do not rerun models.

## Benchmarking

```bash
python scripts/benchmark_modules.py \
  --manifest data/benchmark/manifest.jsonl \
  --config configs/benchmark_smoke.yaml --batch-size 1 \
  --detector-config configs/local_detector.yaml \
  --vlm-config configs/local_vlm.yaml \
  --output artifacts/benchmarks/modules_new

python scripts/benchmark_pipeline.py \
  --manifest data/benchmark/manifest.jsonl \
  --config configs/benchmark_smoke.yaml --pipeline-mode cascaded --batch-size 2 \
  --detector-config configs/local_detector.yaml \
  --vlm-config configs/local_vlm.yaml \
  --output artifacts/benchmarks/pipeline_new

python scripts/benchmark_batch_sizes.py \
  --manifest data/benchmark/manifest.jsonl \
  --config configs/benchmark.yaml --pipeline-mode cascaded \
  --detector-config configs/local_detector.yaml \
  --vlm-config configs/local_vlm.yaml \
  --output artifacts/benchmarks/batch_sweep_new

python scripts/compare_pipeline_performance.py \
  --manifest data/benchmark/manifest.jsonl \
  --config configs/benchmark_smoke.yaml --batch-size 2 \
  --detector-config configs/local_detector.yaml \
  --vlm-config configs/local_vlm.yaml \
  --output artifacts/benchmarks/comparison_new

python scripts/generate_performance_report.py \
  --input artifacts/benchmarks/comparison_new \
  --output artifacts/benchmarks/comparison_new/report.md
```

Use `benchmark_smoke.yaml` only for quick integration checks. Use repeated measured runs before
interpreting percentiles.

## Error analysis and regression

```bash
python scripts/analyze_pipeline_errors.py \
  --records artifacts/fusion/evaluation_new/records.jsonl \
  --config configs/error_analysis.yaml \
  --output artifacts/error_analysis/analysis_new
python scripts/summarize_failure_taxonomy.py \
  --errors artifacts/error_analysis/analysis_new/error_cases.jsonl \
  --output artifacts/error_analysis/analysis_new/taxonomy_summary.csv
python scripts/build_hard_case_dataset.py \
  --errors artifacts/error_analysis/analysis_new/error_cases.jsonl \
  --output data/hard_cases/manifest_new.jsonl
python scripts/replay_error_cases.py \
  --records artifacts/fusion/evaluation_new/records.jsonl \
  --output artifacts/error_analysis/replay_new
python scripts/run_hard_case_regression.py \
  --manifest data/hard_cases/manifest.jsonl \
  --detector-config configs/local_detector.yaml \
  --vlm-config configs/local_vlm.yaml \
  --output artifacts/error_analysis/regression_new
python scripts/generate_error_report.py \
  --analysis artifacts/error_analysis/analysis_new \
  --output artifacts/error_analysis/analysis_new/report_copy.md
```

`export_error_cases.py`, `export_text_errors.py`, `analyze_routing_errors.py`, and
`analyze_fusion_errors.py` are module-specific error exporters. The Phase 11 analyzer is the unified
cross-stage attribution path.

## API

```bash
python scripts/run_api.py --config configs/api.local.yaml
python scripts/smoke_test_api.py \
  --safe-image data/vlm_eval/safe.png \
  --risky-image data/vlm_eval/risky.png
```

The service intentionally runs one Uvicorn worker. Do not use reload or multiple workers for the
real single-GPU smoke because each process initializes its own model set.
