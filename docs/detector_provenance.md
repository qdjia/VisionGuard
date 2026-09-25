# Detector Provenance Record

审计更新：2026-09-26。结论：**当前 MIT Public RC 的 Redistribution status = `NOT_ALLOWED`；阻塞 Public RC。** 本记录是工程证据，不是法律意见。

## Artifact chain

| Field | Recorded value |
|---|---|
| Architecture | Ultralytics YOLO26n |
| Base checkpoint reference | `yolo26n.pt`，5,544,453 bytes，SHA-256 `9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef` |
| Base source | Ultralytics assets release `v8.4.0`：`https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26n.pt` |
| Training mode | `pretrained: true` |
| Training package | Ultralytics 8.4.151 |
| Training runtime | PyTorch 2.11.0+cu128 |
| Dataset | `data/visionguard_smoke`，由 `scripts/create_smoke_dataset.py` 生成的 8 张 synthetic smoke images；项目自有 fixture，随仓库 MIT License |
| Training output | `artifacts/experiments/yolo26n_smoke_640/weights/best.pt` |
| Training output SHA-256 | `0f5676be8b44d2a7d1946846e7aa7ad368de4519ad826be71f49a3e200f6cbe9` |
| Export | ONNX opset 18、dynamic batch、embedded NMS |
| Final bundled artifact | `models/core-models-v1/detector/model.onnx` |
| Final ONNX SHA-256 | `82dccb397dd39113542731e574001241bcadd2ec4a22e8c31b4592815a5b24d6` |

本地重复副本 `yolo26n.pt` 与 `weights/yolo26n.pt` 哈希一致；官方文档和下载日志把 YOLO26 权重定位到 assets release `v8.4.0`。当前证据能够固定 base → `best.pt` → ONNX 的本地字节链，但没有 Ultralytics Enterprise License。把权重导出为 ONNX 不会自动改变上游许可义务。机器可读记录见 `release-evidence/detector-provenance.json`。

## License finding

Ultralytics 官方许可页面在 2026-09-26 明确说明 pretrained、trained/fine-tuned 模型默认使用 AGPL-3.0，或者需要 Enterprise License。VisionGuard 根许可证当前为 MIT，仓库中没有 Ultralytics Enterprise License 证明，也没有实施许可方描述的完整 AGPL-3.0 发行方案。

针对**当前 MIT RC 分发方案**的工程枚举结论：**`NOT_ALLOWED`**。这不是说该模型永远不能发行，而是当前条件没有满足任一许可路径；ONNX 权重不得标记为 `publishable=true`。允许的关闭路径只有：

1. 项目所有者确认并执行完整 AGPL-3.0 合规方案；
2. 提供覆盖当前模型和分发方式的 Ultralytics 商业许可；
3. Public RC 不分发 detector 权重，并重新验收不带权重的产品行为；
4. 经用户另行批准，使用许可来源清晰的 base model 重新训练并重新完成全部回归。

在其中一种路径完成前，Detector License Gate 保持 `BLOCKED`。若选择更换 base 或重新训练，必须先完成影响分析并由用户决定，本轮没有自动替换模型。
