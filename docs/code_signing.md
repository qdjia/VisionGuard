# Windows Code Signing Decision

审计日期：2026-09-25。

- 本地构建没有配置 Authenticode 证书。
- 自签名只能用于测试签名流程，不能描述为正式 Signed Release。
- 如果 RC 通过其他所有 Gate，可以发布 **unsigned release candidate**，但 Release Notes 必须显著说明 Windows SmartScreen 可能拦截或警告。
- 面向公开非技术用户的稳定版建议使用受信任的代码签名证书，并在 clean-machine 环境验证签名、安装、升级和卸载。
- 证书成本与购买流程不作为代码完成度的虚假指标；没有证书时 Stable Gate 保持阻断。
