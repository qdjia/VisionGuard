"""Loopback-only adapter for the optional Advanced AI runtime."""

from __future__ import annotations

import json
from threading import RLock

import cv2
import httpx

from visionguard.moderation.schemas import ModerationResult
from visionguard.utils.image import load_image
from visionguard.vlm.base import VLMProvider
from visionguard.vlm.exceptions import VLMInferenceError, VLMTimeoutError


class RemoteVLMProvider(VLMProvider):
    """Thread-safe endpoint registry plus stable VLMProvider transport."""

    def __init__(self, config) -> None:
        self.config = config
        self._lock = RLock()
        self._endpoint = config.endpoint
        self._token = config.session_token
        self._meta: dict = {}

    @property
    def available(self) -> bool:
        with self._lock:
            return self._endpoint is not None

    def configure(self, endpoint: str, token: str) -> dict:
        if not endpoint.startswith("http://127.0.0.1:"):
            raise ValueError("VLM endpoint must use IPv4 loopback")
        headers = {"X-VisionGuard-Session": token}
        try:
            response = httpx.get(f"{endpoint}/v1/meta", headers=headers, timeout=5)
            response.raise_for_status()
            meta = response.json()
        except Exception as exc:
            raise VLMInferenceError("VLM endpoint registration failed") from exc
        if int(meta.get("api_version", -1)) != self.config.api_version:
            raise VLMInferenceError("VLM_CONTRACT_INCOMPATIBLE")
        if meta.get("prompt_version") != self.config.prompt_version:
            raise VLMInferenceError("VLM_VERSION_INCOMPATIBLE")
        with self._lock:
            self._endpoint, self._token, self._meta = endpoint, token, meta
        return meta

    def clear(self) -> None:
        with self._lock:
            self._endpoint = self._token = None
            self._meta = {}

    def health(self) -> dict:
        endpoint, token = self._connection()
        response = httpx.get(
            f"{endpoint}/health/ready",
            headers={"X-VisionGuard-Session": token},
            timeout=3,
        )
        return response.json()

    def meta(self) -> dict:
        with self._lock:
            return dict(self._meta)

    def analyze(self, image, context, policy) -> ModerationResult:
        endpoint, token = self._connection()
        frame = load_image(image)
        ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
        if not ok:
            raise VLMInferenceError("could not encode image for VLM runtime")
        data = {
            "context_json": context.model_dump_json(),
            "policy_json": policy.model_dump_json(),
            "prompt_version": self.config.prompt_version,
            "request_metadata_json": json.dumps({"transport": "loopback-multipart"}),
        }
        try:
            response = httpx.post(
                f"{endpoint}/v1/analyze",
                headers={"X-VisionGuard-Session": token},
                data=data,
                files={"image": ("image.jpg", encoded.tobytes(), "image/jpeg")},
                timeout=self.config.timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise VLMTimeoutError("VLM_INFERENCE_TIMEOUT") from exc
        except httpx.HTTPError as exc:
            raise VLMInferenceError("VLM runtime transport failed") from exc
        if response.status_code == 504:
            raise VLMTimeoutError("VLM_INFERENCE_TIMEOUT")
        if response.status_code >= 400:
            code = response.json().get("error", {}).get("code", "VLM_RUNTIME_EXITED")
            raise VLMInferenceError(str(code))
        return ModerationResult.model_validate(response.json()["result"])

    def _connection(self) -> tuple[str, str]:
        with self._lock:
            if not self._endpoint or not self._token:
                raise VLMInferenceError("VLM_NOT_READY")
            return self._endpoint, self._token
