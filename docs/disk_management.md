# Disk Management Policy

## Directory classes

| Class | Examples | Policy |
|---|---|---|
| Source and contract | `src/`, `desktop/src/`, `desktop/src-tauri/src/`, `tests/`, `scripts/`, `configs/`, `packaging/` | Keep and track |
| Release evidence | `release-evidence/`, selected small `artifacts/` reports, SBOM configuration | Keep; do not delete by age alone |
| Active local models | `models/core-models-v1/`, one validated VLM fallback | Keep one verified copy plus provenance |
| Rebuildable output | `runtime-build*/`, `runtime-dist-vlm/`, `desktop/src-tauri/target/`, `desktop/dist/`, `build/` | Ignore; delete after validation |
| Download/cache | `.test-tmp/`, `.build-tmp/`, project HF/Paddle caches | Ignore; delete after successful activation or failed experiment review |
| Release output | `release/`, split assets, generated installer, generated wheel | Ignore; delete after upload/acceptance or when superseded |

## Routine cleanup

After a development cycle:

1. Confirm `git status` and preserve all tracked changes.
2. Confirm no VisionGuard/Core/VLM/bootstrap process uses the target directories.
3. Remove Python caches and test staging.
4. Remove frontend `dist`; remove `node_modules` only when reinstall time is acceptable.
5. Remove Rust `target` after installer/test evidence has been copied to the small evidence location.
6. Remove PyInstaller work directories and superseded runtime distributions.
7. Remove local Release assets after upload or after the candidate is superseded.
8. Keep only one validated copy of each large model, plus hashes and provenance records.
9. Rescan size and run Git integrity checks.

## Model policy

- Keep `models/core-models-v1` while it is the default release input.
- Until online bootstrap completes a full fresh-cache acceptance run, keep exactly one validated
  `models/vlm-models-v1` fallback.
- Never remove a model referenced by an active registry, manifest or release process.
- Before deleting duplicates over 100 MiB, require matching SHA-256, not just filename or size.
- Preserve the detector base checkpoint, fine-tuned provenance checkpoint, exported model hash and training metadata.

## Release policy

- Generated RC directories are temporary local products, not long-term project storage.
- Default online-bootstrap candidates must not contain Qwen weights, external wheels, CUDA/NVIDIA DLLs or old split assets.
- Retain release manifests, SBOM generation sources, license evidence and acceptance summaries in Git.
- Rebuild final assets from a clean commit; do not reuse an old staging tree as a source of truth.

## Restore commands

```powershell
# Frontend dependencies and output
cd desktop
npm ci
npm run build

# Rust/Tauri cache
cd src-tauri
cargo build

# Core runtime
cd ../..
python scripts/build_runtime.py --profile core

# Legacy VLM runtime, only for an explicit fallback investigation
python scripts/build_runtime.py --profile vlm

# Current default release candidate
python scripts/build_release.py --version <version>
```

Do not run restore commands immediately after cleanup merely to prove they exist; that recreates the deleted disk
usage. Use lightweight source, manifest and metadata checks until a real build is required.

## Safety rules

- Never use `git clean -xfd`, recursive deletion at repository root, broad globs or unresolved environment variables.
- Resolve every deletion target and confirm it remains inside the project root.
- Do not traverse or delete symlink/junction targets.
- Treat access-denied directories, unknown environments and unique model/checkpoint copies as `REVIEW_REQUIRED`.
- Do not modify ACLs or kill unrelated processes solely to make cleanup succeed.
- Do not clean user-global Hugging Face, pip, Conda, npm or Cargo caches as part of project cleanup.

