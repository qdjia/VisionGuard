# Release License Report

| Component | Scope | License | Decision |
|---|---|---|---|
| VisionGuard source/Desktop | Source + installer | AGPL-3.0-only | PASS (source alignment) |
| Ultralytics YOLO detector | Core Models | AGPL-3.0 / applicable Enterprise terms | `ALLOWED_WITH_CONDITIONS` |
| Qwen3-VL-2B-Instruct | Optional VLM Models | Apache-2.0 | PASS (evidence) |
| PaddleOCR models | Core Models | Apache-2.0 metadata | PASS (evidence) |
| ONNX Runtime | Core Runtime | MIT | PASS (notice required) |
| PyTorch / torchvision | Optional VLM Runtime | BSD-style + notices | PASS (evidence) |
| NVIDIA CUDA / cuDNN native files | Optional VLM Runtime | NVIDIA terms | BLOCKED: one mapping remains `UNCLEAR` |
| WebView2 Runtime | Installer | Microsoft distribution terms | Conditional on frozen artifact evidence |

VisionGuard 自有代码与第三方资产是两个许可层。项目采用 AGPL 不会把第三方 MIT、Apache、BSD 或专有再分发条款改成 AGPL，也不会自动解决 NVIDIA 二进制再分发问题。

最终候选必须包含 `LICENSE`、`NOTICE`、本报告、`THIRD_PARTY_NOTICES.md`、模型/Runtime provenance 与 CycloneDX SBOM，并映射到源码 commit 和预期 tag。
