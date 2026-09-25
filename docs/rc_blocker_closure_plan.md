# RC Blocker Closure Plan

审计更新：2026-09-26。状态只使用 `PASS`、`FAIL`、`BLOCKED`、`N/A`。本表是工程审计，不是法律意见。

| Blocker | Severity | Current Evidence | Required Evidence | Can Fix In Code? | User Action? | External Verification? | Blocks RC Tag? | Closure Criteria |
|---|---|---|---|---|---|---|---|---|
| Detector / Ultralytics redistribution | Critical | assets `v8.4.0` base URL/hash、trained/ONNX hashes 和官方许可声明已固定；当前 MIT RC=`NOT_ALLOWED` | AGPL 合规决策、适用商业授权，或用户批准的不随包分发/更换 base 路径 | Partial | Yes | Yes | Yes | 工程结论为 `ALLOWED` 或 `ALLOWED_WITH_CONDITIONS` 且条件已实现 |
| Historical near-boundary case | Major | 最终 `high`、VLM success、manual review；score `0.700001` | 固定字段证据和安全影响分类 | Yes | No | No | Yes | 分类不是 `CONFIRMED_REGRESSION`，且无 unsafe low/fast pass |
| Historical coverage | Major | 16 个合同；2 个历史图片 fixture、1 eligible；可证明 real-world provenance 的图片为 0 | 20–50 个可再分发、已验证的真实图片 suite，覆盖要求场景并在 packaged runtime/clean machine 回放 | Partial | Yes | Yes | Yes | 所有必需场景有结果；无 `CONFIRMED_REGRESSION` |
| Clean Windows acceptance | Critical | 当前机器无 Sandbox/Hyper-V/VMware/VirtualBox | 独立无开发环境污染的 Windows 机器证据 | No | Yes | Yes | Yes | 22 项 clean-machine checklist 全部 PASS |
| Real offline acceptance | Critical | offline-mode smoke only | 禁用网卡或隔离 VM 网络后的端到端记录 | No | Yes | Yes | Yes | Core、Fast、VLM lazy load、Deep、routing VLM 全部 PASS |
| GUI lifecycle | Major | 自动化 sidecar shutdown only | 人工鼠标验收、时间与隐私处理后的截图 | No | Yes | Yes | Yes | 指定 GUI 操作、X close、no orphan、reopen 全部 PASS |
| Qwen provenance/license evidence | Major | 精确 revision、官方 hash/size、模型卡元数据、Apache-2.0 文本已保留 | 最终候选包包含并校验这些 evidence | Yes | No | No | Yes | manifest、SBOM、发行证据与候选 artifact 一致 |
| PaddleOCR model evidence | Major | 三模型精确 revision、官方 hash/size、README license metadata、Apache-2.0 文本 | 最终候选包包含并校验 evidence | Yes | No | No | Yes | manifest、SBOM、发行证据与候选 artifact 一致 |
| NVIDIA native redistribution | Critical | 20 个实例 / 19 个唯一 SHA；`torch_cuda → cusparse → nvJitLink` 依赖和隔离加载探针已固定；1 个 `UNCLEAR` | 许可方/合格审查确认 Attachment A 与 Windows 指南的 filename discrepancy | No | Yes | Yes | Yes | 所有 required DLL 均 `ALLOWED`/`ALLOWED_WITH_CONDITIONS` 且满足条件 |
| Final RC validator | Critical | Local PASS；RC fail closed | 所有硬 Gate 的真实证据及最终重建 | Yes | Yes | Yes | Yes | `validate_release.py --rc` 无 bypass PASS |

## 执行边界

- 不修改 routing/fusion threshold、ground truth 或 expected result 来制造通过。
- 不自动更换 detector base、缩减 RC scope、提交、打 tag 或发布。
- 无独立 Windows 环境时，Clean/Offline/GUI 保持 `BLOCKED`。
- 许可证文本存在歧义时保持 `UNCLEAR`，交由 license holder 或合格法律审查关闭。
