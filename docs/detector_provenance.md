# Detector Provenance and Redistribution Decision

审计日期：2026-09-26。当前 AGPL 开源发行路径结论：**`ALLOWED_WITH_CONDITIONS`**。这是工程证据，不是法律意见。

## 来源链

| Item | Evidence |
|---|---|
| Base checkpoint | Ultralytics `yolo26n.pt`, assets release `v8.4.0`, SHA-256 `9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef` |
| Training package | `ultralytics==8.4.151` |
| Dataset | `data/visionguard_smoke`，项目生成的 synthetic fixture，项目自有部分随 AGPL-3.0-only 发行 |
| Fine-tuned checkpoint | SHA-256 `0f5676be8b44d2a7d1946846e7aa7ad368de4519ad826be71f49a3e200f6cbe9` |
| Exported ONNX | SHA-256 `82dccb397dd39113542731e574001241bcadd2ec4a22e8c31b4592815a5b24d6` |

导出 ONNX 不消除上游及派生模型许可义务。旧 MIT RC 路径因没有 Enterprise 证明或 AGPL 发行实现而为 `NOT_ALLOWED`，该历史判断已由本次 AGPL 迁移取代。

## 放行条件

1. 根许可证、Python/Node/Rust/Tauri 元数据均声明 `AGPL-3.0-only`。
2. 向接收者提供适用的 Corresponding Source、构建/训练/导出脚本与修改信息。
3. 发行包包含许可证、Notice、第三方声明和本来源记录。
4. 模型 base、训练产物、ONNX 的版本与哈希保持可追溯。
5. 最终 manifest 记录精确源码 commit 和与版本一致的预期 tag。
6. 严格 validator 对上述条件 fail closed。

官方许可说明：<https://www.ultralytics.com/license>。
