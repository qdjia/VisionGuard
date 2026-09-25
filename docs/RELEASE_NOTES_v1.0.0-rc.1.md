# VisionGuard 1.0.0-rc.1 — Draft Release Notes

Status: **Draft / Release Candidate preparation only. Do not publish yet.**

VisionGuard is a local-first multimodal publishing-content review project. The Core installer provides detector, OCR, text baseline, routing and fusion. Advanced AI is an optional local import containing the VLM Runtime and Qwen3-VL model files.

## Candidate layout

- Core users download only `VisionGuard-Setup-1.0.0-rc.1.exe`.
- Advanced AI users additionally download `advanced-ai-manifest.json` and all 9 `.partNN` files.
- Users select the manifest in VisionGuard; they do not manually concatenate parts.
- SHA-256 verification is required before use.

## Measured size

- Core installer: approximately 506.4 MiB.
- Core installed footprint: approximately 0.843 GiB.
- Advanced AI download: approximately 8.191 GiB.
- Additional Advanced AI installation space: approximately 9.009 GiB.
- Peak with downloaded parts retained: approximately 17.2 GiB.

## Validated configuration

Development validation used Windows x86-64 and an NVIDIA RTX 4060 Laptop GPU with 8 GiB VRAM. This is a validated configuration, not a claimed minimum requirement or broad hardware certification.

## Candidate limitations

- The installer is unsigned and may trigger Windows SmartScreen warnings.
- Advanced AI download/import is manual; an online downloader is not part of this candidate.
- Broad GPU compatibility has not been established.
- Clean-machine, offline, upgrade and uninstall acceptance are still pending.
- Detector redistribution and one native NVIDIA DLL mapping remain unresolved; therefore these notes remain a draft and no disputed assets may be uploaded.

## Blocking issues

- Detector redistribution path remains `UNCLEAR`.
- `nvJitLink_120_0.dll` does not yet have an exact-name redistribution mapping accepted for this candidate.
- Real-image historical coverage and clean-machine replay are incomplete.
- Clean Windows, true offline and real GUI lifecycle acceptance are incomplete.

This Release Candidate is not production certification.
