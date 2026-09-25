from pathlib import Path

from scripts.audit_native_runtime import classify_native, inventory, nvidia_redistribution


def test_native_classification_does_not_claim_legal_approval() -> None:
    assert classify_native("cudnn64_9.dll", "torch/lib/cudnn64_9.dll") == (
        "nvidia_cuda_or_cudnn",
        "requires_attachment_a_review",
    )
    assert classify_native("cudart64_12.dll", "torch/lib/cudart64_12.dll") == (
        "nvidia_cuda_or_cudnn",
        "requires_attachment_a_review",
    )
    assert classify_native("torch_cuda.dll", "torch/lib/torch_cuda.dll")[0] == "pytorch_native"


def test_inventory_hashes_and_uses_relative_paths(tmp_path: Path) -> None:
    native = tmp_path / "_internal" / "onnxruntime" / "onnxruntime.dll"
    native.parent.mkdir(parents=True)
    native.write_bytes(b"native")
    result = inventory(tmp_path)
    assert result["native_file_count"] == 1
    assert result["legal_conclusion"] == "not_provided_by_tool"
    assert result["files"][0]["path"] == "_internal/onnxruntime/onnxruntime.dll"
    assert len(result["files"][0]["sha256"]) == 64


def test_nvidia_inventory_maps_official_evidence_without_overclaiming(tmp_path: Path) -> None:
    torch_lib = tmp_path / "_internal" / "torch" / "lib"
    torch_lib.mkdir(parents=True)
    (torch_lib / "cublas64_12.dll").write_bytes(b"blas")
    (torch_lib / "cudnn64_9.dll").write_bytes(b"cudnn")
    (torch_lib / "nvJitLink_120_0.dll").write_bytes(b"jit")

    result = inventory(tmp_path)
    assert result["nvidia_candidate_count"] == 3
    assert result["nvidia_status_counts"] == {
        "ALLOWED_WITH_CONDITIONS": 2,
        "UNCLEAR": 1,
    }
    assert result["nvidia_unique_sha256_count"] == 3
    assert result["nvidia_unique_status_counts"] == {
        "ALLOWED_WITH_CONDITIONS": 2,
        "UNCLEAR": 1,
    }
    by_name = {Path(item["path"]).name: item for item in result["files"]}
    assert by_name["cublas64_12.dll"]["nvidia_redistribution"]["canonical_name"] == ("cublas.dll")
    assert by_name["cudnn64_9.dll"]["nvidia_redistribution"]["category"] == "cuDNN runtime"
    nvjit = by_name["nvJitLink_120_0.dll"]["nvidia_redistribution"]
    assert nvjit["status"] == "UNCLEAR"
    assert nvjit["canonical_name"] == "nvJitLink.dll"
    assert nvjit["attachment_a_name"] == "libnvJitLink.dll"


def test_non_nvidia_file_has_no_redistribution_mapping() -> None:
    assert nvidia_redistribution("torch_cuda.dll") is None


def test_nvidia_inventory_distinguishes_duplicate_files_from_unique_binaries(
    tmp_path: Path,
) -> None:
    torch_lib = tmp_path / "_internal" / "torch" / "lib"
    torchvision = tmp_path / "_internal" / "torchvision"
    torch_lib.mkdir(parents=True)
    torchvision.mkdir(parents=True)
    (torch_lib / "cudart64_12.dll").write_bytes(b"same-runtime")
    (torchvision / "cudart64_12.dll").write_bytes(b"same-runtime")

    result = inventory(tmp_path)
    assert result["nvidia_candidate_count"] == 2
    assert result["nvidia_unique_sha256_count"] == 1
    assert result["nvidia_status_counts"] == {"ALLOWED_WITH_CONDITIONS": 2}
    assert result["nvidia_unique_status_counts"] == {"ALLOWED_WITH_CONDITIONS": 1}
