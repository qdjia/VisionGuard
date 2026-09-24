# Legacy Full Runtime（reference-only）

## 状态

Phase 16 的单体 Full Runtime 现已标记为 **reference-only**。它不再是默认构建、默认发行或生产基线；当前基线是 Phase 17 的 Slim CPU Core Runtime，加上 Phase 18 的可选 VLM Runtime。

旧方案把 Detector、PaddleOCR、Baseline、Routing、Fusion、PyTorch/CUDA、Transformers 和 Qwen3-VL 放进同一个 PyInstaller 目录。这样最初便于验证离线桌面推理和单进程生命周期，但产生了约 4.947 GiB Runtime，并让 Core 启动、失败和升级都与 VLM 耦合。

Phase 17 已用 ONNX Detector 和 CPU PaddleOCR 替代 Core 中的 Ultralytics/PyTorch 路径，将 Core Runtime 降至约 0.697 GiB。Phase 18 进一步把 Qwen3-VL 放入独立进程，使 Fast Review 可以在 Advanced AI 未安装、加载或故障时继续工作。

## 保留内容

- `packaging/runtime/visionguard-runtime.spec`
- `scripts/build_runtime.py --profile full`
- `src/visionguard/vlm/providers/local.py`
- 旧 Full Runtime smoke/regression 入口
- Phase 16/17 的架构、体积与验证记录

这些内容用于历史复现、回滚和新旧架构工程回归，不进入默认 Release。重新构建必须显式执行：

```powershell
python scripts/build_runtime.py --profile full
```

## 生成物策略

`runtime-build/`、`runtime-dist/`、旧 release ZIP、staging 和缓存均可从源码重建，必须保持 Git ignored。清理这些生成物不等于删除 Legacy 源码。

## 完全退役 Gate

只有独立 VLM Runtime 构建、Core→VLM、Deep Review、路由触发、structured output、fail-safe、Fusion 回归、离线、重启、崩溃隔离、无 orphan 和桌面验收全部通过后，才可在单独提交中删除旧 integration。当前结论仍是 **Reference Only**，不是“源码可删除”。
