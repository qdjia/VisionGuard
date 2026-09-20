from concurrent.futures import ThreadPoolExecutor

from api_support import FakePipeline, make_test_app, upload
from fastapi.testclient import TestClient


def test_semaphore_serializes_inference_and_reports_queue_wait():
    slow = FakePipeline(delay=0.12)
    app, _ = make_test_app(
        cascaded=slow,
        api_updates={"max_concurrent_inference": 1, "request_timeout_seconds": 2},
    )
    with TestClient(app) as client:
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: upload(client), range(2)))
    assert all(response.status_code == 200 for response in responses)
    assert slow.max_active == 1
    waits = sorted(response.json()["timing"]["queue_wait_ms"] for response in responses)
    assert waits[0] < 50
    assert waits[1] >= 80
