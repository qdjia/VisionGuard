import time

from api_support import make_test_app
from fastapi.testclient import TestClient


def test_deferred_startup_serves_live_before_models_are_ready():
    app, _ = make_test_app(api_updates={"deferred_startup": True})
    with TestClient(app) as client:
        assert client.get("/health/live").status_code == 200
        deadline = time.perf_counter() + 2
        while time.perf_counter() < deadline:
            response = client.get("/health/ready")
            if response.status_code == 200:
                break
            time.sleep(0.01)
        assert response.status_code == 200
