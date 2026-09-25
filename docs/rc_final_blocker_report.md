# VisionGuard RC Final Blocker Closure Report

日期：2026-09-26

目标：`v1.0.0-rc.1`

最终状态：**RC BLOCKED**

本轮只处理最终发布阻塞，没有新增产品功能，没有降低 Gate，没有重建 Candidate，也没有创建 Tag 或 Release。

## Four-blocker result

| Blocker | Result | Evidence | Minimum closure action |
|---|---|---|---|
| Detector distribution | `NOT_ALLOWED` for current MIT RC | `release-evidence/detector-provenance.json` | 实施合格 AGPL 路径、提供适用商业许可，或由用户选择不分发/替换方案 |
| `nvJitLink_120_0.dll` | `UNCLEAR` | `release-evidence/nvjitlink-analysis.json` | 许可方书面澄清或合格法律审查确认 filename variation |
| Clean Windows / offline / GUI | `BLOCKED` | `release-evidence/acceptance-status.json` | 独立 Windows 完成 22 项真实验收 |
| Historical real-image regression | `BLOCKED` | `release-evidence/historical-regression.json` | 建立可再分发的 20–50 real-world image set 并在 packaged/clean machine 回放 |

## Detector release alternatives and impact analysis

| Option | Development effort | Data need | Regression impact | Performance risk | Release impact |
|---|---|---|---|---|---|
| A. Public RC 不包含 detector weights | Medium | 无新增训练数据 | 必须验证 detector unavailable fail-safe、routing 和 manual review | 视觉目标召回下降 | 可绕开权重分发，但产品能力降级必须明确披露 |
| B. 用户自行导入 detector | Medium–High | 用户提供兼容权重 | 新增导入兼容、hash/schema、失败路径回归 | 权重质量与性能不可控 | 应用不分发权重；仍需审查运行方式与文档 |
| C. 替换为许可明确的 detector base | High | 需要合法训练/验证数据 | Detector、routing、fusion、benchmark 全量重做 | 精度、延迟、导出兼容均可能变化 | 建立新许可链后才可评估发行 |
| D. 从许可链清晰的 base 重新训练 | High | 代表性标注数据和数据许可证 | 同 C，并需重新形成训练证据 | 高 | 周期最长但 provenance 最清晰 |
| E. 获取 Ultralytics 商业许可 | External / Low code | 无 | 验证许可覆盖当前 artifacts；模型行为通常无需改变 | 低 | 最少技术改动，但需要合同证据 |
| F. 实施 AGPL-3.0 合规发行 | High legal/release impact | 无 | 代码行为不一定改变 | 低 | 可能改变整个项目发行与源码义务，必须由项目所有者和合格审查方决定 |

本轮不自动选择任何方案，也不自动换模型。

## Required 38-point final report

| # | Item | Result |
|---:|---|---|
| 1 | Final RC Status | **RC BLOCKED** |
| 2 | Detector License Status | Current MIT RC=`NOT_ALLOWED` |
| 3 | Detector Release Path | 未选择；A–F 影响见上表 |
| 4 | nvJitLink Source | `torch` wheel `2.11.0+cu128`；RECORD 精确映射 |
| 5 | nvJitLink Redistribution Status | `UNCLEAR`；Attachment A=`libnvJitLink.dll`，官方 Windows guide=`nvJitLink.dll` |
| 6 | nvJitLink Removal Test | 未做 package removal；隔离 loader probe：缺少 DLL 时 cusparse 加载失败，加入后成功 |
| 7 | NVIDIA Final Native Audit | 20 instances / 19 unique；18 unique conditional；1 unclear |
| 8 | Clean Windows Environment | 不可用；当前开发机不合格 |
| 9 | Clean Install Result | NOT EXECUTED / BLOCKED |
| 10 | Shortcut / Start Menu | NOT EXECUTED / BLOCKED |
| 11 | Single Instance | Clean-machine GUI 未执行 |
| 12 | Core Ready | 开发机 smoke 曾通过；clean-machine BLOCKED |
| 13 | Fast Review | 开发机 smoke 曾通过；clean-machine BLOCKED |
| 14 | No-VLM Fail-safe | 自动化已有覆盖；真实 GUI clean-machine BLOCKED |
| 15 | Advanced AI Real Install | 真实分卷存在；clean GUI import BLOCKED |
| 16 | Deep Review | 开发机 packaged smoke 曾通过；clean GUI BLOCKED |
| 17 | Routing-triggered VLM | 自动化已有覆盖；clean GUI BLOCKED |
| 18 | Real Offline Result | NOT EXECUTED；offline env 不视为真断网 |
| 19 | GUI Lifecycle Result | NOT EXECUTED / BLOCKED |
| 20 | Window Close / No Orphan | 真实 X-close 未执行 |
| 21 | Upgrade | NOT EXECUTED / BLOCKED |
| 22 | Rollback | NOT EXECUTED / BLOCKED；现已加入 strict Gate |
| 23 | Uninstall | NOT EXECUTED / BLOCKED |
| 24 | Reinstall | NOT EXECUTED / BLOCKED；现已加入 strict Gate |
| 25 | Historical Real-image Count | 0 个具备可证明 real-world provenance；另有 2 个 historical fixture、1 eligible |
| 26 | Regression Coverage | 16/16 source contracts；real-image coverage insufficient |
| 27 | Near-boundary Verdict | `DIAGNOSTIC_ONLY`；距 high threshold `0.000001`；无安全降级 |
| 28 | Confirmed Regression Count | 0（现有证据范围内） |
| 29 | Legacy Runtime Verdict | Reference Only；未删除 |
| 30 | Final SBOM | 未刷新；四 blocker 未关闭，因此未允许 final rebuild |
| 31 | Final Asset Count | 未重新计算；旧候选为 11 binary/model assets、22 total files |
| 32 | Max Asset Size | 旧候选 1,073,741,824 bytes；final 尚不存在 |
| 33 | Release Manifest | 旧 candidate schema v3；build template 新增 rollback/reinstall Gate |
| 34 | SHA256 Status | Evidence 自身已固定；final candidate hashes 未生成 |
| 35 | Strict RC Validator Result | FAIL CLOSED；新增 machine-readable blocker evidence 检查 |
| 36 | Remaining Blockers | Detector、nvJitLink、independent Windows acceptance、real-image regression、final rebuild |
| 37 | User Action Required | 见下一节 |
| 38 | Versioning Recommendation | Commit/push normal branch Yes；RC Tag/Pre-release/Stable No |

## Quality gate evidence

- Python: 185 tests passed；2 upstream deprecation warnings；Ruff、format check and compileall passed.
- Behavior contracts: 16/16 `PASS`.
- Frontend: 46 tests passed；ESLint、TypeScript and production Vite build passed.
- Rust: 21 tests passed；`cargo fmt --check` and `cargo check` passed；one non-blocking MSVC linker message warning.
- `nvJitLink` isolated dependency probe: cusparse load failed without the DLL and passed with the DLL; the temporary probe directory was removed.
- Existing candidate local integrity validator: PASS.
- Strict validator against the old candidate: failed closed and reported rollback/reinstall plus all existing unresolved gates. The old candidate predates the new evidence files and is not a final rebuilt candidate.
- Final release build: intentionally not executed because the four blocker classes are not closed.

## User Action Required

### Action 1 — Select the detector distribution path

Why: 当前 MIT RC 分发 Ultralytics trained/fine-tuned detector 不满足已记录的 AGPL 或 Enterprise 路径。

Exact Steps:

1. 在上方 A–F 中选择路径。
2. 若选 E，提供覆盖当前项目、fine-tuned weight 和 ONNX 分发的许可证明。
3. 若选 F，让合格审查方确认完整 AGPL obligations 并批准项目许可变更。
4. 若选 A–D，先批准单独的 impact/retraining 工作，不在本 Closure 中自动执行。

Evidence Needed: 书面路径决定、适用许可或合规审查记录。

Blocks RC: **Yes**。

### Action 2 — Obtain nvJitLink clarification

Why: NVIDIA Attachment A 与官方 Windows nvJitLink guide 使用不同的基础文件名；该 DLL 又是 cusparse 的静态依赖，不能安全直接删除。

Exact Steps:

1. 将 `release-evidence/nvjitlink-analysis.json` 提交给 NVIDIA license contact 或合格审查方。
2. 请求确认 `nvJitLink_120_0.dll` 是否属于允许再分发的 Windows filename variation。
3. 保留书面答复及适用版本条款。

Evidence Needed: 许可方书面答复或合格法律意见。

Blocks RC: **Yes**。

### Action 3 — Provide an independent Windows environment

Why: 开发机不能关闭 clean install、真断网和 GUI 生命周期 Gate。

Exact Steps: 按 `docs/clean_machine_acceptance.md` 的 22 行模板执行并返回脱敏证据。

Evidence Needed: 环境信息、最终候选哈希、截图编号、进程/端口/GPU 输出和日志摘要。

Blocks RC: **Yes**。

### Action 4 — Provide redistribution-safe real images

Why: synthetic fixtures 不能被计为 real-image coverage。

Exact Steps:

1. 确认可再分发、无私人敏感内容的 20–50 张真实图片。
2. 补齐 case metadata 和 Ground Truth 状态。
3. 在 packaged runtime 与 clean machine 回放。

Evidence Needed: 来源/许可、固定 hashes、期望行为、actual results 和 drift classification。

Blocks RC: **Yes**。

## Versioning Recommendation

Commit:
Yes

Recommended commit message:
`chore(release): document final v1.0 RC blockers`

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

- Detector is `NOT_ALLOWED` under the current MIT RC path.
- `nvJitLink_120_0.dll` remains `UNCLEAR` and is a required binary dependency.
- Independent Windows, true-offline and GUI lifecycle acceptance are not executed.
- Verified real-world image coverage is zero.
- No final rebuilt candidate exists and strict RC validation cannot pass.

Known non-blocking limitations:

- Unsigned RC may trigger Windows SmartScreen.
- Advanced AI remains a large manual multipart import.
- Hardware validation remains limited to the recorded RTX 4060 Laptop configuration.

Next Release Gate:
Obtain the two external license decisions, complete independent Windows and real-image evidence, rebuild every candidate asset with refreshed SBOM/hashes/manifest/evidence, then require `python scripts/validate_release.py --rc` to PASS without bypass.
