# Release Acceptance Checklist

- [ ] 独立干净 Windows 环境记录完整
- [ ] 安装器和组件 SHA-256 与 manifest 一致
- [ ] Core 启动、健康检查、Fast Review、退出无 orphan
- [ ] Advanced AI 获取/导入、安装、激活与失败回滚
- [ ] Deep Review 使用本地 VLM sidecar
- [ ] 网络观察证明审核流量仅到 loopback，未调用云端推理 API
- [ ] 升级、回滚、卸载与重装
- [ ] 历史真实图片回归
- [ ] Detector AGPL 条件与源码 commit/tag 映射完整
- [ ] NVIDIA 原生文件逐项再分发结论全部放行
- [ ] SBOM、LICENSE、NOTICE、Third-Party Notices 均随候选分发
- [ ] `python scripts/validate_release.py <candidate> --rc` 无绕过通过

可选：在隔离网络中运行附加 smoke；该项不是 v1.0 RC gate。
