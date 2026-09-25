# Third-Party Notices

VisionGuard 自有源代码使用 MIT License。下列第三方代码、二进制和模型继续适用其原始许可证；本仓库的 MIT License 不会重新许可它们。

| Component | Runtime scope | License / upstream |
|---|---|---|
| Tauri | Desktop | Apache-2.0 OR MIT — https://github.com/tauri-apps/tauri |
| React | Desktop | MIT — https://github.com/facebook/react |
| PyInstaller | Core / VLM packaging | GPL-2.0-or-later with bootloader exception — https://pyinstaller.org/en/stable/license.html |
| FastAPI | Core / VLM service | MIT — https://github.com/fastapi/fastapi |
| Uvicorn | Core / VLM service | BSD-3-Clause — https://github.com/encode/uvicorn |
| ONNX Runtime | Core detector inference | MIT — https://github.com/microsoft/onnxruntime |
| PaddlePaddle / PaddleOCR | Core OCR | Apache-2.0 — https://github.com/PaddlePaddle/PaddleOCR |
| OpenCV | Core image processing | Apache-2.0 plus bundled notices — https://github.com/opencv/opencv |
| scikit-learn | Core text baseline | BSD-3-Clause — https://github.com/scikit-learn/scikit-learn |
| NumPy | Core / VLM numeric runtime | BSD-3-Clause — https://github.com/numpy/numpy |
| Pillow | Core / VLM image codecs | HPND — https://github.com/python-pillow/Pillow |
| Pydantic | Core / VLM schemas | MIT — https://github.com/pydantic/pydantic |
| PyTorch | Optional VLM Runtime | BSD-style plus bundled third-party notices — https://github.com/pytorch/pytorch/blob/main/LICENSE |
| Transformers | Optional VLM Runtime | Apache-2.0 — https://github.com/huggingface/transformers |
| Qwen3-VL-2B-Instruct | Optional VLM Models | Apache-2.0 — https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct |
| Ultralytics YOLO / derived detector | Training / detector provenance | AGPL-3.0 or commercial license — https://www.ultralytics.com/license |

## Native binary boundary

VLM Runtime may contain CUDA、cuDNN、PyTorch 和 Paddle 相关原生文件。NVIDIA 只允许按照 CUDA Toolkit EULA 及其 Attachment A 再分发列明的文件；最终冻结目录必须逐项核对，而不能仅凭 `torch` 包名判断许可。

## Current distribution gate

公开二进制再分发尚未放行：

1. detector 权重来源和 Ultralytics 派生关系仍是 blocker；
2. 最终 VLM Runtime 原生文件清单尚未逐项完成 NVIDIA 再分发复核；
3. Qwen / Paddle 模型包仍需实际随附 LICENSE、NOTICE、模型卡、来源 revision 和哈希；
4. 最终 SBOM 必须从冻结发行 profile 和打包目录重新生成。

本文件是工程审计记录，不构成法律意见。
