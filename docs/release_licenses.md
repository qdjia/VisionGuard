# VisionGuard v1.0 RC Distribution License Report

审计日期：2026-09-25。状态基于当前冻结候选资产；不是法律意见。

| Component | Version / artifact | Included in | License | Redistribution status | Required notice / evidence | Gate |
|---|---|---|---|---|---|---|
| VisionGuard source/Desktop | 1.0.0 | Installer | MIT | Allowed with MIT notice | 根 `LICENSE` | PASS |
| Ultralytics YOLO26 detector | Ultralytics 8.4.151；final ONNX SHA-256 `82dccb…24d6` | Core Models | AGPL-3.0 or Enterprise | Unclear for current MIT distribution | Base revision/hash、许可路径、corresponding source 或商业许可 | **BLOCKED** |
| Qwen3-VL-2B-Instruct | BF16；model SHA-256 `7de183…78a0` | VLM Models | Apache-2.0 on official model card | Allowed with conditions, but frozen bundle provenance incomplete | Exact upstream revision、Apache-2.0 text、model card/notice | **BLOCKED** |
| PaddleOCR source | Frozen Python package | Core Runtime | Apache-2.0 | Allowed with conditions | Apache-2.0 notice | PARTIAL |
| PaddleOCR model assets | Detection/recognition/orientation bundles | Core Models | Bundled README declares Apache-2.0 | Unclear until asset provenance is retained | Exact model source/revision and LICENSE files; current README links point to absent local LICENSE files | **BLOCKED** |
| ONNX Runtime | Frozen Core Runtime | Core Runtime | MIT | Allowed with notice | Preserve ONNX Runtime license and third-party notices | PARTIAL |
| PyTorch | 2.11.0+cu128 | VLM Runtime | BSD-style plus bundled third-party components | Allowed with conditions | PyTorch license plus native dependency notices | PARTIAL |
| CUDA/cuDNN libraries | CUDA 12.x / cuDNN 9 family DLLs | VLM Runtime | NVIDIA SDK EULA | Unclear pending file-level mapping | Map every NVIDIA DLL to current EULA Attachment A and retain applicable notices | **BLOCKED** |
| WebView2 Evergreen Standalone Installer | File version 1.3.271.7 in current Tauri build cache | Core NSIS | Microsoft distribution terms | Supported distribution method | Record installer SHA-256 and Microsoft distribution evidence | PARTIAL |
| Node/Rust/Python dependencies | Exact versions in CycloneDX SBOM | Desktop/Core/VLM | Mixed | Per-component review required | Final SBOM and bundled notices | PARTIAL |

## Frozen model evidence gaps

- `models/vlm-models-v1/vlm` does not contain an upstream revision, `LICENSE`, model card or notice.
- OCR subdirectories contain README metadata declaring Apache-2.0, but the referenced local LICENSE files are absent.
- The detector training record retains the trained checkpoint and ONNX hashes, but not the original `yolo26n.pt` revision/hash or an Enterprise License.

These are distribution evidence defects, not model-inference defects. They keep the public RC blocked even though local inference works.

## Official evidence accessed 2026-09-25

- Qwen model card: <https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct>
- PaddleOCR license: <https://github.com/PaddlePaddle/PaddleOCR/blob/main/LICENSE>
- Paddle license: <https://github.com/PaddlePaddle/Paddle/blob/develop/LICENSE>
- Ultralytics licensing: <https://www.ultralytics.com/license>
- ONNX Runtime license: <https://github.com/microsoft/onnxruntime/blob/main/LICENSE>
- PyTorch license: <https://github.com/pytorch/pytorch/blob/main/LICENSE>
- NVIDIA CUDA EULA: <https://docs.nvidia.com/cuda/eula/index.html>
- WebView2 distribution: <https://learn.microsoft.com/microsoft-edge/webview2/concepts/distribution>
