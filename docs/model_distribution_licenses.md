# Model Redistribution License Audit

审计日期：2026-09-22。本文是工程发行门禁记录，不构成法律意见。仓库的 MIT License 只覆盖 VisionGuard 自有代码，不会把第三方代码或模型权重变成 MIT。

| 组件 | 来源与许可证据 | 可否随当前公开 Release 再分发 | 必需动作 | Release action |
|---|---|---|---|---|
| Qwen3-VL-2B-Instruct | [官方 Hugging Face 模型卡](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct)，标记 Apache-2.0 | 原则上允许，需保留许可与 notices | 在模型包附 Apache-2.0 与模型来源 | 许可侧通过 |
| PaddleOCR 代码与 PP-OCR 模型 | [PaddleOCR 官方仓库](https://github.com/PaddlePaddle/PaddleOCR)标记 Apache-2.0 | 原则上允许 | 保留 Apache-2.0、版权和 NOTICE；发布前核对实际下载模型的随附文件 | 条件通过 |
| Ultralytics YOLO 代码 | [Ultralytics 官方许可说明](https://www.ultralytics.com/license)说明默认使用 AGPL-3.0，并提供 Enterprise License | 当前 MIT 组合发行不能直接按 MIT 声明 | 选择完整 AGPL 合规发行路径，或取得覆盖本发行方式的 Enterprise License | **阻塞** |
| 基于 Ultralytics 训练的 detector 权重 | [Ultralytics AGPL 说明](https://www.ultralytics.com/legal/agpl-3-0-software-license)将其默认模型和相关产物置于相应许可路径 | 权重来源/衍生关系未获得可用于当前 MIT 二进制包的书面确认 | 获取许可方确认或改用许可清晰且兼容的 detector 实现与权重 | **阻塞** |
| TF-IDF + GBDT 自训练 baseline | VisionGuard 自有训练产物；依赖 scikit-learn BSD-3-Clause | 可以，但需携带 scikit-learn notices | 记录训练数据来源与模型版本 | 通过 |
| PyTorch CUDA Runtime | [PyTorch 官方 LICENSE](https://github.com/pytorch/pytorch/blob/main/LICENSE)为 BSD-style，但二进制 wheel 同时包含多项第三方组件 | PyTorch 主体允许；随包 CUDA/NVIDIA 组件的实际文件清单与再分发条款尚未完成逐项核对 | 对最终 `_internal` 生成 SBOM/文件清单，依据 NVIDIA 适用条款确认每个 redistributable | **阻塞** |
| Transformers | [Hugging Face Transformers 官方仓库](https://github.com/huggingface/transformers)为 Apache-2.0 | 允许 | 保留许可与 NOTICE | 通过 |

## 决策

当前 `VisionGuard-Models-v1.zip` 只能作为本机候选构建产物用于安装链路验证，不得上传 GitHub Release。即使 Qwen 与 PaddleOCR 的许可允许再分发，Ultralytics detector 仍会阻塞整个组合模型包。

公开发布前必须同时满足：

1. Ultralytics 代码与 detector 权重获得与目标发行方式一致的许可路径；
2. 最终 PyInstaller `_internal` 的第三方二进制和许可文件完成逐项清单；
3. 模型 ZIP 内附对应许可文本、模型卡和来源版本；
4. `THIRD_PARTY_NOTICES.md` 与实际冻结依赖一致；
5. 由项目所有者或法律顾问复核，不以本审计表替代法律判断。

Release builder 将模型资产标记为 `publishable: false`，公开模式校验必须失败，以防误上传。

## Phase 17 deployment boundary update

The Core Runtime now executes the exported detector through ONNX Runtime and no longer bundles the Ultralytics Python package or detector-side PyTorch/CUDA libraries. ONNX Runtime is MIT-licensed and is listed in `THIRD_PARTY_NOTICES.md`. This changes only the runtime dependency boundary; it does **not** clear the detector weight. Because the weight was derived through the Ultralytics training/export path, its provenance and redistribution permission remain a release blocker pending written confirmation or replacement with a clearly licensed detector.
