# Detector Provenance Record

审计日期：2026-09-25。结论：**Redistribution status = Unclear；阻塞 Public RC。** 本记录是工程证据，不是法律意见。

## Artifact chain

| Field | Recorded value |
|---|---|
| Architecture | Ultralytics YOLO26n |
| Base checkpoint reference | `yolo26n.pt` (exact upstream revision/hash not retained) |
| Base source | Ultralytics official pretrained model obtained through the `ultralytics` package download path |
| Training mode | `pretrained: true` |
| Training package | Ultralytics 8.4.151 |
| Training runtime | PyTorch 2.11.0+cu128 |
| Dataset | `data/visionguard_smoke`，由 `scripts/create_smoke_dataset.py` 生成的 8 张 synthetic smoke images；项目自有 fixture，随仓库 MIT License |
| Training output | `artifacts/experiments/yolo26n_smoke_640/weights/best.pt` |
| Training output SHA-256 | `0f5676be8b44d2a7d1946846e7aa7ad368de4519ad826be71f49a3e200f6cbe9` |
| Export | ONNX opset 18、dynamic batch、embedded NMS |
| Final bundled artifact | `models/core-models-v1/detector/model.onnx` |
| Final ONNX SHA-256 | `82dccb397dd39113542731e574001241bcadd2ec4a22e8c31b4592815a5b24d6` |

导出元数据能够证明 `best.pt → model.onnx` 的文件链，但不能证明最初下载的 `yolo26n.pt` revision、原始文件哈希或额外商业授权。把权重导出为 ONNX 不会自动改变上游许可义务。

## License finding

Ultralytics 官方许可页面在 2026-09-25 仍说明其代码、模型架构、训练流程以及默认模型产物受 AGPL-3.0 或商业许可路径约束。VisionGuard 根许可证当前为 MIT，仓库中没有 Ultralytics Enterprise License 证明，也没有将整个适用作品切换为 AGPL-3.0 的明确决策。

工程枚举结论：**UNCLEAR**。因此当前 ONNX 权重不得标记为 `publishable=true`。允许的关闭路径只有：

1. 项目所有者确认并执行完整 AGPL-3.0 合规方案；
2. 提供覆盖当前模型和分发方式的 Ultralytics 商业许可；
3. Public RC 不分发 detector 权重，并重新验收不带权重的产品行为；
4. 经用户另行批准，使用许可来源清晰的 base model 重新训练并重新完成全部回归。

在其中一种路径完成前，Detector License Gate 保持 `BLOCKED`。
