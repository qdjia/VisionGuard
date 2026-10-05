# v1.0 Release Gate

截至 2026-10-05，源码已完成 AGPL 对齐，`v1.0.0-rc.1` 已通过严格校验并公开为 Prerelease。当前准备 `v1.0.0` Stable 候选；历史干净机复验和 Authenticode 签名仍未完成，仅通过版本限定的项目所有者风险豁免解除阻断。

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
| Historical real-image regression | PASS_WITH_LIMITATION / WAIVED_BY_OWNER for v1.0.0 | 开发验收机 27 张锁定图片达到 0 confirmed / 0 potential / 0 unsafe fast path；独立干净机复验仍未完成，项目所有者仅为 v1.0.0 接受风险 |
| Authenticode signing | NOT_COMPLETED / WAIVED_BY_OWNER for v1.0.0 | 安装包未签名，必须披露 SmartScreen 风险并提供 SHA-256 |
| Final rebuilt RC candidate | PASS | `v1.0.0-rc.1` 已完成严格 validator 并公开为 Prerelease |

Split Windows 验收模型见 [`windows_acceptance.md`](windows_acceptance.md)。只有三个 Windows Gate、
历史回归的结果仍是 `PASS_WITH_LIMITATION`，代码签名仍是 `NOT_COMPLETED`。项目所有者已通过机器可读证据对且仅对 `v1.0.0` 接受这两项风险；这不会改变原始状态，也不会自动延续到未来版本。Stable validator 必须验证豁免的版本、所有者、理由、剩余风险与披露要求。网络只用于安装、模型获取和更新；图片审核推理仍在本地完成且不依赖云端推理 API。
