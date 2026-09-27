"""Rebuild Gate 1 Core Models from tracked fixtures and immutable official sources."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_CHECKPOINT = {
    "url": "https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26n.pt",
    "size_bytes": 5_544_453,
    "sha256": "9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef",
}
OCR_MODELS = {
    "ocr_detection": {
        "repo_id": "PaddlePaddle/PP-OCRv6_medium_det",
        "revision": "8e0f56fb2ef86b461d99cfc7ac5c137738985f61",
        "artifact": "inference.pdiparams",
        "sha256": "85218d2e3d98f5a21c58b4220627be923a97aee5db3cc71f39536ab31ac53960",
    },
    "ocr_recognition": {
        "repo_id": "PaddlePaddle/PP-OCRv6_medium_rec",
        "revision": "e5a92bcbc5cc1b494628e458d267778f0704fd7c",
        "artifact": "inference.pdiparams",
        "sha256": "1b01c79a914587933f615569e75de54f2e638ebb5d3f3b3c1b38c24ede8c7319",
    },
    "ocr_orientation": {
        "repo_id": "PaddlePaddle/PP-LCNet_x1_0_textline_ori",
        "revision": "cd237a44b0e359d4fe38310a416203cf7403faa5",
        "artifact": "inference.pdiparams",
        "sha256": "0de2bcf996cf553e2b848dd7b1769dafffc6917b1ccdf55c1d8efe7909fbf743",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_file(path: Path, *, expected_sha256: str, expected_size: int | None = None) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"required model artifact is missing: {path}")
    if expected_size is not None and path.stat().st_size != expected_size:
        raise RuntimeError(f"model artifact size mismatch: {path.name}")
    if sha256(path) != expected_sha256:
        raise RuntimeError(f"model artifact SHA-256 mismatch: {path.name}")


def download_base_checkpoint(target: Path) -> None:
    if target.is_file():
        verify_file(
            target,
            expected_sha256=str(BASE_CHECKPOINT["sha256"]),
            expected_size=int(BASE_CHECKPOINT["size_bytes"]),
        )
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(".partial")
    request = urllib.request.Request(
        str(BASE_CHECKPOINT["url"]), headers={"User-Agent": "VisionGuard-gate1/1"}
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as output:
            shutil.copyfileobj(response, output, length=1024 * 1024)
        verify_file(
            partial,
            expected_sha256=str(BASE_CHECKPOINT["sha256"]),
            expected_size=int(BASE_CHECKPOINT["size_bytes"]),
        )
        partial.replace(target)
    finally:
        partial.unlink(missing_ok=True)


def run(command: list[str]) -> None:
    print("+", subprocess.list2cmdline(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def fetch_ocr_models(work_root: Path) -> dict[str, Path]:
    from huggingface_hub import snapshot_download

    sources: dict[str, Path] = {}
    for role, spec in OCR_MODELS.items():
        snapshot = Path(
            snapshot_download(
                repo_id=str(spec["repo_id"]),
                revision=str(spec["revision"]),
                cache_dir=work_root / "huggingface",
            )
        ).resolve()
        verify_file(snapshot / str(spec["artifact"]), expected_sha256=str(spec["sha256"]))
        sources[role] = snapshot
    return sources


def ensure_clean_checkout_inputs() -> None:
    required = (
        ROOT / "data/visionguard_smoke/images/train/train_00.jpg",
        ROOT / "data/visionguard_smoke/labels/train/train_00.txt",
        ROOT / "data/text_moderation/sample/train.csv",
        ROOT / "configs/train_detector_smoke.yaml",
        ROOT / "configs/baseline_text.yaml",
    )
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"tracked Gate 1 build inputs are missing: {', '.join(missing)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "models/core-models-v1")
    parser.add_argument("--work-root", type=Path, default=ROOT / "artifacts/gate1-build")
    args = parser.parse_args(argv)
    output = args.output.resolve()
    work_root = args.work_root.resolve()
    if output.exists():
        raise FileExistsError(
            f"Gate 1 requires a fresh checkout; Core Models output already exists: {output}"
        )
    ensure_clean_checkout_inputs()
    work_root.mkdir(parents=True, exist_ok=True)
    checkpoint = ROOT / "yolo26n.pt"
    download_base_checkpoint(checkpoint)
    run(
        [
            sys.executable,
            "scripts/train_detector.py",
            "--config",
            "configs/train_detector_smoke.yaml",
            "--device",
            "cpu",
        ]
    )
    trained = ROOT / "artifacts/experiments/yolo26n_smoke_640/weights/best.pt"
    detector = work_root / "detector/model.onnx"
    run(
        [
            sys.executable,
            "scripts/export_detector_onnx.py",
            "--checkpoint",
            str(trained),
            "--output",
            str(detector),
            "--device",
            "cpu",
            "--batch",
            "1",
        ]
    )
    run(
        [sys.executable, "scripts/train_text_baseline.py", "--config", "configs/baseline_text.yaml"]
    )
    baseline = ROOT / "artifacts/baseline/char_2_4_gbdt_sample_v1"
    ocr = fetch_ocr_models(work_root)
    run(
        [
            sys.executable,
            "scripts/build_model_bundle.py",
            "--profile",
            "core",
            "--bundle-version",
            "core-models-v1",
            "--output",
            str(output),
            "--detector",
            str(detector),
            "--baseline",
            str(baseline),
            "--ocr-detection",
            str(ocr["ocr_detection"]),
            "--ocr-recognition",
            str(ocr["ocr_recognition"]),
            "--ocr-orientation",
            str(ocr["ocr_orientation"]),
        ]
    )
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    expected_roles = {"detector", "ocr_detection", "ocr_recognition", "ocr_orientation", "baseline"}
    if set(manifest.get("models", {})) != expected_roles or (output / "vlm").exists():
        raise RuntimeError("Gate 1 Core Models bundle has an unexpected component set")
    size = sum(path.stat().st_size for path in output.rglob("*") if path.is_file())
    print(json.dumps({"output": str(output), "size_bytes": size, "roles": sorted(expected_roles)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
