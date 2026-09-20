"""Exercise a running VisionGuard API with real configured models."""

import argparse
import mimetypes
from pathlib import Path

import httpx


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--safe-image", type=Path, required=True)
    parser.add_argument("--risky-image", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=180)
    return parser.parse_args()


def _post(client: httpx.Client, image: Path, mode: str) -> None:
    media_type = mimetypes.guess_type(image.name)[0] or "image/jpeg"
    with image.open("rb") as stream:
        response = client.post(
            "/v1/review",
            params={"pipeline_mode": mode, "save_artifacts": "false"},
            files={"file": (image.name, stream, media_type)},
        )
    payload = response.json()
    result = payload.get("result", {})
    timing = payload.get("timing", {})
    print(
        f"POST {image.name} mode={mode}: status={response.status_code} "
        f"run_id={payload.get('run_id')} risk={result.get('risk_level')} "
        f"request_ms={timing.get('request_total_ms')} "
        f"queue_ms={timing.get('queue_wait_ms')} "
        f"pipeline_ms={timing.get('pipeline_total_ms')}"
    )
    response.raise_for_status()


def main() -> None:
    args = parse_args()
    for image in (args.safe_image, args.risky_image):
        if not image.is_file():
            raise FileNotFoundError(image)
    with httpx.Client(base_url=args.base_url, timeout=args.timeout) as client:
        for endpoint in ("/health/live", "/health/ready", "/v1/meta"):
            response = client.get(endpoint)
            print(f"GET {endpoint}: status={response.status_code} body={response.json()}")
            response.raise_for_status()
        _post(client, args.safe_image, "cascaded")
        _post(client, args.risky_image, "cascaded")
        _post(client, args.safe_image, "full")
        invalid = client.post(
            "/v1/review",
            files={"file": ("invalid.png", b"not-an-image", "image/png")},
        )
        print(f"POST invalid file: status={invalid.status_code} body={invalid.json()}")
        if invalid.status_code != 400:
            raise RuntimeError("invalid-image smoke request did not return HTTP 400")


if __name__ == "__main__":
    main()
