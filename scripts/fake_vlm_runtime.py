"""Small contract-compatible VLM sidecar for lifecycle and failure testing."""

import argparse
import os
import time
from typing import Annotated

import uvicorn
from fastapi import FastAPI, Header, HTTPException


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument(
        "--mode",
        choices=(
            "ready",
            "slow-ready",
            "slow-load",
            "crash",
            "invalid-schema",
            "timeout",
            "version-mismatch",
        ),
        default="ready",
    )
    args = parser.parse_args()
    token = os.environ.get("VISIONGUARD_VLM_SESSION_TOKEN", "fake-session-token")
    app = FastAPI()

    def authorize(x_visionguard_session: str | None = Header(default=None)):
        if x_visionguard_session != token:
            raise HTTPException(status_code=404)

    @app.get("/health/live")
    def live():
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready(_: Annotated[str | None, Header(alias="X-VisionGuard-Session")] = None):
        authorize(_)
        if args.mode == "slow-ready":
            time.sleep(2)
        return {"status": "installed", "model_loaded": False, "model_init_count": 0}

    @app.get("/v1/meta")
    def meta(_: Annotated[str | None, Header(alias="X-VisionGuard-Session")] = None):
        authorize(_)
        return {
            "api_version": 999 if args.mode == "version-mismatch" else 1,
            "runtime_version": "fake",
            "model_bundle_version": "fake",
            "model_identifier": "fake",
            "prompt_version": "v1",
            "model_loaded": False,
            "model_init_count": 0,
            "pid": os.getpid(),
        }

    @app.post("/v1/analyze")
    def analyze(_: Annotated[str | None, Header(alias="X-VisionGuard-Session")] = None):
        authorize(_)
        if args.mode == "crash":
            os._exit(9)
        if args.mode in {"slow-load", "timeout"}:
            time.sleep(30)
        if args.mode == "invalid-schema":
            return {"result": {"risk_level": "unknown"}}
        return {
            "api_version": 1,
            "result": {
                "risk_level": "low",
                "categories": [],
                "reason": "fake",
                "evidence": [],
                "confidence_score": 1.0,
                "requires_manual_review": False,
                "metadata": {},
            },
            "timing": {},
            "metadata": {},
        }

    uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
