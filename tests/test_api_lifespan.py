import time

from api_support import FakePipeline, make_test_app, upload
from fastapi.testclient import TestClient


def test_timeout_returns_504_without_claiming_hard_cancellation():
    slow = FakePipeline(delay=0.12)
    app, state = make_test_app(
        cascaded=slow,
        api_updates={"request_timeout_seconds": 0.02, "shutdown_grace_seconds": 1},
    )
    with TestClient(app) as client:
        response = upload(client)
        _ = client.get("/health/live")
        time.sleep(0.15)
        assert not state["container"].active_tasks
    assert response.status_code == 504
    assert response.json()["error"]["code"] == "INFERENCE_TIMEOUT"
    assert response.json()["error"]["details"]["phase"] == "inference"
