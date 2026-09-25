# VisionGuard v1.0 Release Gate

审计日期：2026-09-25。状态值：`PASS`、`PARTIAL`、`BLOCKED`、`PENDING MANUAL`。

| Gate | Status | Evidence | Blocker / next action |
|---|---|---|---|
| Core runtime isolation | PASS | Phase 17 / 18 smoke records | 无 |
| VLM process isolation | PASS | `docs/phase18_report.md` | 无 |
| Advanced AI split build | PASS | 真实 Runtime / Models 共 9 个分卷，大小见 Phase 19 报告 | GUI 导入验收待执行 |
| Parts verification | PASS | 最终资产单卷 + 组合归档 SHA-256 | 无 |
| Streaming staging install | PASS | multipart reader 直接供 ZipArchive | 真实大包 GUI 验收待执行 |
| Atomic activation / previous | PASS | `components.json` + `components.previous.json` | 真实大包验收待执行 |
| Cancel / disk preflight | PASS | 取消标记、真实字节进度、fs2 可用空间 | GUI 人工验收待执行 |
| Upgrade / rollback / uninstall | PARTIAL | 独立版本目录、previous swap、停止 VLM 后卸载 | 大包与 Desktop upgrade 人工验收 |
| Core bundled installer | PARTIAL | 已构建 531,009,419-byte NSIS，包含 Slim Core + Models | 在干净机安装验收 |
| Clean Windows | BLOCKED | `docs/clean_machine_acceptance.md` | 尚未执行 |
| Offline | PARTIAL | Phase 18 packaged smoke | 干净机端到端待执行 |
| Single instance / shortcut / Start Menu | PARTIAL | 配置和开发验证存在 | 干净机人工确认 |
| Asset hosting | PASS (strategy) | `docs/release_asset_strategy.md` | 上传仍需许可证 Gate 与用户授权 |
| SBOM tooling | PARTIAL | `scripts/generate_sbom.py` | 已从 frozen Runtime 生成精确版本清单；许可证字段和 native 再分发仍需人工复核 |
| Detector license | BLOCKED | `docs/model_distribution_licenses.md` | 选择 AGPL 合规路径、商业许可或替换权重 |
| Qwen / Paddle license | PARTIAL | 官方上游许可记录 | 最终模型包补齐 LICENSE / notice / revision |
| PyTorch / CUDA redistribution | BLOCKED | 最终 native inventory 尚未逐项对照 NVIDIA Attachment A | 法律/发行复核 |
| Code signing | DOCUMENTED / UNSIGNED | `docs/code_signing.md` | RC 可明确 unsigned；Stable 建议受信证书 |
| Historical regression | PENDING | Phase 6/8/9/11 scripts 存在 | 新架构 fixtures / hard cases 未完整执行 |
| RC validator | BLOCKED EXPECTED | `scripts/validate_release.py --rc` | critical blockers 必须清零 |

当前建议：Commit 可在自动化验证通过后进行；RC Tag、Stable Tag、GitHub Pre-release 与 Stable Release 均为 **No**。

只有 clean-machine、Advanced AI 真实安装/升级/卸载、离线、历史回归和许可证分发门全部达到 RC 标准，且 `validate_release.py --rc` 通过，才建议 `v1.0.0-rc.1`。
