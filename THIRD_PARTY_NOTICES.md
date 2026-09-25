# Third-Party Notices

VisionGuard 自有源代码采用 `AGPL-3.0-only`。该许可证只覆盖 VisionGuard 有权许可的代码，不会改变第三方代码、二进制、模型和资产的许可证。

| Component | Scope | License / upstream |
|---|---|---|
| Tauri | Desktop | Apache-2.0 OR MIT — https://github.com/tauri-apps/tauri |
| React | Desktop | MIT — https://github.com/facebook/react |
| PyInstaller | Packaging | GPL-2.0-or-later with bootloader exception |
| FastAPI | Runtime | MIT |
| Uvicorn | Runtime | BSD-3-Clause |
| ONNX Runtime | Core detector | MIT |
| PaddlePaddle / PaddleOCR models | Core OCR | Apache-2.0 metadata；精确 revision/hash 见 release evidence |
| OpenCV | Image processing | Apache-2.0 plus bundled notices |
| scikit-learn | Text baseline | BSD-3-Clause |
| NumPy | Numeric runtime | BSD-3-Clause |
| Pillow | Image codecs | HPND |
| Pydantic | Schemas | MIT |
| PyTorch | Optional VLM Runtime | BSD-style plus bundled notices |
| Transformers | Optional VLM Runtime | Apache-2.0 |
| Qwen3-VL-2B-Instruct | Optional VLM Models | Apache-2.0；revision `89644892e4d85e24eaac8bacfd4f463576704203` |
| NVIDIA CUDA / cuDNN DLLs | Optional VLM Runtime | NVIDIA CUDA SDK EULA / cuDNN Supplement |
| Ultralytics YOLO / derived detector | Detector | AGPL-3.0 or applicable Enterprise terms |
| Microsoft Edge WebView2 Runtime | Desktop installer | Microsoft distribution terms |

## 当前发行边界

- Ultralytics Detector 采用 AGPL 开源发行路径，状态为 `ALLOWED_WITH_CONDITIONS`。条件包括：同时提供适用源码、构建脚本、AGPL 文本、模型来源与修改记录，并把候选产物映射到明确的源码 commit 和预期 tag。
- NVIDIA 原生文件按最终冻结清单逐项审计；`nvJitLink_120_0.dll` 当前仍为 `UNCLEAR`，因此公开二进制发行尚未放行。
- Qwen 与 Paddle 的精确 revision、哈希、模型卡元数据和 Apache-2.0 文本保存在 `release-evidence/`。

本文件是工程审计记录，不构成法律意见。
