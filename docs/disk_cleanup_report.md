# Disk Cleanup Report

Cleanup date: 2026-09-27  
Scope: project workspace only; `.git` and user-global caches were excluded.

## Result

| Metric | Bytes | GiB |
|---|---:|---:|
| Project size before | 68,572,996,700 | 63.86 |
| Project size after | 5,215,848,526 | 4.86 |
| Total freed | 63,357,148,174 | 59.00 |
| Reduction | 92.39% | — |
| Available disk after cleanup | 303,834,877,952 | 282.97 |

Sizes exclude `.git`. The after-scan used read-only traversal and skipped ACL-protected directories.

## Deleted items

| Category | Relative path/content | Reason | Restore method |
|---|---|---|---|
| SAFE_DELETE | `.build-tmp/`, `.test-tmp/`, `.pytest_cache/`, `.ruff_cache/`, root pytest cache directories | Temporary build/test caches | Recreated automatically |
| SAFE_DELETE | project `__pycache__/`, `*.pyc`, `*.pyo`, `.coverage` | Python caches | Recreated automatically |
| SAFE_DELETE | `artifacts/huggingface_cache/` | Incomplete/re-downloadable official-source cache | Run Advanced AI bootstrap again |
| SAFE_DELETE | `artifacts/modelscope/` | Duplicate model download cache | Fetch from the pinned official source |
| SAFE_DELETE | `artifacts/paddlex_cache/` | Duplicate OCR download cache | Re-fetch models or use retained Core Models |
| SAFE_DELETE | `desktop/dist/` | Frontend build output | `npm run build` |
| REBUILDABLE_DELETE | `desktop/src-tauri/target/` | Rust/Tauri build and bundle cache | `cargo build` or Tauri build command |
| REBUILDABLE_DELETE | `desktop/src-tauri/binaries/` | Superseded full-runtime Tauri staging | Re-run the relevant runtime staging/build script |
| REBUILDABLE_DELETE | `desktop/node_modules/` | Lock-file reproducible dependencies | `npm ci` |
| REBUILDABLE_DELETE | `release/` | Superseded local RC and duplicate split assets | `python scripts/build_release.py ...` |
| REBUILDABLE_DELETE | `artifacts/advanced-ai-package-phase19/` | Duplicate legacy Advanced AI split package | Run the explicit bundled/fallback package build |
| REBUILDABLE_DELETE | `artifacts/phase18/` | Legacy VLM Runtime package audit ZIP | Rebuild legacy VLM Runtime and audit it |
| REBUILDABLE_DELETE | `runtime-build-core/`, `runtime-build-vlm/` | PyInstaller work directories | `python scripts/build_runtime.py --profile ...` |
| REBUILDABLE_DELETE | `runtime-dist-vlm/` | Legacy 4+ GiB VLM PyInstaller Runtime | `python scripts/build_runtime.py --profile vlm` |
| REBUILDABLE_DELETE | `models/models-v1/` | Superseded combined bundle; model and detector copies were duplicated elsewhere | `python scripts/build_model_bundle.py --hardlink` |
| REBUILDABLE_DELETE | `build/`, generated bootstrap wheel | Python package build output | Run the bootstrap wheel build/release builder |
| SAFE_DELETE | `weights/yolo26n.pt` | Exact SHA-256 duplicate of retained root `yolo26n.pt` | Copy the retained checkpoint if a legacy path is needed |

No Git-tracked source or evidence file was deleted by the disk cleanup operation. Tracked document removals are
the separate documentation consolidation described below.

## Kept items

- `runtime-dist-core/`: current validated Slim Core Runtime build input.
- `models/core-models-v1/`: current Core model bundle and manifest.
- `models/vlm-models-v1/`: the single local VLM fallback while a complete fresh online download remains blocked.
- `artifacts/experiments/.../weights/best.pt`: detector provenance checkpoint.
- `artifacts/phase17/`, regression, benchmark, error-analysis, SBOM and acceptance evidence.
- `yolo26n.pt`: the single base detector checkpoint.
- All source, tests, configuration, manifests, lock files, licenses, notices and build scripts.

## Review-required items

Seventeen `artifacts/pytest-*` directories report zero visible bytes but deny directory enumeration through their
ACL. They were not force-deleted, ownership was not changed, and no process was terminated. They are negligible
in the measured project size and may be removed manually only after their ACL and contents are independently
verified.

No project-local Python virtual environment was found. User-global Conda, pip, Hugging Face and Cargo caches were
outside scope and were not touched.

## Top directories before

| # | Path | Bytes | GiB |
|---:|---|---:|---:|
| 1 | `desktop/` | 25,832,386,099 | 24.058 |
| 2 | `artifacts/` | 18,821,940,690 | 17.529 |
| 3 | `release/` | 9,326,684,080 | 8.686 |
| 4 | `models/` | 8,852,273,717 | 8.244 |
| 5 | `runtime-dist-vlm/` | 4,527,251,608 | 4.216 |
| 6 | `runtime-dist-core/` | 748,419,793 | 0.697 |
| 7 | `runtime-build-vlm/` | 219,387,067 | 0.204 |
| 8 | `runtime-build-core/` | 162,620,488 | 0.151 |
| 9 | `.test-tmp/` | 65,564,881 | 0.061 |
| 10 | `yolo26n.pt` | 5,544,453 | 0.005 |
| 11 | `weights/` | 5,544,453 | 0.005 |
| 12 | `src/` | 1,408,321 | 0.001 |
| 13 | `tests/` | 1,341,117 | 0.001 |
| 14 | `scripts/` | 875,858 | 0.001 |
| 15 | `runs/` | 574,131 | 0.001 |
| 16 | `build/` | 489,004 | <0.001 |
| 17 | `docs/` | 243,447 | <0.001 |
| 18 | `bootstrap-dist/` | 184,825 | <0.001 |
| 19 | `data/` | 111,375 | <0.001 |
| 20 | `release-evidence/` | 53,347 | <0.001 |

## Top directories after

| # | Path | Bytes | GiB |
|---:|---|---:|---:|
| 1 | `models/` | 4,423,446,655 | 4.120 |
| 2 | `runtime-dist-core/` | 748,419,793 | 0.697 |
| 3 | `artifacts/` | 34,564,241 | 0.032 |
| 4 | `yolo26n.pt` | 5,544,453 | 0.005 |
| 5 | `desktop/` | 1,986,256 | 0.002 |
| 6 | `runs/` | 574,131 | 0.001 |
| 7 | `src/` | 524,576 | <0.001 |
| 8 | `scripts/` | 208,349 | <0.001 |
| 9 | `docs/` | 186,292 | <0.001 |
| 10 | `tests/` | 153,120 | <0.001 |
| 11 | `data/` | 111,375 | <0.001 |
| 12 | `release-evidence/` | 53,347 | <0.001 |
| 13 | `LICENSE` | 34,523 | <0.001 |
| 14 | `configs/` | 13,490 | <0.001 |
| 15 | `packaging/` | 11,851 | <0.001 |
| 16 | `README.md` | 6,872 | <0.001 |
| 17 | `THIRD_PARTY_NOTICES.md` | 2,036 | <0.001 |
| 18 | `.gitignore` | 2,029 | <0.001 |
| 19 | `pyproject.toml` | 1,518 | <0.001 |
| 20 | `prompts/` | 1,318 | <0.001 |

## Top 30 files before

| # | Size | Relative path |
|---:|---:|---|
| 1 | 4,255,140,312 | `artifacts/modelscope/Qwen3-VL-2B-Instruct/model.safetensors` |
| 2 | 4,255,140,312 | `models/vlm-models-v1/vlm/model.safetensors` |
| 3 | 4,255,140,312 | `models/models-v1/vlm/model.safetensors` |
| 4 | 2,861,409,521 | `artifacts/phase18/package-audit/VisionGuard-VLM-Runtime-0.1.0-windows-x64.zip` |
| 5 | 2,706,713,104 | `artifacts/huggingface_cache/.../blobs/7de1838c...` |
| 6 | 1,073,741,824 | `artifacts/advanced-ai-package-phase19/...Runtime...part04` |
| 7 | 1,073,741,824 | `artifacts/advanced-ai-package-phase19/...Runtime...part01` |
| 8 | 1,073,741,824 | `release/v1.0.0-rc.1/...Models...part03` |
| 9 | 1,073,741,824 | `release/v1.0.0-rc.1/...Models...part02` |
| 10 | 1,073,741,824 | `artifacts/advanced-ai-package-phase19/...Runtime...part03` |
| 11 | 1,073,741,824 | `release/v1.0.0-rc.1/...Models...part01` |
| 12 | 1,073,741,824 | `release/v1.0.0-rc.1/...Runtime...part01` |
| 13 | 1,073,741,824 | `release/v1.0.0-rc.1/...Runtime...part02` |
| 14 | 1,073,741,824 | `release/v1.0.0-rc.1/...Runtime...part04` |
| 15 | 1,073,741,824 | `release/v1.0.0-rc.1/...Runtime...part03` |
| 16 | 1,073,741,824 | `artifacts/advanced-ai-package-phase19/...Models...part03` |
| 17 | 1,073,741,824 | `artifacts/advanced-ai-package-phase19/...Models...part02` |
| 18 | 1,073,741,824 | `artifacts/advanced-ai-package-phase19/...Models...part01` |
| 19 | 1,073,741,824 | `artifacts/advanced-ai-package-phase19/...Runtime...part02` |
| 20 | 1,062,867,524 | `desktop/src-tauri/target/debug/deps/visionguard_desktop_lib.lib` |
| 21 | 1,045,419,613 | `release/v1.0.0-rc.1/...Models...part04` |
| 22 | 1,045,419,613 | `artifacts/advanced-ai-package-phase19/...Models...part04` |
| 23 | 1,032,260,884 | `desktop/src-tauri/target/debug/visionguard_desktop_lib.lib` |
| 24 | 811,561,984 | `desktop/src-tauri/binaries/_internal/torch/lib/torch_cuda.dll` |
| 25 | 811,561,984 | `runtime-dist-vlm/.../torch/lib/torch_cuda.dll` |
| 26 | 674,667,520 | `desktop/src-tauri/binaries/_internal/torch/lib/cublasLt64_12.dll` |
| 27 | 674,667,520 | `runtime-dist-vlm/.../torch/lib/cublasLt64_12.dll` |
| 28 | 531,009,419 | `desktop/src-tauri/target/release/bundle/nsis/VisionGuard_1.0.0_x64-setup.exe` |
| 29 | 531,009,419 | `release/v1.0.0-rc.1/VisionGuard-Setup-1.0.0-rc.1.exe` |
| 30 | 481,015,408 | `desktop/src-tauri/binaries/_internal/torch/lib/cudnn_engines_precompiled64_9.dll` |

## Duplicate audit

- Three identical 4,255,140,312-byte VLM weights were reduced to one retained fallback copy.
- RC and Phase 19 split assets were byte-for-byte duplicate groups and both generated copies were removed.
- Legacy Tauri VLM staging and `runtime-dist-vlm` shared identical CUDA/PyTorch binaries; both generated trees were removed.
- The duplicate base detector checkpoint under `weights/` was removed; root `yolo26n.pt` remains.
- The fine-tuned detector checkpoint and exported ONNX provenance evidence remain.

## Documentation consolidation

Seventeen superseded phase, RC, raw size-audit and fragmented operations documents were consolidated into:

- [`release_history.md`](release_history.md): architecture evolution, historical measurements and superseded conclusions.
- [`release_operations.md`](release_operations.md): clean-machine checklist, hardware boundary, signing, model licensing and asset policy.

Current architecture, release gate, licenses, evidence, experiment and reproducibility documents remain separate.

## 36-point outcome

1. Project Size Before: 68,572,996,700 bytes.
2. Project Size After: 5,215,848,526 bytes.
3. Total Freed: 63,357,148,174 bytes.
4. Reduction: 92.39%.
5. Top 20 Directories Before: recorded above.
6. Top 20 Directories After: recorded above.
7. Top 30 Files Before: recorded above.
8. SAFE_DELETE Items: removed except ACL-protected review items.
9. REBUILDABLE_DELETE Items: removed where rebuild evidence was clear.
10. KEEP Items: source, current Core, one VLM fallback, models, checkpoints and evidence retained.
11. REVIEW_REQUIRED Items: 17 ACL-protected zero-visible-byte pytest directories.
12. PyInstaller Cleanup: legacy VLM build/dist and Core work directory removed; current Core dist retained.
13. Release Cleanup: superseded local RC removed.
14. Advanced AI Split Cleanup: duplicate Phase 19 and RC split assets removed.
15. Rust Target Cleanup: removed.
16. Frontend Cleanup: `dist` removed.
17. Node Modules Decision: removed; restore with `npm ci`.
18. Python Env Audit: no project-local environment found.
19. Removed Environments: none.
20. Kept Environments: no project-local environment; external environments untouched.
21. Model Duplicate Audit: completed using size, manifest and SHA-256.
22. Deleted Model Copies: two duplicate VLM trees and one duplicate base checkpoint.
23. Kept Active Models: Core bundle, one VLM fallback, fine-tuned detector and base checkpoint.
24. HF Cache Decision: project-local incomplete cache removed; global cache untouched.
25. Logs Cleanup: no large standalone log set found; evidence logs retained.
26. Artifacts Cleanup: large caches/packages removed; small evidence retained.
27. Training Outputs: provenance checkpoint and experiment evidence retained.
28. Staging Cleanup: project build/test/bootstrap staging removed.
29. Duplicate Large Files: audited; generated duplicate groups removed.
30. Git Status: only intentional documentation changes remain.
31. Accidental Tracked Deletions: none from disk cleanup.
32. Restore Commands: recorded in the deleted-items table.
33. Current Largest Remaining Directory: `models/`, 4,423,446,655 bytes.
34. Current Largest Remaining File: VLM `model.safetensors`, 4,255,140,312 bytes.
35. Additional Manual Cleanup Opportunities: ACL-protected pytest directories after independent verification.
36. Recommended Future Disk Policy: maintained in [`disk_management.md`](disk_management.md).
