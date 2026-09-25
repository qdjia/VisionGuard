# Historical Regression Record

候选版本：`1.0.0-rc.1`  
审计更新：2026-09-26
结论：**BLOCKED（真实图像覆盖不足）；Legacy Full Runtime 继续为 Reference Only。**

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
| Clean-machine componentized replay | Not executed |

这里的 2 个图片 case 是历史 fixture 数量，不等同于真实世界数据集。当前能够证明真实世界来源并可安全再分发的图片数量为 **0**；synthetic/smoke 图片不计入 real-image coverage。

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

1. Curate 20–50 verified, redistribution-safe real-world images across the required scenarios rather than treating the 16 contracts or synthetic fixtures as model-quality evidence. If fewer are available, record the actual count without inflating it.
2. Execute them through the packaged Core + VLM services and retain structured result fields: risk, categories, route, manual review, VLM status, fusion score and module status.
3. Classify every difference as Equivalent, Expected Difference, Potential Regression, Confirmed Regression or Not Comparable.
4. Repeat the packaged run on the clean acceptance machine.

Until the real-image matrix exists and is replayed on the clean acceptance machine with no confirmed regression, Historical Regression remains `BLOCKED` and Legacy source cannot be marked Safe To Retire.
