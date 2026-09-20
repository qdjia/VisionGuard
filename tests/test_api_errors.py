from api_support import FakePipeline, make_test_app, upload
from fastapi.testclient import TestClient

from visionguard.pipeline.exceptions import PipelineFatalError


def _assert_error(response, status, code):
    assert response.status_code == status
    body = response.json()["error"]
    assert body["code"] == code
    assert body["request_id"]
    assert "traceback" not in response.text.lower()


def test_upload_validation_and_invalid_mode():
    app, _ = make_test_app()
    with TestClient(app) as client:
        _assert_error(upload(client, content=b"not-image"), 400, "INVALID_IMAGE")
        _assert_error(upload(client, content=b""), 400, "INVALID_IMAGE")
        _assert_error(
            upload(client, mime="application/octet-stream"),
            415,
            "UNSUPPORTED_MEDIA_TYPE",
        )
        _assert_error(
            upload(client, params={"pipeline_mode": "invalid"}),
            400,
            "INVALID_PIPELINE_MODE",
        )


def test_oversized_upload_is_bounded():
    app, _ = make_test_app(api_updates={"max_upload_mb": 1})
    with TestClient(app) as client:
        response = upload(client, content=b"x" * (1024 * 1024 + 1))
    _assert_error(response, 413, "UPLOAD_TOO_LARGE")


def test_pipeline_and_unknown_failures_are_sanitized():
    pipeline_error = PipelineFatalError("private/path/model error", run_id="a" * 32)
    app, _ = make_test_app(cascaded=FakePipeline(error=pipeline_error))
    with TestClient(app, raise_server_exceptions=False) as client:
        response = upload(client)
    _assert_error(response, 500, "PIPELINE_FAILURE")
    assert response.json()["error"]["run_id"] == "a" * 32
    assert "private" not in response.text

    app, _ = make_test_app(cascaded=FakePipeline(error=RuntimeError("secret path")))
    with TestClient(app, raise_server_exceptions=False) as client:
        response = upload(client)
    _assert_error(response, 500, "INTERNAL_ERROR")
    assert "secret path" not in response.text


def test_missing_file_is_schema_error():
    app, _ = make_test_app()
    with TestClient(app) as client:
        response = client.post("/v1/review")
    _assert_error(response, 422, "INVALID_REQUEST")
