# VisionGuard v1.0 RC Acceptance Report

日期：2026-09-25  
候选：`1.0.0-rc.1`（未创建 Tag）  
最终结论：**RC BLOCKED**

## RC Acceptance Summary

本阶段没有新增产品功能。完成了最终候选重建、22 文件资产布局、全元数据 SHA-256、5 份 CycloneDX SBOM、native inventory、官方许可/托管规则复核、冻结 VLM/Core 联调和现有 hard-case live regression。Local Validator PASS；RC Validator fail closed。

当前机器没有可用 Windows Sandbox/VM，不能完成 Clean-machine、真实 GUI 安装生命周期和真正断网验收。Detector、模型 provenance 和 NVIDIA native redistribution 也尚未闭环。不得 Tag 或公开上传。

## Final Gate Table

| Gate | Result | Evidence / blocker |
|---|---|---|
| Core Package | PASS (local) | 506.4 MiB NSIS；packaged Core smoke 已通过 |
| Advanced AI Package | PASS (package) / BLOCKED (GUI acceptance) | 9 verified parts；真实 Desktop 导入未在 clean machine 执行 |
| Atomic Install | PASS (implementation) / PENDING MANUAL | staging、hash validation、atomic registry |
| Upgrade / Rollback / Uninstall | PENDING MANUAL | 代码与自动化存在；真实大包/桌面验收未执行 |
| Clean Machine | BLOCKED | 无独立 Windows 环境 |
| Offline | PARTIAL | packaged VLM offline-mode PASS；真正断网未执行 |
| Historical Regression | FAIL | 唯一 eligible hard case 仍有 near-boundary failure；样本矩阵不足 |
| Distribution Licenses | BLOCKED | detector、Qwen/Paddle bundle provenance 未闭环 |
| CUDA/cuDNN | BLOCKED | 19 个 NVIDIA candidate DLL 待逐项 Attachment A 复核 |
| SBOM | PASS (inventory) | Desktop 815、Core 443、VLM 225、Models 44、Distribution 1 |
| Signing | PASS for RC decision | Unsigned RC 明确披露；Stable 仍建议 Authenticode |
| Asset Hosting | PASS (strategy) | GitHub Release，22 assets，单文件均小于 2 GiB |
| README | PASS (preparation mode) | 未宣称 RC 已发布 |
| Local Validator | PASS | schema、hash、parts、metadata、SBOM 完整 |
| RC Validator | FAIL EXPECTED | 无 bypass；保留全部硬阻塞 |

## Execution Results — 52-point handoff

| # | Required result | Actual result |
|---:|---|---|
| 1 | RC Acceptance Summary | RC BLOCKED |
| 2 | Final Gate Table | 见上表 |
| 3 | Clean-machine Environment | 不可用；当前开发机不合格 |
| 4 | Core Install Result | NSIS 构建与 packaged smoke PASS；clean install 未执行 |
| 5 | Desktop Shortcut | PENDING MANUAL |
| 6 | Start Menu | PENDING MANUAL |
| 7 | Single Instance | 自动化存在；真实桌面 PENDING MANUAL |
| 8 | Core Ready | Packaged smoke PASS |
| 9 | Fast Review | Packaged smoke PASS |
| 10 | No-VLM Fail-safe | PASS on development machine：partial / medium / manual review |
| 11 | Advanced AI Install | BLOCKED：真实 GUI 导入未执行 |
| 12 | Missing Part | Unit/validator fail closed；真实 GUI PENDING |
| 13 | Corrupt Part | SHA fail-closed tests；真实 GUI PENDING |
| 14 | Cancel | Implementation/test coverage；真实大包 PENDING |
| 15 | Disk Preflight | Implementation coverage；低磁盘真实环境 PENDING |
| 16 | Atomic Activation | Implementation/test coverage；真实大包 PENDING |
| 17 | Deep Review | Packaged VLM PASS；clean GUI PENDING |
| 18 | Routing-triggered VLM | Core+VLM integration PASS；clean GUI PENDING |
| 19 | VLM Init Count | PASS：3 requests，同一 PID，init count 1 |
| 20 | Window Close | PENDING MANUAL |
| 21 | Orphan Process | 自动化 shutdown PASS；真实窗口 PENDING |
| 22 | Reopen | PENDING MANUAL |
| 23 | Advanced AI Uninstall | PENDING MANUAL |
| 24 | Advanced AI Reinstall | PENDING MANUAL |
| 25 | Runtime Upgrade | PENDING MANUAL |
| 26 | Model Upgrade | PENDING MANUAL |
| 27 | Rollback | PENDING MANUAL |
| 28 | Desktop Upgrade | PENDING MANUAL |
| 29 | Desktop Uninstall | PENDING MANUAL |
| 30 | Desktop Reinstall | PENDING MANUAL |
| 31 | Offline Core | Previous packaged smoke only；真正断网 PENDING |
| 32 | Offline Advanced AI | Offline-mode packaged VLM PASS；真正断网 PENDING |
| 33 | Historical Regression | FAIL / incomplete：1 still failing，1 not evaluable |
| 34 | Legacy Retirement Verdict | Reference Only；不是 Safe To Retire |
| 35 | Detector License | BLOCKED / Unclear |
| 36 | Qwen License | Apache-2.0 upstream；bundle revision/license evidence BLOCKED |
| 37 | Paddle License | Apache-2.0 source；model asset evidence BLOCKED |
| 38 | ONNX Runtime License | MIT；notice required，PARTIAL |
| 39 | PyTorch License | BSD-style + third parties，PARTIAL |
| 40 | CUDA/cuDNN Audit | 19 NVIDIA candidates identified；legal mapping BLOCKED |
| 41 | Final SBOM | 5 CycloneDX files generated and checksummed |
| 42 | THIRD_PARTY_NOTICES | Updated；final legal closure still blocked |
| 43 | Signing Decision | Unsigned RC allowed with disclosure；not an RC blocker |
| 44 | Asset Hosting Strategy | GitHub Release + 1 GiB parts |
| 45 | Asset Count | 22 total；11 binary/model assets + 11 metadata assets |
| 46 | Release Manifest | schema v3 generated and checksummed |
| 47 | SHA256 | 21 non-checksum files covered by `SHA256SUMS.txt` |
| 48 | RC Validator | FAIL EXPECTED |
| 49 | Remaining Blockers | clean machine、GUI lifecycle/offline、regression、detector/model/native license |
| 50 | Known Non-blocking Limitations | unsigned、manual 8.191 GiB import、only RTX 4060 Laptop validated |
| 51 | Recommended Commit Message | `chore(release): strengthen v1.0 RC acceptance evidence` |
| 52 | Versioning Recommendation | Commit/push branch Yes；RC Tag/Pre-release/Stable No |

## Measured packaged runtime evidence

- VLM process start: 882 ms.
- First VLM review: 13.138 s；model load 9.117 s.
- Subsequent reviews: 3.547 s and 3.614 s.
- Stable PID: yes；model init count: 1.
- GPU memory observed: 755 MiB idle，5369 MiB loaded.
- Core+VLM review: completed / low / VLM success.
- After forced VLM crash: Core PID unchanged；partial / medium / manual review；no unsafe low.

## Quality Gate

- Python: 175 passed；Ruff check / format check / compileall PASS（2 个 upstream deprecation warnings）。
- Frontend: 46 passed；ESLint、TypeScript build 和 Vite production build PASS。
- Rust: 21 passed（10 unit + 11 integration）；fmt / check PASS。
- Packaging: 22-file local candidate rebuilt；all 9 parts and combined archives verified；Local Validator PASS。
- Repository: `git diff --check`、secret/private-path scan、release binary scan and tracked-large-file scan PASS at handoff time.

## User Action Required

Use the checklist in `docs/clean_machine_acceptance.md` on an independent Windows environment and return the completed, redacted evidence. Separately choose a detector distribution path and obtain a competent review of the frozen NVIDIA/model assets. Only then rebuild the candidate and rerun `python scripts/validate_release.py --rc`.

## Versioning Recommendation

Commit:  
Yes

Recommended commit message:  
`chore(release): strengthen v1.0 RC acceptance evidence`

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

- Clean-machine and true-offline acceptance unavailable.
- Real Advanced AI GUI lifecycle acceptance incomplete.
- Historical hard case still fails near-boundary classification and coverage is insufficient.
- Detector/model provenance and NVIDIA native redistribution are unresolved.

Known non-blocking limitations:

- Unsigned candidate with possible SmartScreen warning.
- Manual Advanced AI download/import of approximately 8.191 GiB.
- Hardware validation currently limited to RTX 4060 Laptop 8 GiB.

Next Release Gate:  
Complete and return clean-machine evidence, resolve distribution licensing/native audit, expand and pass historical regression, rebuild unchanged final assets, then require `validate_release.py --rc` to pass without override.
