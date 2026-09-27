# Release Engineering History

本文只保留对当前架构仍有解释价值的历史决策和实测数据。当前发布判定以
[`release_gate.md`](release_gate.md) 为准，历史阶段报告不作为现行发布依据。

## 架构演进

| 阶段 | 方案 | 实测结果 | 后续决定 |
|---|---|---:|---|
| Phase 16 | 单体 PyInstaller Runtime | Runtime 约 4.947 GiB，完整安装约 9 GiB | 仅保留源码级 reference，不作为默认发行方案 |
| Phase 17 | Slim CPU Core | Core Runtime 748,413,790 bytes；Core Models 156,803,606 bytes | 成为 Fast Review 基线 |
| Phase 18 | Core 与 VLM 独立进程 | VLM Runtime 约 4.216 GiB；VLM Models 约 3.974 GiB | 证明 sidecar、动态端口、token、lazy load 和故障隔离可行 |
| Phase 19 | Advanced AI 分卷 | Advanced AI 分卷总计约 8.191 GiB | 因体积、再分发与升级成本降级为显式 fallback |
| 当前 | Online Bootstrap | Release 只携带轻量 bootstrap；受管环境和固定模型从官方源获取 | 默认方案，审核推理仍完全在本机执行 |

## 关键工程证据

- Detector ONNX：10,685,076 bytes，13 张回归图像中 307/307 detections 匹配，最小 IoU
  0.889982，最大 confidence delta 0.000019922。
- Slim Core：移除了 Core 中的 PyTorch、CUDA、Ultralytics 和完整 Transformers 运行依赖；
  PaddleOCR 仍是 Core 的主要体积来源。
- 独立 VLM：同一进程内模型只初始化一次；Core 在 VLM 缺失或崩溃时保持可用，并以
  `partial + manual review` fail closed。
- 旧分卷安装：验证过顺序、大小、逐卷 SHA-256、组合 SHA-256、staging、原子激活和
  previous pointer 回滚，但未作为公开发行方案。
- Online Bootstrap：受管 CPython、固定依赖、CUDA 检查、动态端口、session token 和真实
  Deep Review 已在开发机通过；完整 fresh-cache 模型下载仍受官方源网络超时阻塞。

## 历史体积结论

旧 Full Runtime 的主要体积来自 CUDA/cuDNN（约 2.986 GiB）和 PyTorch（约 1.116 GiB）。
拆分后的 Core Runtime 约 0.697 GiB，Core Models 约 0.146 GiB，Core-only 合计约 0.843 GiB。
未量化的 Qwen3-VL-2B 模型约 3.974 GiB。历史数字用于解释架构选择，不代表当前最终安装包
或安装后占用；最终数字必须从重新构建的候选包和全新安装中获取。

## 已退役生成物

旧 RC、VLM PyInstaller runtime、分卷资产、Tauri staging、Rust target 和重复模型包均是
可重建生成物，不在 Git 中保存。需要复现旧方案时使用保留的构建脚本和显式参数，而不是
依赖历史二进制目录。

## 被替代的历史结论

- 项目许可证已迁移为 AGPL-3.0-only；早期 MIT 分析不再适用。
- 默认发行不再直接携带 PyTorch/CUDA/NVIDIA DLL，因此旧的直接再分发门禁不适用于默认包。
- “完全离线安装”不是 v1.0 产品承诺；联网只用于安装、模型获取和更新，图片审核推理本地完成。
- 旧 multipart Advanced AI 只保留为显式兼容路径，不应被描述为当前用户安装流程。

