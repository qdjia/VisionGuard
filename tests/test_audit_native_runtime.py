from pathlib import Path

from scripts.audit_native_runtime import classify_native, inventory


def test_native_classification_does_not_claim_legal_approval() -> None:
    assert classify_native("cudnn64_9.dll", "torch/lib/cudnn64_9.dll") == (
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
