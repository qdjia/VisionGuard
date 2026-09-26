"""Strict parsing and trust-boundary checks for the bootstrap manifest."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

TRUSTED_HOSTS = {
    "www.python.org",
    "bootstrap.pypa.io",
    "pypi.org",
    "download.pytorch.org",
    "huggingface.co",
}
PACKAGE = re.compile(r"^[A-Za-z0-9_.-]+==[A-Za-z0-9_.+!-]+$")
PYPI_INDEX = "https://pypi.org/simple"
PYTORCH_INDEX = "https://download.pytorch.org/whl/cu128"
MODEL_ID = "Qwen/Qwen3-VL-2B-Instruct"
MODEL_SOURCE = f"https://huggingface.co/{MODEL_ID}"


class ManifestError(ValueError):
    pass


def _trusted_https(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and parsed.hostname in TRUSTED_HOSTS and not parsed.username


def load_manifest(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or payload.get("distribution_mode") != "online-bootstrap":
        raise ManifestError("unsupported Advanced AI bootstrap manifest")
    if payload.get("platform") != "windows" or payload.get("architecture") != "x86_64":
        raise ManifestError("bootstrap manifest is not compatible with this release")
    urls = [
        payload["python"]["url"],
        payload["python"]["pip_bootstrap"]["url"],
        *payload["indexes"].values(),
        payload["model"]["source"],
    ]
    if not all(isinstance(url, str) and _trusted_https(url) for url in urls):
        raise ManifestError("bootstrap manifest contains an untrusted source")
    if payload["indexes"] != {"pypi": PYPI_INDEX, "pytorch": PYTORCH_INDEX}:
        raise ManifestError("bootstrap package indexes do not match the approved sources")
    if not re.fullmatch(r"[0-9a-f]{64}", payload["python"]["sha256"]):
        raise ManifestError("Python installer SHA-256 is invalid")
    if payload["python"].get("distribution") != "official-embeddable-zip" or not re.fullmatch(
        r"[0-9a-f]{64}", payload["python"]["pip_bootstrap"]["sha256"]
    ):
        raise ManifestError("Python bootstrap metadata is invalid")
    if not re.fullmatch(r"[0-9a-f]{40}", payload["model"]["revision"]):
        raise ManifestError("model revision must be an immutable commit")
    model = payload["model"]
    if model.get("id") != MODEL_ID or model.get("source") != MODEL_SOURCE:
        raise ManifestError("model source does not match the approved repository")
    required = model.get("required_files")
    required_file = model.get("required_file")
    if (
        not isinstance(required, list)
        or not required
        or required_file not in required
        or any(
            not isinstance(name, str)
            or not name
            or Path(name).is_absolute()
            or ".." in Path(name).parts
            for name in required
        )
        or not isinstance(model.get("required_file_size_bytes"), int)
        or model["required_file_size_bytes"] <= 0
        or not re.fullmatch(r"[0-9a-f]{64}", model.get("required_file_sha256", ""))
    ):
        raise ManifestError("model verification metadata is invalid")
    packages = (
        payload["python"]["pip_bootstrap"]["packages"]
        + payload["packages"]["pytorch"]
        + payload["packages"]["runtime"]
    )
    if not packages or not all(PACKAGE.fullmatch(item) for item in packages):
        raise ManifestError("all bootstrap packages must use exact versions")
    return payload
