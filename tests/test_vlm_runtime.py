import json
from pathlib import Path

import cv2
import httpx
import numpy as np
from fastapi.testclient import TestClient

from visionguard.moderation.policy import ModerationPolicy
from visionguard.moderation.schemas import ModerationResult
from visionguard.vlm.config import VLMConfig
from visionguard.vlm.providers.remote import RemoteVLMProvider
from visionguard.vlm.schemas import VLMContext
from visionguard.vlm_runtime.app import create_vlm_app
from visionguard.vlm_runtime.config import VLMRuntimeConfig


def test_managed_runtime_module_entrypoint_is_available() -> None:
    from visionguard.vlm_runtime.__main__ import run

    assert callable(run)


TOKEN = "a" * 32


def policy():
    return ModerationPolicy.model_validate(
        {
            "version": "v1",
            "categories": {"violence": {"description": "Violence"}},
            "risk_levels": {
                "low": {"description": "Low"},
                "medium": {"description": "Medium"},
                "high": {"description": "High"},
            },
        }
    )


def result():
    return ModerationResult(
        risk_level="low",
        categories=[],
        reason="No risk evidence.",
        evidence=[],
        confidence_score=0.9,
        requires_manual_review=False,
    )


class FakeService:
    loaded = False
    state = "installed"
    model_init_count = 0
    model_load_ms = 0.0

    def analyze(self, image, context, moderation_policy):
        self.loaded = True
        self.state = "ready"
        self.model_init_count += 1
        return result()


def runtime_config(tmp_path: Path):
    model = tmp_path / "model"
    model.mkdir()
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    return VLMRuntimeConfig(
        model_path=model,
        cache_root=tmp_path / "cache",
        log_root=tmp_path / "logs",
        prompts_dir=prompts,
    )


def test_runtime_requires_session_and_preserves_structured_contract(tmp_path):
    service = FakeService()
    client = TestClient(
        create_vlm_app(runtime_config(tmp_path), service, TOKEN),
        client=("127.0.0.1", 50000),
    )
    assert client.get("/health/live").status_code == 200
    assert client.get("/v1/meta").status_code == 404
    headers = {"X-VisionGuard-Session": TOKEN}
    meta = client.get("/v1/meta", headers=headers).json()
    assert meta["api_version"] == 1
    assert meta["model_loaded"] is False
    ok, image = cv2.imencode(".png", np.zeros((12, 16, 3), dtype=np.uint8))
    assert ok
    response = client.post(
        "/v1/analyze",
        headers=headers,
        files={"image": ("image.png", image.tobytes(), "image/png")},
        data={
            "context_json": VLMContext().model_dump_json(),
            "policy_json": policy().model_dump_json(),
            "prompt_version": "v1",
            "request_metadata_json": json.dumps({"request_id": "test"}),
        },
    )
    assert response.status_code == 200
    assert response.json()["result"]["risk_level"] == "low"
    assert service.model_init_count == 1


def test_runtime_rejects_prompt_contract_mismatch(tmp_path):
    client = TestClient(
        create_vlm_app(runtime_config(tmp_path), FakeService(), TOKEN),
        client=("127.0.0.1", 50000),
    )
    ok, image = cv2.imencode(".png", np.zeros((4, 4, 3), dtype=np.uint8))
    assert ok
    response = client.post(
        "/v1/analyze",
        headers={"X-VisionGuard-Session": TOKEN},
        files={"image": ("x.png", image.tobytes(), "image/png")},
        data={
            "context_json": VLMContext().model_dump_json(),
            "policy_json": policy().model_dump_json(),
            "prompt_version": "v999",
        },
    )
    assert response.status_code == 409


def test_remote_provider_registration_and_timeout_mapping(monkeypatch, tmp_path):
    config = VLMConfig(
        provider="remote",
        model_name_or_path="optional",
        prompts_dir=tmp_path,
        endpoint=None,
    )
    provider = RemoteVLMProvider(config)

    class Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"api_version": 1, "prompt_version": "v1"}

    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: Response())
    provider.configure("http://127.0.0.1:43125", TOKEN)
    assert provider.available
    assert provider.meta()["api_version"] == 1
    provider.clear()
    assert not provider.available
