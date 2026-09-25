from scripts.build_model_bundle import attach_provenance


def test_attach_provenance_adds_immutable_model_metadata() -> None:
    models = {"vlm": {"path": "vlm", "files": []}}
    evidence = {
        "vlm": {
            "model_id": "owner/model",
            "revision": "a" * 40,
            "license": "Apache-2.0",
            "source": "https://example.test/owner/model",
            "artifact": "vlm/model.safetensors",
            "sha256": "b" * 64,
            "verification": "not copied into the bundle manifest",
        }
    }

    attach_provenance(models, evidence)

    assert models["vlm"]["provenance"]["revision"] == "a" * 40
    assert "verification" not in models["vlm"]["provenance"]


def test_attach_provenance_leaves_unknown_model_unchanged() -> None:
    models = {"detector": {"path": "detector/model.onnx"}}
    attach_provenance(models, {})
    assert "provenance" not in models["detector"]
