# Historical Regression Record

候选版本：`1.0.0-rc.1`  
审计日期：2026-09-25  
结论：**PENDING；Legacy Full Runtime 继续为 Reference Only。**

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

## Required scenario coverage

The automated suite covers safe/risky contracts, no text, low-confidence and ambiguous routing signals, evidence conflict, high detector risk, prompt-injection resistance, fast/VLM paths, missing/failed VLM, fusion boundaries and partial results. However, this coverage is distributed across mocks, structured-signal tests and a very small real-image set. It is not a statistically meaningful model-quality dataset.

## Classification

| Evidence class | Result |
|---|---|
| Source-level behavioral contracts | Equivalent / PASS |
| Packaged Core and VLM smoke | Equivalent on the development machine |
| One eligible verified hard case | Available for execution, insufficient alone |
| Full Legacy vs componentized comparison | Not Comparable：Legacy generated runtime is intentionally absent |
| Clean-machine componentized replay | Not executed |

## 2026-09-25 live hard-case execution

The existing manifest was executed with real YOLO, PaddleOCR, baseline and local Qwen inference on the development machine:

- Total records: 2.
- Not evaluable: 1 (`eligible_for_regression=false`).
- Still failing: 1.
- The eligible risky sample remained correctly classified `high` with `sensitive_text`, invoked the VLM successfully and required manual review, but its fusion score was `0.700001`, so the recorded `near_decision_boundary` failure remains present.
- No new failure was observed, but the historical failure is not fixed.

The raw execution artifact is intentionally Git-ignored because it contains development-machine paths. This summarized record contains no private absolute path.

No ground truth was changed to obtain these results.

## Remaining evidence required

1. Curate verified, redistribution-safe images for every required scenario rather than duplicating the current three VLM samples.
2. Execute them through the packaged Core + VLM services and retain structured result fields: risk, categories, route, manual review, VLM status, fusion score and module status.
3. Classify every difference as Equivalent, Expected Difference, Potential Regression, Confirmed Regression or Not Comparable.
4. Repeat the packaged run on the clean acceptance machine.

Until this matrix exists with no critical confirmed regression, Historical Regression cannot become PASS and Legacy source cannot be marked Safe To Retire.
