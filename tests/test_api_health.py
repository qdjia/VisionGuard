from api_support import make_test_app
from fastapi.testclient import TestClient


def test_liveness_readiness_meta_and_openapi():
    app, _ = make_test_app()
    with TestClient(app) as client:
        live = client.get("/health/live")
        ready = client.get("/health/ready")
        meta = client.get("/v1/meta")
        openapi = client.get("/openapi.json")
    assert live.json() == {"status": "ok"}
    assert ready.status_code == 200
    assert all(ready.json()["components"].values())
    assert meta.json()["model_identifiers"]["detector"] == "mock.pt"
    assert "D:" not in meta.text
    assert openapi.status_code == 200
    assert "/v1/review" in openapi.json()["paths"]


def test_not_ready_has_structured_503():
    app, state = make_test_app()
    with TestClient(app) as client:
        state["container"].ready = False
        response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "PIPELINE_NOT_READY"
    assert response.json()["error"]["request_id"]
