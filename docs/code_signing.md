# Windows Code Signing Decision

审计日期：2026-09-25。

- 本地构建没有配置 Authenticode 证书。
- 自签名只能用于测试签名流程，不能描述为正式 Signed Release。
- 如果 RC 通过其他所有 Gate，可以发布 **unsigned release candidate**，但 Release Notes 必须显著说明 Windows SmartScreen 可能拦截或警告。
- 面向公开非技术用户的稳定版建议使用受信任的代码签名证书，并在 clean-machine 环境验证签名、安装、升级和卸载。
- 证书成本与购买流程不作为代码完成度的虚假指标；没有证书时 Stable Gate 保持阻断。

## RC decision

对当前开源作品集定位，`1.0.0-rc.1` 允许以 **Unsigned Release Candidate** 发布，前提是其余 RC 硬 Gate 全部通过、SHA-256 完整，并在下载页和 Release Notes 显著披露 SmartScreen 风险。因此 Signing Decision Gate 对 RC 为 **PASS（documented unsigned）**，不是当前 RC blocker；对 Stable v1.0 仍为建议解决项。
