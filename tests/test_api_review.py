from api_support import FakePipeline, make_test_app, upload
from fastapi.testclient import TestClient


def test_review_modes_details_artifacts_and_ids():
    full = FakePipeline(mode="full")
    cascaded = FakePipeline(mode="cascaded")
    app, _ = make_test_app(full=full, cascaded=cascaded)
    with TestClient(app) as client:
        default_response = upload(client)
        full_response = upload(
            client,
            params={
                "pipeline_mode": "full",
                "include_details": "true",
                "save_artifacts": "true",
            },
        )
    assert default_response.status_code == 200
    assert default_response.json()["metadata"]["pipeline_mode"] == "cascaded"
    assert default_response.json()["details"] is None
    body = full_response.json()
    assert body["metadata"]["pipeline_mode"] == "full"
    assert body["details"]["image_width"] == 48
    assert body["details"]["image_height"] == 32
    assert body["details"]["ocr_block_count"] == 1
    assert body["details"]["ocr_full_text"] == "test"
    assert body["details"]["ocr_blocks"][0]["text"] == "test"
    assert body["details"]["ocr_blocks"][0]["polygon"] == [
        [1.0, 1.0],
        [9.0, 1.0],
        [9.0, 8.0],
        [1.0, 8.0],
    ]
    assert body["details"]["vlm_evidence"] == []
    assert body["details"]["fusion_scores"] is None
    assert body["artifact_saved"] is True
    assert body["artifact_id"] == body["run_id"]
    assert body["request_id"] == full_response.headers["X-Request-ID"]
    assert len(body["run_id"]) == 32
    assert full.calls == 1
    assert cascaded.calls == 1


def test_partial_review_is_http_200_and_requires_manual_review():
    app, _ = make_test_app(cascaded=FakePipeline(partial=True))
    with TestClient(app) as client:
        response = upload(client)
    assert response.status_code == 200
    assert response.json()["status"] == "partial"
    assert response.json()["result"]["requires_manual_review"] is True


def test_models_are_initialized_once_for_multiple_requests_and_released():
    app, state = make_test_app()
    with TestClient(app) as client:
        for _ in range(3):
            assert upload(client).status_code == 200
        assert state["initializations"] == 1
        container = state["container"]
        assert container.initialization_count == 1
    assert container.full_pipeline is None
    assert container.cascaded_pipeline is None
