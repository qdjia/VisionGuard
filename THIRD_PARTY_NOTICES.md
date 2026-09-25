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
| PaddlePaddle / PaddleOCR models | Core OCR | Apache-2.0 metadata；exact revisions/hashes in `release-evidence/model-provenance.json` |
| OpenCV | Core image processing | Apache-2.0 plus bundled notices — https://github.com/opencv/opencv |
| scikit-learn | Core text baseline | BSD-3-Clause — https://github.com/scikit-learn/scikit-learn |
| NumPy | Core / VLM numeric runtime | BSD-3-Clause — https://github.com/numpy/numpy |
| Pillow | Core / VLM image codecs | HPND — https://github.com/python-pillow/Pillow |
| Pydantic | Core / VLM schemas | MIT — https://github.com/pydantic/pydantic |
| PyTorch | Optional VLM Runtime | BSD-style plus bundled third-party notices — https://github.com/pytorch/pytorch/blob/main/LICENSE |
| Transformers | Optional VLM Runtime | Apache-2.0 — https://github.com/huggingface/transformers |
| Qwen3-VL-2B-Instruct | Optional VLM Models | Apache-2.0；revision `89644892e4d85e24eaac8bacfd4f463576704203` |
| NVIDIA CUDA / cuDNN runtime DLLs | Optional VLM Runtime | NVIDIA CUDA SDK EULA / cuDNN Supplement；file-level mapping in `release-evidence/native-nvidia-inventory.json` |
| Ultralytics YOLO / derived detector | Training / detector provenance | AGPL-3.0 or commercial license — https://www.ultralytics.com/license |
| Microsoft Edge WebView2 Runtime | Desktop offline installer | Microsoft distribution terms — https://learn.microsoft.com/microsoft-edge/webview2/concepts/distribution |

## Native binary boundary

VLM Runtime may contain CUDA、cuDNN、PyTorch 和 Paddle 相关原生文件。NVIDIA 只允许按照 CUDA Toolkit EULA 及其 Attachment A 再分发列明的文件；最终冻结目录必须逐项核对，而不能仅凭 `torch` 包名判断许可。

## Current distribution gate

公开二进制再分发尚未放行：

1. Detector base 已固定为 Ultralytics assets `v8.4.0`、SHA-256 `9b09cc…4fef`；官方将 trained/fine-tuned models 置于 AGPL-3.0 或 Enterprise 路径，当前 MIT RC 未满足任一路径，因此为 `NOT_ALLOWED`；
2. 20 个 NVIDIA DLL 文件实例（19 个唯一 SHA-256）已逐项映射；按唯一二进制计，18 个为 `ALLOWED_WITH_CONDITIONS`。`nvJitLink_120_0.dll` 是 `cusparse64_12.dll` 的静态依赖，但 Attachment A 与官方 Windows 指南的基础文件名不一致，故仍为 `UNCLEAR`；
3. Qwen / Paddle 精确 revision、哈希、模型卡元数据和 Apache-2.0 文本已进入 release evidence；
4. 最终候选仍需重建，使更新后的 provenance、SBOM 和 notices 与实际资产完全一致。

本文件是工程审计记录，不构成法律意见。
