# VisionGuard 1.0.0-rc.1 Draft Release Notes

状态：草案；尚未获准 Tag 或公开发布。

## Release alignment

- VisionGuard 自有代码已迁移为 `AGPL-3.0-only`。
- 产品定义改为“网络辅助安装/组件获取/更新 + 完全本地审核推理”，不再宣称 Fully Offline。
- Real Offline gate 为 N/A，不再阻断 v1.0 RC。
- Ultralytics Detector 在 AGPL 路径下为 `ALLOWED_WITH_CONDITIONS`。
- SBOM、manifest 与严格 validator 需要携带和验证项目许可证及源码版本映射。

## Remaining blockers

- Advanced AI 改为按需在线安装固定官方依赖与模型；完成后审核推理仍完全在本机运行。
- 默认 Release 不再直接分发 PyTorch/CUDA/NVIDIA DLL 或 Qwen 权重；旧分卷路径仅作为 legacy fallback 保留。
- Advanced AI 全新下载、clean Windows GUI 生命周期与历史真实图片回归仍未完成，RC 继续阻塞。
- Clean Windows、真实 GUI 生命周期和历史真实图片回归尚未完成。
- 许可证迁移后的最终候选尚未重建。

本文件不表示候选已经公开发布。
