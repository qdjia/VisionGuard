# Model and Runtime Redistribution Audit

审计日期：2026-09-25。本记录不是法律意见。

| Component | Official evidence | Engineering verdict |
|---|---|---|
| Qwen3-VL-2B-Instruct | [官方模型卡](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct)标为 Apache-2.0 | 条件通过；模型包必须携带许可证、模型卡、来源 revision 与完整哈希 |
| PaddleOCR code / Paddle runtime | [Paddle LICENSE](https://github.com/PaddlePaddle/Paddle/blob/develop/LICENSE)为 Apache-2.0 | 条件通过；最终 OCR 模型随附文件和 notice 仍需核对 |
| Ultralytics YOLO / trained models | [官方许可说明](https://www.ultralytics.com/license)说明默认 AGPL-3.0，闭源/专有路径需商业许可 | **阻断**；ONNX 导出不会改变来源许可 |
| Current detector weight | Base fixed to assets `v8.4.0` and SHA-256 `9b09cc…4fef`; trained/ONNX hashes retained；current MIT RC has neither an AGPL distribution plan nor Enterprise License | **`NOT_ALLOWED` for current distribution；阻断** |
| PyTorch binaries | PyTorch 主体 BSD-style，但 wheel 包含第三方原生组件 | 条件通过；以最终 Runtime SBOM / 文件清单为准 |
| CUDA / cuDNN native files | [CUDA 13.1 EULA](https://docs.nvidia.com/cuda/archive/13.1.1/pdf/EULA.pdf) Attachment A 列出可再分发文件 | **阻断**；必须把最终打包文件逐项映射到适用条款 |

## Detector resolution options

公开发行前必须明确选择并留下证据：

1. 按 AGPL-3.0 完成整个适用作品的合规公开；或
2. 取得覆盖当前用途和分发方式的 Ultralytics 商业许可；或
3. 不分发 detector 权重，改由用户提供；或
4. 使用许可来源明确且与目标发行方式兼容的 detector base 重新训练。

当前代码不替项目所有者或法律顾问强行选择路径。当前 MIT RC 的结论是 `NOT_ALLOWED`，`public_release_ready` 必须保持 `false`。

## Packaging requirements

- Core Models 和 VLM Models 独立打包，不能因 Qwen 许可清晰而忽略 detector blocker。
- VLM Runtime 和 VLM Models 独立版本、独立 SBOM / notice、独立分卷。
- 每份最终模型包需记录上游名称、精确 revision、文件哈希、训练数据来源和修改说明。
- 分卷只解决托管体积，不改变任何许可义务。
