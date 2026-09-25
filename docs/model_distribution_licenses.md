# Model Distribution Licenses

| Component | License evidence | Current decision |
|---|---|---|
| Qwen3-VL-2B-Instruct | Apache-2.0 model metadata, immutable revision and hashes | PASS (evidence) |
| PaddleOCR models | Apache-2.0 repository metadata, immutable revisions and hashes | PASS (evidence) |
| Ultralytics YOLO / trained detector | Upstream AGPL-3.0 or applicable Enterprise terms | `ALLOWED_WITH_CONDITIONS` under VisionGuard AGPL path |

Detector 条件见 `docs/detector_provenance.md`。VisionGuard 根许可证不会重新许可第三方模型；每项模型仍须按自身来源链审计。NVIDIA 原生 Runtime 许可是独立 gate，不能由项目改用 AGPL 自动解决。
