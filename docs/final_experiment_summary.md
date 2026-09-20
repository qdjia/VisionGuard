# Final Experiment Summary

This compact summary is derived from recorded local artifacts and verified test runs. Generated raw
artifacts remain ignored by Git. See [experiments.md](experiments.md) for interpretation and caveats.

## Summary table

| Experiment | Dataset / count | Hardware | Configuration | Metrics | Evidence and limitation |
|---|---|---|---|---|---|
| YOLO training | Synthetic rectangles; 4 train, 2 val, 2 test | RTX 4060 Laptop GPU | 1 epoch, seed 42, YOLO26n smoke | Val P 0.0033, R 1.0, mAP50 0.0406, mAP50:95 0.0366 | Level C; training-path verification only |
| OCR CER | Clean synthetic Chinese text; 1 | CPU OCR | PaddleOCR, confidence 0.5 | CER 0.0 | Level C; no scan/layout diversity |
| Text baseline | Self-authored synthetic text; 20/8/8 | CPU | char TF-IDF 2–4 + GBDT, threshold 0.5 | Val P 1.0, R 0.75, F1 0.8571 | Level B; only 36 total samples |
| VLM structured output | Synthetic images; 3 | RTX 4060 Laptop GPU | Qwen3-VL-2B, prompt/policy v1 | 3/3 structured; mean 6608.31 ms | Level B/C; not a quality benchmark |
| Full pipeline | Synthetic images; 3 | RTX 4060 + CPU OCR | Pipeline v1 | Mean 15479.49 ms; P95 21174.29 ms | Level B; engineering-chain validation |
| Full vs cascaded routing | Same synthetic images; 3 | RTX 4060 + CPU OCR | routing_v1 | VLM 100%→66.7%; mean 20132.14→13054.70 ms; unsafe fast pass 0 | Level B/C; observed 35.15% reduction on 3 samples |
| Risk fusion | Same synthetic images; 3 | Same stack | weighted fusion_v1 | Risk accuracy 1.0; micro F1 1.0; manual 33.3%; unsafe fused low 0 | Level B; values not representative |
| Batch-2 comparison | Engineering workload; 2 samples, 1 measured run | RTX 4060 Laptop GPU | mixed batch, synchronized CUDA | Full 16218.14 ms/0.123 img/s; cascaded 16383.42 ms/0.122 img/s | Level C; no throughput improvement |
| Error analysis | Phase 9 GT records; 3 | Offline + optional live replay | error_analysis_v1 | 84 failure types, 9 stages, 2 hard cases, 1 regression candidate | Level B/C; framework is the result |
| API smoke | Safe/risky synthetic images | RTX 4060 local stack | FastAPI, one worker, semaphore 1 | health/meta/review passed; invalid image 400; init count 1 | Level C; production-style, not production-ready |

## Performance conclusion

The fairest recorded Full/Cascaded performance comparison is the Phase 10 batch-2 smoke because it
shares models, inputs, warmup, seed, artifact settings, and hardware. Both modes called the VLM for
all samples. Full achieved 0.123 images/s and Cascaded 0.122 images/s; the difference is ordinary
one-run variation, not an optimization result.

Full module-time shares in that run:

| Module | Share |
|---|---:|
| VLM | 91.21% |
| OCR | 8.69% |
| YOLO | 0.08% |
| Baseline | 0.01% |
| Fusion | <0.01% |

The defensible engineering conclusion is that VLM generation is the dominant bottleneck and that
batching YOLO/Baseline alone does not improve throughput when OCR and VLM remain sequential.

## Evaluation gaps

- No large independently annotated publishing dataset.
- No reliable per-category detection or moderation recall estimate.
- No repeated Phase 10 performance runs for stable percentile statistics.
- No confidence or risk-score calibration set.
- Very few true conflicts, failures, and adversarial prompt cases.
- No production traffic, load test, or service-level objective.

## Optional Phase 14 gate

The engineering platform is ready for an optional stronger-evaluation phase, but current metrics are not. A Phase 14 should begin only after defining a rights-cleared representative dataset, annotation/adjudication protocol, leakage-safe split, primary safety metrics and a repeated benchmark protocol. It should strengthen evidence rather than add unrelated product features.
