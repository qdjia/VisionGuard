# v1.0 Release Gate

截至 2026-10-04，源码已完成 AGPL 对齐。历史真实图片回归以明确风险接受的 `PASS_WITH_LIMITATION` 继续 RC 流程；最终 RC 尚未重建，因此当前仍不得 Tag 或公开上传二进制。

| Gate | Status | Closure |
|---|---|---|
| Project license alignment | PASS | AGPL-3.0-only metadata、LICENSE、NOTICE 与自动校验已对齐 |
| Local inference architecture | PASS | 审核链只使用本地进程/loopback；无云端推理 Provider |
| Real Offline | N/A | 不是 v1.0 产品要求，不阻断 RC |
| Detector redistribution | ALLOWED_WITH_CONDITIONS | 最终候选须满足来源记录、Corresponding Source、构建脚本、license/notice 和 commit/tag 映射 |
| Clean Core Acceptance | PASS | GitHub-hosted Windows runner 已完成候选安装、Core smoke、卸载与证据归档 |
| Fresh-user GUI Acceptance | PASS | 当前机器的新普通用户 GUI、Fast Review、卸载与重装已验收 |
| Advanced AI GPU Acceptance | PASS | RTX 4060 上的受管 Python/CUDA、Qwen VLM、Deep Review 与恢复流程已验收 |
| Overall Clean-environment Acceptance | PASS | 三个 split Windows Gate 已全部 PASS |
| Installer lifecycle | PASS | `0.9.0` → `1.0.0` 升级、降级拒绝、显式回滚、用户数据保留与最终清理均已真实验收 |
| Prebuilt VLM Runtime distribution | N/A | 已降级为 legacy/reference-only，不属于默认 Release |
| nvJitLink direct redistribution | N/A | 默认 Release 不携带该 DLL；运行时依赖由官方 PyTorch 源在用户安装时获取 |
| Historical real-image regression | PASS_WITH_LIMITATION | 开发验收机 27 张锁定图片达到 0 confirmed / 0 potential / 0 unsafe fast path；独立干净机复验延期并作为 Stable 硬门槛 |
| Final rebuilt candidate | BLOCKED | 须基于当前冻结提交重建最终 RC 并运行严格 validator |

Split Windows 验收模型见 [`windows_acceptance.md`](windows_acceptance.md)。只有三个 Windows Gate、
历史回归的受限通过仅适用于 `v1.0.0-rc.1`；Stable 仍要求独立干净机复验。最终候选重建、严格 validator 和所有实际分发许可 gate 完成后，才建议创建 `v1.0.0-rc.1`。网络只用于安装、模型获取和更新；图片审核推理仍在本地完成且不依赖云端推理 API。
