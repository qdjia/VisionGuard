# VisionGuard v1.0 RC Distribution License Report

审计日期：2026-09-25。状态基于当前冻结候选资产；不是法律意见。

| Component | Version / artifact | Included in | License | Redistribution status | Required notice / evidence | Gate |
|---|---|---|---|---|---|---|
| VisionGuard source/Desktop | 1.0.0 | Installer | MIT | Allowed with MIT notice | 根 `LICENSE` | PASS |
| Ultralytics YOLO26 detector | Ultralytics 8.4.151；final ONNX SHA-256 `82dccb…24d6` | Core Models | AGPL-3.0 or Enterprise | Unclear for current MIT distribution | Base revision/hash、许可路径、corresponding source 或商业许可 | **BLOCKED** |
| Qwen3-VL-2B-Instruct | revision `89644892…4203`；model SHA-256 `7de183…78a0` | VLM Models | Apache-2.0 on immutable official model card | Allowed with conditions | `release-evidence/model-provenance.json`、model-card metadata、canonical Apache-2.0 text | PASS (evidence) |
| PaddleOCR source | Frozen Python package | Core Runtime | Apache-2.0 | Allowed with conditions | Apache-2.0 notice | PARTIAL |
| PaddleOCR model assets | revisions `8e0f56…` / `e5a92b…` / `cd237a…` | Core Models | Bundled immutable README metadata declares Apache-2.0 | Allowed with conditions | Exact hashes/revisions and canonical Apache-2.0 text retained in `release-evidence/` | PASS (evidence) |
| ONNX Runtime | 1.26.0 (`onnxruntime-gpu` build source；CPU-only Core package profile) | Core Runtime | MIT | Allowed with notice | Runtime mapping in `release-evidence/runtime-provenance.json` | PASS (evidence) |
| PyTorch | 2.11.0+cu128；torchvision 0.26.0+cu128 | VLM Runtime | BSD-3-Clause plus bundled third-party components | Allowed with conditions | Bundled LICENSE/NOTICE + native dependency audit | PASS (framework evidence) |
| CUDA/cuDNN libraries | CUDA 12.x / cuDNN 9 family DLLs | VLM Runtime | NVIDIA SDK EULA / cuDNN Supplement | 20 file occurrences / 19 unique hashes；18 unique allowed with conditions；1 unique unclear | `release-evidence/native-nvidia-inventory.json`；resolve `nvJitLink_120_0.dll` name mapping | **BLOCKED** |
| WebView2 Evergreen Standalone Installer | File version 1.3.271.7 in current Tauri build cache | Core NSIS | Microsoft distribution terms | Supported distribution method | Record installer SHA-256 and Microsoft distribution evidence | PARTIAL |
| Node/Rust/Python dependencies | Exact versions in CycloneDX SBOM | Desktop/Core/VLM | Mixed | Per-component review required | Final SBOM and bundled notices | PARTIAL |

## Frozen model evidence status

- Qwen model bytes match immutable revision `89644892e4d85e24eaac8bacfd4f463576704203`; immutable model-card metadata and canonical Apache-2.0 text are retained.
- OCR weight bytes match three immutable upstream revisions. Those repositories' README metadata declares Apache-2.0 but the revisions return 404 for standalone `LICENSE`; the canonical license text is therefore retained as explicit release evidence.
- The detector training record retains the trained checkpoint and ONNX hashes, but not the original `yolo26n.pt` revision/hash or an Enterprise License.

Qwen/Paddle evidence defects are closed at the engineering-evidence level. Detector and one native NVIDIA mapping still keep the public RC blocked.

## Official evidence accessed 2026-09-25

- Qwen model card: <https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct>
- PaddleOCR license: <https://github.com/PaddlePaddle/PaddleOCR/blob/main/LICENSE>
- Paddle license: <https://github.com/PaddlePaddle/Paddle/blob/develop/LICENSE>
- Ultralytics licensing: <https://www.ultralytics.com/license>
- ONNX Runtime license: <https://github.com/microsoft/onnxruntime/blob/main/LICENSE>
- PyTorch license: <https://github.com/pytorch/pytorch/blob/main/LICENSE>
- NVIDIA CUDA EULA: <https://docs.nvidia.com/cuda/eula/index.html>
- WebView2 distribution: <https://learn.microsoft.com/microsoft-edge/webview2/concepts/distribution>
