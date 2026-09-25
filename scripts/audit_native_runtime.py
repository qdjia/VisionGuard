"""Create a hash-complete native runtime inventory without making legal conclusions."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

NATIVE_SUFFIXES = {".dll", ".exe", ".pyd"}
NVIDIA_PREFIXES = (
    "cublas",
    "cudart",
    "cudnn",
    "cufft",
    "cupti",
    "curand",
    "cusparse",
    "nvjitlink",
    "nvrtc",
)
CUDA_EULA_URL = "https://docs.nvidia.com/cuda/eula/"
CUDNN_EULA_URL = "https://docs.nvidia.com/deeplearning/cudnn/latest/reference/eula.html"


def nvidia_redistribution(name: str) -> dict[str, str] | None:
    """Map a bundled NVIDIA DLL to the official redistribution evidence.

    This is an engineering mapping, not legal advice.  A name that cannot be
    matched exactly enough remains UNCLEAR and therefore blocks a public RC.
    """
    lowered = name.casefold()
    if lowered.startswith("cudnn"):
        return {
            "category": "cuDNN runtime",
            "canonical_name": "cudnn*.dll",
            "source_component": "PyTorch CUDA wheel / NVIDIA cuDNN runtime",
            "evidence_url": CUDNN_EULA_URL,
            "evidence_reference": "cuDNN Supplement, Distribution: runtime .so and .dll",
            "status": "ALLOWED_WITH_CONDITIONS",
        }
    mappings = (
        ("cublaslt", "CUDA BLAS Library", "cublasLt.dll"),
        ("cublas", "CUDA BLAS Library", "cublas.dll"),
        ("cudart", "CUDA Runtime", "cudart.dll"),
        ("cufftw", "CUDA FFT Library", "cufftw.dll"),
        ("cufft", "CUDA FFT Library", "cufft.dll"),
        ("curand", "CUDA Random Number Generation Library", "curand.dll"),
        ("cusparse", "CUDA Sparse Matrix Library", "cusparse.dll"),
        ("nvrtc-builtins", "NVIDIA Runtime Compilation Library", "nvrtc-builtins.dll"),
        ("nvrtc", "NVIDIA Runtime Compilation Library", "nvrtc.dll"),
    )
    for prefix, category, canonical in mappings:
        if lowered.startswith(prefix):
            return {
                "category": category,
                "canonical_name": canonical,
                "source_component": "PyTorch CUDA wheel / NVIDIA CUDA runtime",
                "evidence_url": CUDA_EULA_URL,
                "evidence_reference": "CUDA Toolkit Supplement, Attachment A",
                "status": "ALLOWED_WITH_CONDITIONS",
            }
    if lowered.startswith("nvjitlink"):
        return {
            "category": "NVIDIA JIT Linking Library",
            "canonical_name": "libnvJitLink.dll",
            "source_component": "PyTorch CUDA wheel / NVIDIA CUDA runtime",
            "evidence_url": CUDA_EULA_URL,
            "evidence_reference": "CUDA Toolkit Supplement, Attachment A",
            "status": "UNCLEAR",
        }
    return None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def classify_native(name: str, relative: str) -> tuple[str, str]:
    lowered = name.casefold()
    relative_lower = relative.casefold()
    if lowered.startswith(NVIDIA_PREFIXES):
        return "nvidia_cuda_or_cudnn", "requires_attachment_a_review"
    if "torch" in relative_lower:
        return "pytorch_native", "requires_pytorch_third_party_review"
    if "onnxruntime" in relative_lower:
        return "onnx_runtime", "mit_notice_required"
    if "paddle" in relative_lower or lowered.startswith("phi_"):
        return "paddle_native", "apache_notice_and_model_review_required"
    if lowered.startswith(("vcruntime", "msvcp", "ucrtbase")):
        return "microsoft_vc_runtime", "microsoft_redistributable_terms_apply"
    if lowered.endswith(".pyd"):
        return "python_extension", "package_license_review_required"
    return "other_native", "manual_review_required"


def inventory(runtime_root: Path) -> dict[str, object]:
    root = runtime_root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"runtime root does not exist: {root}")
    files = []
    statuses: Counter[str] = Counter()
    owners: Counter[str] = Counter()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.casefold() not in NATIVE_SUFFIXES:
            continue
        relative = path.relative_to(root).as_posix()
        owner, status = classify_native(path.name, relative)
        owners[owner] += 1
        statuses[status] += 1
        record = {
            "path": relative,
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
            "classification": owner,
            "redistribution_review": status,
        }
        evidence = nvidia_redistribution(path.name)
        if evidence:
            record["source_package"] = "torch"
            record["source_package_version"] = "2.11.0+cu128"
            record["nvidia_redistribution"] = evidence
        files.append(record)
    nvidia = [item for item in files if "nvidia_redistribution" in item]
    unique_nvidia = {item["sha256"]: item for item in nvidia}.values()
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "runtime_component": root.name,
        "native_file_count": len(files),
        "bytes": sum(int(item["size_bytes"]) for item in files),
        "classification_counts": dict(sorted(owners.items())),
        "review_counts": dict(sorted(statuses.items())),
        "legal_conclusion": "not_provided_by_tool",
        "nvidia_candidate_count": len(nvidia),
        "nvidia_unique_sha256_count": len(unique_nvidia),
        "nvidia_status_counts": dict(
            sorted(Counter(item["nvidia_redistribution"]["status"] for item in nvidia).items())
        ),
        "nvidia_unique_status_counts": dict(
            sorted(
                Counter(item["nvidia_redistribution"]["status"] for item in unique_nvidia).items()
            )
        ),
        "files": files,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = inventory(args.runtime)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({key: payload[key] for key in ("native_file_count", "bytes")}))


if __name__ == "__main__":
    main()
