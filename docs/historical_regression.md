# Historical Regression Record

候选版本：`1.0.0-rc.1`  
审计更新：2026-10-03
结论：**BLOCKED（开发机真实图像回放发现 17 个确认回归）；Legacy Full Runtime 继续为 Reference Only。**

## 2026-10-03 verified real-image replay

已建立 27 张经人工核验、许可可追溯的 Wikimedia Commons 真实图片集。锁定清单位于 `data/regression/real_image_manifest.jsonl`，记录来源页面、修订号、许可证、作者、Commons SHA-1、本地 SHA-256、尺寸及人工 ground truth；图片二进制保留在验收目录，不进入 Git。

数据集覆盖 safe publishing、multilingual text、QR code、weapon、violence、blood、prohibited symbol 和 watermark。27/27 标注已核验，所有文件哈希验证通过。

使用打包 Core Runtime 与 Gate 3 托管本地 GPU VLM 在开发验收机回放，结果为：

- Equivalent：9
- Expected Difference：1
- Potential Regression：0
- Confirmed Regression：17
- 总耗时：434.905 秒

17 个确认回归均涉及非低风险 ground truth 被输出为 `low` 或丢失必要人工复核。其中 7 个错误进入 fast path，10 个虽调用 VLM 仍未保住安全结果。失败分布：QR code 3、weapon 4、violence 4、blood 2、prohibited symbol 2、watermark 2。

这批结果是模型/路由质量基线，不允许通过修改 ground truth、放宽 Gate 或把测试素材标为 synthetic 来规避。完整无私人路径的结构化结果保存在 `release-evidence/historical-real-image-regression.json`。

## Evidence inventory

| Historical source | Current evidence | Status |
|---|---|---|
| Phase 6 VLM | VLM schema/provider/prompt-injection tests and `data/vlm_eval` | Automated contract coverage only |
| Phase 7 pipeline | Pipeline unit/integration tests | PASS in source test suite |
| Phase 8 routing | Routing policy/evaluator tests | PASS in source test suite |
| Phase 9 fusion | Boundary/conflict/missing-module tests | PASS in source test suite |
| Phase 11 hard cases | `data/hard_cases/manifest.jsonl` | 2 records；only 1 eligible for live regression |
| Phase 12 API | API tests and packaged Core smoke | PASS on development machine |
| Phase 17 deployment | Core model/runtime manifests and smoke evidence | PASS on development machine |
| Phase 18 component integration | Packaged Core + VLM smoke and crash isolation | Previously PASS on development machine |

## Fixed contract suite

`data/regression/contract_manifest.jsonl` 固定了 16 个行为合同，覆盖 safe、risky、no text、OCR low confidence、baseline ambiguous、detector high risk、evidence conflict、prompt injection、fast path、VLM route、no VLM、VLM failure、partial result、fusion boundary、routing boundary 和 structured-output recovery。2026-09-25 使用项目虚拟环境逐项运行结果为 **16 PASS / 0 confirmed regression**。

这 16 项是 source-level behavioral contracts。它们不能替代真实图像模型质量集，也不能把 clean-machine replay 标为 PASS。

## Classification

| Evidence class | Result |
|---|---|
| Source-level behavioral contracts | PASS（16/16） |
| Packaged Core and VLM smoke | Equivalent on the development machine |
| One eligible verified hard case | Available for execution, insufficient alone |
| Full Legacy vs componentized comparison | Not Comparable：Legacy generated runtime is intentionally absent |
| Development-machine real-image packaged replay | BLOCKED：27 cases，17 confirmed regressions |
| Clean-machine componentized replay | Not executed；must wait for remediation |

原有 2 个 hard-case fixture 仍属于诊断材料，不计入新的真实图片集。当前真实世界来源并具备可验证再分发许可与人工标注的图片数量为 **27**；synthetic/smoke 图片仍不计入 real-image coverage。

## 2026-09-25 live hard-case execution

The existing manifest was executed with real YOLO, PaddleOCR, baseline and local Qwen inference on the development machine:

- Total records: 2.
- Not evaluable: 1 (`eligible_for_regression=false`).
- Diagnostic flag present: 1.
- The eligible risky sample remained correctly classified `high` with `sensitive_text`, routed to VLM, completed VLM successfully and required manual review. Fusion score was `0.700001`, only `0.000001` above the configured high-risk boundary.
- Replay evidence records `changed=false` / `comparison=unchanged`; there was no unsafe low, wrong fast path, lost manual review or risk downgrade.
- Classification: **DIAGNOSTIC_ONLY**, not `CONFIRMED_REGRESSION`. The diagnostic correctly identifies a fragile boundary even though the safety outcome is correct.

The raw execution artifact is intentionally Git-ignored because it contains development-machine paths. This summarized record contains no private absolute path.

No ground truth was changed to obtain these results.

## Remaining evidence required

1. Remediate the 17 confirmed regressions, prioritizing the 7 wrong fast-path decisions and the 10 unsafe post-VLM decisions.
2. Rebuild the packaged Core candidate and replay the unchanged locked 27-image manifest.
3. Review every changed result without modifying ground truth to fit model output.
4. After zero confirmed and zero unresolved potential regressions on the development replay, repeat on the clean acceptance machine.

Until the unchanged real-image matrix has zero confirmed/unresolved potential regressions and passes on the clean acceptance machine, Historical Regression remains `BLOCKED` and Legacy source cannot be marked Safe To Retire.
