# VisionGuard v1.0 Release Gate

审计更新：2026-09-26。状态值：`PASS`、`PARTIAL`、`FAIL`、`BLOCKED`、`PENDING MANUAL`。

| Gate | Status | Evidence | Blocker / next action |
|---|---|---|---|
| Core runtime isolation | PASS | Phase 17 / 18 smoke records | 无 |
| VLM process isolation | PASS | `docs/phase18_report.md` | 无 |
| Advanced AI split build | PASS | 真实 Runtime / Models 共 9 个分卷，大小见 Phase 19 报告 | GUI 导入验收待执行 |
| Parts verification | PASS | 最终资产单卷 + 组合归档 SHA-256 | 无 |
| Streaming staging install | PASS | multipart reader 直接供 ZipArchive | 真实大包 GUI 验收待执行 |
| Atomic activation / previous | PASS | `components.json` + `components.previous.json` | 真实大包验收待执行 |
| Cancel / disk preflight | PASS | 取消标记、真实字节进度、fs2 可用空间 | GUI 人工验收待执行 |
| Upgrade / rollback / uninstall | PENDING MANUAL | 独立版本目录、previous swap、停止 VLM 后卸载 | 真实大包与 Desktop upgrade 人工验收 |
| Core bundled installer | PARTIAL | 已构建 531,009,419-byte NSIS，包含 Slim Core + Models | 在干净机安装验收 |
| Clean Windows | BLOCKED | 本机无 Sandbox、Hyper-V、VMware 或 VirtualBox | 需要用户提供独立干净 Windows 环境 |
| Offline | PARTIAL | Packaged VLM offline-mode smoke PASS | 真正断网的干净机端到端待执行 |
| Single instance / shortcut / Start Menu | PARTIAL | 配置和开发验证存在 | 干净机人工确认 |
| Asset hosting | PASS (strategy) | `docs/release_asset_strategy.md` | 上传仍需许可证 Gate 与用户授权 |
| SBOM inventory | PASS | 5 份 CycloneDX：Desktop、Core、VLM、Models、Distribution | 许可结论由独立 License Gate 负责 |
| Detector license | BLOCKED / `NOT_ALLOWED` for current MIT RC | base/trained/ONNX hash chain and official license statement fixed in `release-evidence/detector-provenance.json` | 实施合格 AGPL 路径、提供商业许可或不分发权重；换模型需用户另行决定 |
| Qwen / Paddle evidence | PASS | `release-evidence/model-provenance.json` | 最终候选需重建并携带 evidence |
| PyTorch / CUDA redistribution | BLOCKED | `torch_cuda → cusparse → nvJitLink` 为静态依赖；20 个实例 / 19 个唯一 SHA；18 条件允许、1 `UNCLEAR` | 获取 filename discrepancy 的书面确认；该 DLL 不能在当前依赖链中直接移除 |
| Code signing | PASS (RC decision) | `docs/code_signing.md` | RC 明确 unsigned；Stable 建议受信证书 |
| Historical regression | BLOCKED | 16/16 contract PASS；near-boundary=`DIAGNOSTIC_ONLY` | 真实图像覆盖与 clean-machine replay 仍不足 |
| RC validator | FAIL EXPECTED | `scripts/validate_release.py --rc` | critical blockers 必须清零，禁止 bypass |

当前建议：本阶段修改在自动化验证通过后可以 Commit / push normal branch；RC Tag、Stable Tag、GitHub Pre-release 与 Stable Release 均为 **No**。

只有 clean-machine、Advanced AI 真实安装/升级/卸载、离线、历史回归和许可证分发门全部达到 RC 标准，且 `validate_release.py --rc` 通过，才建议 `v1.0.0-rc.1`。
