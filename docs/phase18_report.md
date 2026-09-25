# Phase 18 Engineering Report

> 历史快照：本报告中的 MIT / offline 描述记录当时状态；当前政策以 `docs/agpl_migration.md` 和 `docs/release_gate.md` 为准。

验证日期：2026-09-24。结论：组件化 Core + Optional VLM 架构已形成并完成本机工程验证；仍不满足公开 v1.0 或 RC 发行门禁。

## Legacy Full Runtime Audit

Legacy Full Runtime 已标记为 `reference-only`，默认 build/release 已切换到 CPU Core。保留旧 source、PyInstaller spec、显式 `--profile full` 构建入口、LocalVLMProvider、历史 smoke/benchmark 与设计文档。已删除可重建且受 Git ignore 保护的 `runtime-build/`（0.296 GiB）、`runtime-dist/`（4.947 GiB）和旧 `release/`（9.268 GiB）；删除不可直接恢复，但可由保留脚本重建。

退役 verdict：**Reference Only**。新架构已经不依赖旧单体产物，但在干净机 Desktop 全流程、组件安装器和更完整新旧样本回归完成前，不建议删除 Legacy source/integration。

## 架构与合同

- Core：Detector ONNX、PaddleOCR、Baseline、Routing、Fusion、Review orchestration。
- VLM Runtime：Qwen3-VL、processor、prompt、structured parse/Pydantic/policy validation、health/meta/lifecycle。
- Transport：`127.0.0.1` loopback HTTP，OS 动态端口，multipart 图片；不传 Base64，不返回 raw generation。
- API major：`1`；端点为 `/health/live`、`/health/ready`、`/v1/meta`、`/v1/analyze`。
- 注册：Desktop 启动轻量 VLM 进程后，以 Core control token 调用 `PUT /_runtime/vlm`；Core 的线程安全 `RemoteVLMProvider` 在运行时切换 endpoint。
- 安全：Core 与 VLM 使用不同的每进程随机 token；VLM 请求头为 `X-VisionGuard-Session`，只接受 loopback。
- 兼容：注册时校验 VLM API major 和 prompt version；VLM 启动校验 model bundle type/version、API major 与 prompt versions。

采用“VLM 进程预启动、模型首次 analyze 时 lazy load”的方案。Core Ready 不等待 VLM；同一 VLM PID 内模型加载一次并保持到 Stop/退出。产品态为 Not Installed、Installed、Starting、Loading Model、Ready、Failed、Stopping/Stopped，失败时提供只重启 Advanced AI 的动作。

## 体积与性能

| 项目 | 实测 |
|---|---:|
| Core Runtime | 748,419,792 B（0.697 GiB） |
| Core Models | 156,803,606 B（0.146 GiB） |
| VLM Runtime unpacked | 4,527,251,608 B（4.216 GiB） |
| VLM Runtime ZIP | 2,861,409,521 B（2.665 GiB） |
| VLM Models | 4,266,642,871 B（3.974 GiB） |
| Core model initialization | 4,918.98 ms |
| VLM lightweight process start | 604.95 ms（最佳复跑）；最终 windowed smoke 2,617.66 ms |
| VLM model cold load | 8,821.13 ms（另一次 8,669.96 ms） |
| First Deep Review | 12,911.77 ms（另一次 13,289.51 ms） |
| Subsequent Deep Review | 3,562.56 / 3,588.01 ms |
| GPU memory before/loaded | 1,141 / 5,756 MiB，总量净增约 4,615 MiB |
| VLM init count after 3 requests | 1，同 PID |

VLM Runtime 最大部分是 `torch` 4,078.8 MiB，其次 Transformers 44.3 MiB、TorchVision 23.1 MiB、NumPy libs 20 MiB。Core 再次审计未发现 Torch、Transformers、Ultralytics、CUDA 或 cuDNN。当前 VLM ZIP 仍超过 2 GiB，不能作为单个 GitHub asset；模型与 Runtime 都需要分卷或外部托管。

## 行为验证

- Core 无 VLM：Ready；`core_ready=true`、`fast_review=true`、`vlm_available=false`、`deep_review=false`。
- No-VLM review：`partial + medium + requires_manual_review=true`；没有 unsafe low fallback。
- Core + VLM：动态注册后 `vlm_available/deep_review=true`；真实 cascaded review 为 completed/low，VLM module success。
- VLM crash：Core PID 不变；下一次 review 为 partial/medium/manual；Core 继续存活。
- Offline：`HF_HUB_OFFLINE=1`、`TRANSFORMERS_OFFLINE=1` 下 packaged VLM 完成真实推理。
- Shutdown：smoke 结束后未发现 `visionguard-core-runtime`、`visionguard-vlm-runtime` 或 legacy runtime orphan。
- Structured output：Remote Runtime 返回并由 Core 直接消费 `ModerationResult`；164 项 Python 回归覆盖 schema、token、version、timeout/fail-safe 与既有 Phase 6/7/8/9 行为。

当前小样本只构成 engineering regression：真实 safe 图结果、risk/category/schema 与 Local provider 合同一致；Fusion 和 Routing 的既有回归套件通过。没有把这些结果描述为真实业务准确率。

## Release、分卷与量化

Release manifest schema v2 将 Desktop、Core Runtime、Core Models 标为 required，将 VLM Runtime/Models 标为 optional。`scripts/split_release_asset.py` 生成有序 part、逐卷 SHA-256 和源文件总 SHA-256；最终安装器应在临时目录自动校验/拼装并原子激活，不能让用户手工合并。

VLM 量化状态仍为 **未采用**：没有可在当前 Windows frozen runtime 中通过 structured output、risk/category、延迟、显存和稳定性 Gate 的量化候选，BF16 仍是已验证 reference。不得用估算 INT4 数字冒充结果。

许可审计已按 Core/VLM 组件边界更新。Detector 衍生权重许可、最终 frozen SBOM/NVIDIA 文件条款、代码签名、公开资产托管和 clean-machine acceptance 仍是 blocker。

## Quality Gate

- Python：164 passed；Ruff check/format、compileall 通过（仅有 FastAPI TestClient/httpx2 迁移警告）。
- Frontend：45 passed；ESLint、TypeScript、Vite production build 通过。
- Rust：19 passed；Cargo fmt/check 通过。
- Packaging：Core 与 VLM PyInstaller build 成功；Core-only、VLM offline、Core+VLM、crash isolation、shutdown smoke 通过。
- Repo：`git diff --check`、secret scan、absolute-path scan、tracked >50 MiB scan 通过。

## 当前限制

Advanced AI 的最终 ZIP/分卷导入 UI、原子安装/升级/回滚尚未完成完整 clean-machine 人工验收；Rust 已复用既有 lifecycle 行为与新 manager，但 VLM 专属的进程级 fake-runtime 场景还需要在 CI 中扩展。VLM Runtime 仍为 4.216 GiB，主要由 CUDA PyTorch 决定；未量化。没有生成签名安装器，也没有上传、Tag 或 Release。
