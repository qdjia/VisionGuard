# Design Decisions

These decisions describe the implemented system. They are engineering trade-offs rather than
claims that the chosen approach is universally optimal.

## 1. Provider abstraction for OCR and VLM

- **Problem:** Model SDKs differ in initialization, inputs, outputs, and error behavior.
- **Decision:** Expose narrow provider/adapter contracts and keep concrete backends behind factories.
- **Reason:** Pipeline and API code can consume stable schemas without importing PaddleOCR or a
  specific VLM architecture.
- **Trade-off:** Each new backend still needs an explicit adapter and compatibility tests.

## 2. Pydantic structured output

- **Problem:** Free-form model text is unsafe as an internal program contract.
- **Decision:** Validate moderation, routing, fusion, pipeline, artifact, and API results with strict
  Pydantic schemas.
- **Reason:** Required fields, ranges, enums, and unknown-field rejection make failures observable.
- **Trade-off:** Legitimate but malformed generations are rejected or retried instead of being
  guessed into a result.

## 3. OCR and image text are untrusted input

- **Problem:** Text inside an image can contain instructions aimed at the VLM rather than content to
  classify.
- **Decision:** Delimit and escape OCR content, label it as untrusted evidence, and keep moderation
  policy outside the image-derived context.
- **Reason:** This reduces accidental instruction/data confusion and supports a tested conflict case.
- **Trade-off:** It is not a complete prompt-injection defense; adversarial evaluation remains small.

## 4. Cascaded inference

- **Problem:** The local VLM dominates latency and does not need to inspect every obvious case.
- **Decision:** Run Detector + OCR + Baseline first, then call the VLM only when routing signals need
  semantic resolution.
- **Reason:** A three-sample engineering validation observed a lower VLM call rate and lower mean
  latency while retaining the tested safety behavior.
- **Trade-off:** The current router is rule-based and requires a much larger annotated set before its
  thresholds can be considered reliable.

## 5. Conservative fast path

- **Problem:** An aggressive fast path can turn routing mistakes into unsafe low-risk decisions.
- **Decision:** Require high-confidence low-risk agreement and apply a pre-fusion safety guard.
- **Reason:** Failures, conflicts, insufficient evidence, and non-low Stage 1 fusion cannot silently
  pass as low risk.
- **Trade-off:** More ambiguous cases invoke the expensive VLM or require manual review.

## 6. Routing and fusion remain separate

- **Problem:** Combining cost-control logic with the final risk decision makes behavior difficult to
  explain and replay.
- **Decision:** Routing decides whether to call the VLM; fusion decides the final result.
- **Reason:** Each policy has a separate version, schema, evaluator, reason codes, and replay path.
- **Trade-off:** The pipeline has an extra boundary and must preserve all signals consistently.

## 7. Weighted explainable fusion

- **Problem:** A single model can be wrong, unavailable, or contradicted by another modality.
- **Decision:** Use configured severity mappings, normalized available-source weights, explicit
  conflict rules, and evidence provenance.
- **Reason:** Decisions can be inspected, ablated, swept, and replayed without rerunning models.
- **Trade-off:** The weights are expert rules, not learned or calibrated estimates.

## 8. Offline replay

- **Problem:** Re-running YOLO, OCR, and especially the VLM is slow and introduces generation noise.
- **Decision:** Save structured live-evaluation records and replay routing/fusion policies offline.
- **Reason:** Strategy comparisons, threshold sweeps, and failure analysis become fast and
  reproducible; replay metadata states `models_executed=false`.
- **Trade-off:** Replay cannot reveal behavior that would require new upstream model outputs.

## 9. Benchmark before optimization

- **Problem:** Optimizing a visually prominent component may not improve end-to-end performance.
- **Decision:** Measure cold start, steady-state latency, percentiles, throughput, module share, and
  GPU memory before selecting optimization work.
- **Reason:** The recorded Phase 10 smoke identified the VLM—not Fusion or Baseline—as the dominant
  latency source and showed that sequential batch 2 did not improve throughput.
- **Trade-off:** The current smoke has one measured run per condition and cannot support broad
  performance claims.

## 10. Single-GPU bounded API concurrency

- **Problem:** Concurrent VLM requests can duplicate memory pressure, trigger OOM, and exercise
  components whose thread safety has not been established.
- **Decision:** Use one application process and an `asyncio.Semaphore`, defaulting to one full
  inference at a time; synchronous work runs in a worker thread.
- **Reason:** The event loop stays responsive while model access remains bounded and predictable.
- **Trade-off:** Requests may queue, and `queue_wait_ms` can dominate under load. This is not a
  dynamic batching server.

## 11. API timeout is not hard GPU cancellation

- **Problem:** An HTTP timeout cannot safely terminate an already-running CUDA kernel or Python
  model call.
- **Decision:** Return a structured timeout, keep the semaphore held until background inference
  naturally finishes, and document the distinction.
- **Reason:** It avoids falsely claiming cancellation or allowing overlapping GPU work after timeout.
- **Trade-off:** Capacity can remain occupied after the client has received HTTP 504.

## 12. Partial results use HTTP 200

- **Problem:** A module can fail while the system still produces an explicit conservative result and
  manual-review requirement.
- **Decision:** Return HTTP 200 for a successfully handled `partial` review; reserve 5xx for service or
  pipeline execution failure.
- **Reason:** Transport success and moderation completeness are different concepts.
- **Trade-off:** Clients must inspect `status`, module states, and `requires_manual_review`.

## 13. Artifacts are reproducible but private by default

- **Problem:** Debugging needs structured evidence, but uploaded images and local paths may be
  sensitive.
- **Decision:** Save versioned structured artifacts, disable input copies by default, return only an
  artifact ID over HTTP, and ignore runtime artifacts in Git.
- **Reason:** Runs remain traceable without making raw user content a default repository asset.
- **Trade-off:** Exact visual reproduction may require an explicitly retained input outside Git.

