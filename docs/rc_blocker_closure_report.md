# VisionGuard RC Blocker Closure Report

> 历史快照（已被取代）：本报告记录迁移前的 MIT / Fully Offline 状态。当前政策以 `docs/agpl_migration.md` 和 `docs/release_gate.md` 为准。

日期：2026-09-25  
目标版本：`v1.0.0-rc.1`  
结论：**RC BLOCKED**

本轮只处理 Release blocker，没有新增产品功能。Qwen/Paddle provenance、16 类行为合同和 20 个 NVIDIA DLL 文件实例（19 个唯一 SHA-256）的逐文件工程审计已落地；无法由当前开发机真实完成的 Clean Windows、断网和 GUI 生命周期仍保持 `BLOCKED`。

## Final Blocker Matrix

| Blocker | Severity | Result | Minimum closure action |
|---|---|---|---|
| Detector redistribution | Critical | BLOCKED / current MIT RC `NOT_ALLOWED` | 用户选择 AGPL 合规、商业许可、不分发权重或批准换 base/重训 |
| Historical real-image coverage | Major | BLOCKED | 建立 redistribution-safe 真实图像 suite 并在 packaged/clean machine 回放 |
| Clean Windows | Critical | BLOCKED | 独立 Windows 完成 22 项清单 |
| True offline | Critical | BLOCKED | 禁用网卡/隔离网络完成端到端验收 |
| GUI lifecycle | Major | BLOCKED | 人工点击、关闭、no-orphan、重开、升级/回滚/卸载证据 |
| NVIDIA redistribution | Critical | BLOCKED | `nvJitLink` 为静态依赖，不能直接移除；需解决官方材料的 filename discrepancy |
| Final candidate rebuild | Major | BLOCKED | 清除 VLM SBOM 中 pytest metadata，重建并重新校验全部证据/hash |

完整 closure criteria 见 `docs/rc_blocker_closure_plan.md`。

## Required 52-point handoff

| # | Item | Result |
|---:|---|---|
| 1 | RC Blocker Summary | **RC BLOCKED**；最少剩余项见上表 |
| 2 | Final Blocker Matrix | 已建立；含 severity、证据、用户/外部动作和 closure criteria |
| 3 | Detector Provenance | YOLO26n → Ultralytics 8.4.151 fine-tune → best.pt → ONNX；两级产物 SHA-256 已记录 |
| 4 | Detector License Status | current MIT RC=`NOT_ALLOWED`；不得公开上传 detector asset |
| 5 | Detector Release Options | AGPL 合规、商业授权、用户导入、许可清晰 base 重训；未自动选择 |
| 6 | Historical Regression Suite Size | 16 个 source-level contracts + 2 个历史图片 fixture（1 eligible）；可证明 real-world provenance 数量为 0 |
| 7 | Near-boundary Analysis | risky OCR/baseline/VLM 一致；VLM path；score `0.700001`；距 high boundary `0.000001`；final high/manual |
| 8 | Historical Regression Result | 合同 16/16 PASS；near-boundary=`DIAGNOSTIC_ONLY`；真实图像覆盖仍 BLOCKED |
| 9 | Legacy Runtime Verdict | Reference Only；未删除 |
| 10 | Qwen Revision | `89644892e4d85e24eaac8bacfd4f463576704203` |
| 11 | Qwen License Evidence | Apache-2.0 model-card metadata、immutable URL、canonical license、官方 hash/size match；PASS (evidence) |
| 12 | Paddle Model Provenance | det `8e0f56…`、rec `e5a92b…`、orientation `cd237a…`；官方 hash/size match |
| 13 | Paddle License Evidence | 三模型 README metadata = Apache-2.0；canonical text retained；PASS (evidence) |
| 14 | ONNX Runtime Evidence | 1.26.0；MIT；Core excludes CUDA/TensorRT providers；native/SBOM mapping retained |
| 15 | PyTorch Evidence | `2.11.0+cu128`，torchvision `0.26.0+cu128`；bundled LICENSE/NOTICE；native conditions separate |
| 16 | NVIDIA Native DLL Count | 20 个文件实例；19 个唯一 SHA-256（两份 cudart 路径共享同一哈希） |
| 17 | NVIDIA Per-DLL Audit | Hash、size、source package/version、category、canonical name、URL/reference、status 已记录 |
| 18 | Native Redistribution Status | 文件实例：19 `ALLOWED_WITH_CONDITIONS` + 1 `UNCLEAR`；唯一二进制：18 + 1；`nvJitLink_120_0.dll` 使结果保持 BLOCKED |
| 19 | Final SBOM | 5 份现有候选 SBOM；需随重建刷新，当前不是可发布 final |
| 20 | SBOM Validation | Inventory/schema/hash local valid；RC hygiene 发现 VLM SBOM 含 pytest metadata，BLOCKED pending rebuild |
| 21 | THIRD_PARTY_NOTICES Status | 已更新精确 model/native evidence；final candidate 待重建携带 |
| 22 | Clean-machine Environment | 不可用；NOT TESTED / BLOCKED |
| 23 | Clean-machine Core Install | NOT TESTED |
| 24 | Shortcut | NOT TESTED on clean machine |
| 25 | Start Menu | NOT TESTED on clean machine |
| 26 | Single Instance | Source automation exists；clean GUI NOT TESTED |
| 27 | Fast Review | Development packaged smoke PASS；clean machine NOT TESTED |
| 28 | No-VLM Fail-safe | Development integration PASS；clean machine NOT TESTED |
| 29 | Advanced AI Install | Package/parts verified；real GUI clean install NOT TESTED |
| 30 | Deep Review | Development packaged VLM PASS；clean GUI NOT TESTED |
| 31 | Routing-triggered VLM | Development integration PASS；clean GUI NOT TESTED |
| 32 | Real Offline Test | NOT TESTED；environment variables不计作断网证据 |
| 33 | GUI Lifecycle | NOT TESTED |
| 34 | Window Close | Automated shutdown covered；real X click NOT TESTED |
| 35 | No Orphan | Automated path covered；real GUI NOT TESTED |
| 36 | Upgrade | NOT TESTED on clean machine |
| 37 | Rollback | NOT TESTED on clean machine |
| 38 | Uninstall | NOT TESTED on clean machine |
| 39 | Reinstall | NOT TESTED on clean machine |
| 40 | Authenticode Decision | Unsigned RC allowed with disclosure；Stable recommended trusted Authenticode |
| 41 | SmartScreen Status | Unsigned RC may warn；do not instruct users to disable Windows Security |
| 42 | Asset Hosting Status | GitHub Release + 1 GiB split strategy valid；upload not authorized while blocked |
| 43 | Asset Count | Existing candidate: 11 binary/model assets；22 files including metadata |
| 44 | Max Asset Size | 1,073,741,824 bytes (1 GiB) |
| 45 | Release Manifest | Existing schema v3 valid locally；new evidence/gates require rebuild |
| 46 | SHA256 | Existing `SHA256SUMS.txt`: 21 entries；new evidence require regenerated checksum set |
| 47 | RC Validator Result | FAIL CLOSED；no bypass |
| 48 | Remaining Critical Blockers | Detector、Clean Windows、True Offline、NVIDIA exact mapping、RC validator |
| 49 | Remaining Major Blockers | Real-image coverage、GUI lifecycle、final rebuild/SBOM hygiene、upgrade/uninstall evidence |
| 50 | Known Non-blocking Limitations | Unsigned RC、manual ~8.191 GiB Advanced AI、only RTX 4060 Laptop 8 GiB validated |
| 51 | User Action Required | 提供独立 Windows 验收；选择 detector license path；获取 `nvJitLink` redistribution confirmation |
| 52 | Versioning Recommendation | Commit/push normal branch Yes；RC Tag/Pre-release/Stable No |

## Verification completed on the development machine

- Python: 184 tests passed；2 upstream deprecation warnings，no failures.
- Fixed behavioral contracts: 16/16 `PASS`.
- Frontend: 46 tests passed；ESLint、TypeScript build 和 production Vite build passed.
- Rust desktop shell: 21 tests passed；`cargo fmt --check` and `cargo check` passed.
- Ruff lint/format、Python compileall and `git diff --check`: passed.
- Existing local candidate: local integrity validator passed.
- Existing local candidate under strict `--rc`: failed closed as required. It predates the new evidence bundle, contains `pytest` metadata in the VLM SBOM, is not marked public-ready, and all externally unverified gates remain `BLOCKED`.

These development-machine checks do not replace clean-machine, true-offline, GUI lifecycle, license, or final rebuilt-candidate acceptance.

## Near-decision-boundary classification

- Input evidence: OCR `鼓励暴力伤害他人`，confidence `0.9999548`；baseline probability `0.9966895`；VLM `high/sensitive_text`，success。
- Old behavior: stored replay comparison is `unchanged`.
- New behavior: route `vlm_path`；fusion `high`；manual review `true`；score `0.700001`.
- Safety impact: no unsafe low、no incorrect fast path、no lost manual review、no risk downgrade.
- Classification: `DIAGNOSTIC_ONLY`. The remaining diagnostic flag is expected to expose boundary fragility; thresholds and ground truth were not changed.

## User Action Required

1. 在独立、无 VisionGuard 开发环境污染的 Windows 机器执行 `docs/clean_machine_acceptance.md`，并返回去隐私化证据。
2. 明确 detector 路径：AGPL 合规、Ultralytics 商业许可、不随 RC 分发，或批准许可清晰 base 的重训评估。
3. 向 NVIDIA/license holder 或合格审查方确认 `nvJitLink_120_0.dll` 是否落入当前 Attachment A 的允许变体；否则从 runtime 移除并做全量回归。
4. 提供/确认可再分发真实图像 fixture，完成 packaged runtime 与 clean-machine historical replay。

## Versioning Recommendation

Commit:  
Yes

Recommended commit message:  
`chore(release): harden v1.0 RC blocker closure gates`

Push normal branch:  
Yes

RC Tag:  
No

Recommended RC tag:  
N/A

GitHub Pre-release:  
No

Stable Tag:  
No

Recommended stable tag:  
N/A

GitHub Stable Release:  
No

Blocking reasons:

- Clean-machine, true-offline and real GUI lifecycle evidence is unavailable.
- Detector redistribution is `NOT_ALLOWED` for the current MIT RC until an approved license path is implemented.
- One NVIDIA native DLL remains `UNCLEAR`.
- Real-image historical coverage and final rebuilt candidate validation are incomplete.

Known non-blocking limitations:

- Unsigned RC may trigger SmartScreen.
- Advanced AI is a manual approximately 8.191 GiB import.
- Hardware validation is limited to RTX 4060 Laptop 8 GiB.

Next Release Gate:  
Close external license/clean-machine actions, expand real-image regression, rebuild the candidate with clean runtime metadata, then require `python scripts/validate_release.py --rc` to PASS without bypass.
