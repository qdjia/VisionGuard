# v1.0 Release Gate

截至 2026-09-26，源码已完成 AGPL 对齐，但正式 RC 仍为 **BLOCKED**，不得 Tag 或公开上传二进制。

| Gate | Status | Closure |
|---|---|---|
| Project license alignment | PASS | AGPL-3.0-only metadata、LICENSE、NOTICE 与自动校验已对齐 |
| Local inference architecture | PASS | 审核链只使用本地进程/loopback；无云端推理 Provider |
| Real Offline | N/A | 不是 v1.0 产品要求，不阻断 RC |
| Detector redistribution | ALLOWED_WITH_CONDITIONS | 最终候选须满足来源记录、Corresponding Source、构建脚本、license/notice 和 commit/tag 映射 |
| NVIDIA native redistribution | BLOCKED | `nvJitLink_120_0.dll` 映射仍为 `UNCLEAR` |
| Clean Windows | BLOCKED | 独立干净 Windows 尚未验收 |
| GUI lifecycle | BLOCKED | 安装/启动/升级/回滚/卸载/重装尚未完成真实 GUI 验收 |
| Historical real-image regression | BLOCKED | 测试集与签字证据不足 |
| Final rebuilt candidate | BLOCKED | 本轮按要求不重建候选 |

只有严格 validator、clean-machine、GUI lifecycle、历史回归和所有实际分发许可 gate 全部通过，才建议创建 `v1.0.0-rc.1`。网络可用于安装、模型获取和更新；图片审核推理仍在本地完成且不依赖云端推理 API。
