"""Acquire and verify the immutable VLM snapshot inside a managed directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from urllib.parse import quote


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download_required_file(spec: dict, target: Path, *, attempts: int = 20) -> None:
    import requests

    partial = target.with_suffix(target.suffix + ".partial")
    expected = spec["required_file_size_bytes"]
    if target.is_file() and target.stat().st_size == expected:
        return
    target.unlink(missing_ok=True)
    if partial.is_file() and partial.stat().st_size == expected:
        partial.replace(target)
        return
    if partial.is_file() and partial.stat().st_size > expected:
        partial.unlink()
    source = spec["source"].rstrip("/")
    revision = quote(spec["revision"], safe="")
    filename = quote(spec["required_file"], safe="/")
    url = f"{source}/resolve/{revision}/{filename}"
    for attempt in range(1, attempts + 1):
        offset = partial.stat().st_size if partial.is_file() else 0
        headers = {"Range": f"bytes={offset}-"} if offset else {}
        try:
            with requests.get(
                url,
                headers=headers,
                stream=True,
                allow_redirects=True,
                timeout=(30, 60),
            ) as response:
                response.raise_for_status()
                append = offset > 0 and response.status_code == 206
                mode = "ab" if append else "wb"
                with partial.open(mode) as output:
                    for chunk in response.iter_content(chunk_size=4 * 1024 * 1024):
                        if chunk:
                            output.write(chunk)
            if partial.stat().st_size == expected:
                partial.replace(target)
                return
            if partial.stat().st_size > expected:
                partial.unlink()
                raise RuntimeError("MODEL_VALIDATION_FAILED: model download exceeded expected size")
        except requests.RequestException:
            if attempt == attempts:
                raise
        if attempt < attempts:
            delay = min(2 ** min(attempt, 5), 30)
            print(
                f"Model transfer incomplete at {partial.stat().st_size if partial.exists() else 0} "
                f"bytes; resuming in {delay}s (attempt {attempt + 1}/{attempts})",
                flush=True,
            )
            time.sleep(delay)
    raise RuntimeError("MODEL_DOWNLOAD_FAILED: retry budget exhausted")


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    from huggingface_hub import snapshot_download
    from requests import RequestException

    model_dir = args.output / "vlm"
    model_dir.mkdir(parents=True, exist_ok=True)
    required = model_dir / spec["required_file"]
    snapshot_required = [name for name in spec["required_files"] if name != spec["required_file"]]
    for attempt in range(1, 6):
        try:
            snapshot_download(
                repo_id=spec["id"],
                revision=spec["revision"],
                local_dir=model_dir,
                resume_download=True,
                token=False,
                ignore_patterns=[spec["required_file"]],
            )
            missing = [name for name in snapshot_required if not (model_dir / name).is_file()]
            if not missing:
                break
            if attempt == 5:
                raise RuntimeError(
                    f"MODEL_VALIDATION_FAILED: missing required files: {', '.join(missing)}"
                )
            delay = min(2**attempt, 30)
            print(
                f"Model snapshot is incomplete; resuming in {delay}s (attempt {attempt + 1}/5)",
                flush=True,
            )
            time.sleep(delay)
        except RequestException:
            if attempt == 5:
                raise
            delay = min(2**attempt, 30)
            print(
                f"Model download interrupted; resuming in {delay}s (attempt {attempt + 1}/5)",
                flush=True,
            )
            time.sleep(delay)
    _download_required_file(spec, required)
    if not required.is_file() or required.stat().st_size != spec["required_file_size_bytes"]:
        raise RuntimeError("MODEL_VALIDATION_FAILED: required model file size mismatch")
    if _sha256(required) != spec["required_file_sha256"]:
        raise RuntimeError("MODEL_VALIDATION_FAILED: required model file hash mismatch")
    manifest = {
        "schema_version": 1,
        "bundle_type": "vlm",
        "bundle_version": spec["bundle_version"],
        "compatible_api_major": 1,
        "compatible_prompt_versions": ["v1"],
        "model_id": spec["id"],
        "revision": spec["revision"],
        "files": [
            {
                "path": f"vlm/{required.name}",
                "size_bytes": required.stat().st_size,
                "sha256": spec["required_file_sha256"],
            }
        ],
    }
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
