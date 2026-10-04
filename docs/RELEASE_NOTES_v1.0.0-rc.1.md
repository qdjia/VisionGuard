# VisionGuard 1.0.0-rc.1 Draft Release Notes

状态：草案；尚未获准 Tag 或公开发布。

## Release alignment

- VisionGuard 自有代码已迁移为 `AGPL-3.0-only`。
- 产品定义改为“网络辅助安装/组件获取/更新 + 完全本地审核推理”，不再宣称 Fully Offline。
- Real Offline gate 为 N/A，不再阻断 v1.0 RC。
- Ultralytics Detector 在 AGPL 路径下为 `ALLOWED_WITH_CONDITIONS`。
- SBOM、manifest 与严格 validator 需要携带和验证项目许可证及源码版本映射。

## Accepted limitation

- 27 张锁定真实图片已在开发验收机完成打包 Core + 托管本地 VLM 回放，结果为 0 confirmed regression、0 potential regression、0 unsafe fast path。
- 独立干净机器复验尚未执行。该风险已针对 `v1.0.0-rc.1` 接受并记录为 `PASS_WITH_LIMITATION`；Stable Release 仍必须完成复验。

## Remaining blockers

- 许可证迁移及当前算法修复后的最终候选尚未冻结和重建。

本文件不表示候选已经公开发布。
