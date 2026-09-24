# Third-Party Notices

VisionGuard 自有源代码使用 MIT License。下表记录组件化 Windows 候选包的主要第三方组件；各组件继续适用其原始许可。本文件不重新许可任何第三方代码或模型。PyTorch、Transformers 与 Qwen 仅属于可选 Advanced AI 组件，Core 不包含它们。

| Component | Purpose | License / upstream |
|---|---|---|
| Tauri | Desktop shell and NSIS bundling | Apache-2.0 OR MIT — https://github.com/tauri-apps/tauri |
| React | Desktop UI | MIT — https://github.com/facebook/react |
| PyInstaller | Python one-folder packaging | GPL-2.0-or-later with bootloader exception — https://pyinstaller.org/en/stable/license.html |
| FastAPI | Local inference API | MIT — https://github.com/fastapi/fastapi |
| Uvicorn | Local ASGI server | BSD-3-Clause — https://github.com/encode/uvicorn |
| ONNX Runtime | Core detector inference runtime | MIT — https://github.com/microsoft/onnxruntime |
| PyTorch | Tensor and CUDA inference runtime | BSD-style plus bundled third-party notices — https://github.com/pytorch/pytorch/blob/main/LICENSE |
| Transformers | VLM model runtime | Apache-2.0 — https://github.com/huggingface/transformers |
| Qwen3-VL-2B-Instruct | Vision-language model weights | Apache-2.0 — https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct |
| PaddlePaddle / PaddleOCR | OCR runtime and models | Apache-2.0 — https://github.com/PaddlePaddle/PaddleOCR |
| Ultralytics | YOLO inference/training | AGPL-3.0 or commercial Enterprise License — https://www.ultralytics.com/license |
| OpenCV | Image processing | Apache-2.0 plus bundled third-party notices — https://github.com/opencv/opencv |
| scikit-learn | Text baseline | BSD-3-Clause — https://github.com/scikit-learn/scikit-learn |
| NumPy | Numeric runtime | BSD-3-Clause — https://github.com/numpy/numpy |
| Pillow | Image codecs | HPND — https://github.com/python-pillow/Pillow |
| Pydantic | Runtime schemas | MIT — https://github.com/pydantic/pydantic |

The public redistribution audit is **not cleared**. In particular, the current Ultralytics-based detector and the NVIDIA/CUDA binary inventory remain release blockers. See `docs/model_distribution_licenses.md`.

Before any public binary release, generate separate frozen dependency/SBOM inventories for Core Runtime and VLM Runtime, and include all license and NOTICE files required by each component. Split model parts remain one logical Qwen asset and must ship the same license, model-card and revision metadata. This candidate notice is an engineering audit record, not legal advice.
