from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import types
import zipfile
from pathlib import Path

import pytest

from scripts.build_release import assert_online_bootstrap_hygiene
from visionguard.bootstrap import model_download
from visionguard.bootstrap.manager import BootstrapError, BootstrapManager
from visionguard.bootstrap.manifest import ManifestError, load_manifest

ROOT = Path(__file__).resolve().parents[1]
SOURCE_MANIFEST = ROOT / "packaging/bootstrap/advanced-ai-bootstrap-manifest.json"


def _manifest(tmp_path: Path, **updates) -> Path:
    payload = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    payload.update(updates)
    target = tmp_path / "manifest.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


def test_manifest_pins_official_sources_and_immutable_versions() -> None:
    manifest = load_manifest(SOURCE_MANIFEST)
    assert manifest["python"]["version"] == "3.11.9"
    assert manifest["python"]["distribution"] == "official-embeddable-zip"
    assert manifest["packages"]["pytorch"] == [
        "torch==2.11.0+cu128",
        "torchvision==0.26.0+cu128",
    ]
    assert len(manifest["model"]["revision"]) == 40


def test_human_readable_lock_matches_bootstrap_manifest() -> None:
    manifest = load_manifest(SOURCE_MANIFEST)
    expected = set(
        manifest["python"]["pip_bootstrap"]["packages"]
        + manifest["packages"]["pytorch"]
        + manifest["packages"]["runtime"]
    )
    actual = {
        line
        for line in (ROOT / "requirements-vlm-bootstrap.lock")
        .read_text(encoding="utf-8")
        .splitlines()
        if line and not line.startswith(("#", "--"))
    }
    assert actual == expected


def test_online_release_scan_rejects_cuda_and_model_payloads(tmp_path: Path) -> None:
    (tmp_path / "nvJitLink_120_0.dll").write_bytes(b"native")
    with pytest.raises(RuntimeError, match="forbidden Advanced AI assets"):
        assert_online_bootstrap_hygiene(tmp_path)


def test_cancel_file_stops_managed_subprocess(tmp_path: Path) -> None:
    wheel = tmp_path / "visionguard.whl"
    wheel.write_bytes(b"wheel")
    cancel = tmp_path / "cancel"
    cancel.write_text("cancel", encoding="utf-8")
    manager = BootstrapManager(
        SOURCE_MANIFEST,
        tmp_path / "data",
        tmp_path / "status.json",
        wheel,
        cancel_path=cancel,
    )
    with pytest.raises(BootstrapError) as raised:
        manager._run([sys.executable, "-c", "import time; time.sleep(30)"])
    assert raised.value.code == "ADVANCED_AI_INSTALL_CANCELLED"


def test_manifest_rejects_arbitrary_download_source(tmp_path: Path) -> None:
    payload = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    payload["python"]["url"] = "https://example.invalid/python.exe"
    target = tmp_path / "manifest.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ManifestError, match="untrusted"):
        load_manifest(target)


def test_manifest_rejects_arbitrary_model_repository(tmp_path: Path) -> None:
    payload = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    payload["model"]["id"] = "untrusted/arbitrary-model"
    target = tmp_path / "manifest.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ManifestError, match="approved repository"):
        load_manifest(target)


def test_model_download_retries_transient_stream_failure(tmp_path: Path, monkeypatch) -> None:
    from requests.exceptions import ChunkedEncodingError

    weights = b"verified-model"
    spec = {
        "id": "Qwen/Qwen3-VL-2B-Instruct",
        "revision": "a" * 40,
        "bundle_version": "test-model",
        "required_file": "model.safetensors",
        "required_files": ["config.json", "model.safetensors"],
        "required_file_size_bytes": len(weights),
        "required_file_sha256": hashlib.sha256(weights).hexdigest(),
    }
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    attempts = 0

    def snapshot_download(**kwargs) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ChunkedEncodingError("connection interrupted")
        if attempts == 2:
            return
        model_dir = Path(kwargs["local_dir"])
        model_dir.mkdir(parents=True, exist_ok=True)
        (model_dir / "config.json").write_text("{}", encoding="utf-8")

    monkeypatch.setitem(
        sys.modules, "huggingface_hub", types.SimpleNamespace(snapshot_download=snapshot_download)
    )
    monkeypatch.setattr(model_download.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        model_download,
        "_download_required_file",
        lambda _spec, target: target.write_bytes(weights),
    )

    assert model_download.run(["--spec", str(spec_path), "--output", str(tmp_path / "model")]) == 0
    assert attempts == 3


def test_required_model_download_resumes_with_http_range(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "model.safetensors"
    target.with_suffix(".safetensors.partial").write_bytes(b"abc")
    observed_headers = {}

    class Response:
        status_code = 206

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def raise_for_status(self) -> None:
            return None

        def iter_content(self, chunk_size: int):
            assert chunk_size == 4 * 1024 * 1024
            yield b"def"

    def get(_url, *, headers, **_kwargs):
        observed_headers.update(headers)
        return Response()

    monkeypatch.setattr("requests.get", get)
    model_download._download_required_file(
        {
            "source": "https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct",
            "revision": "a" * 40,
            "required_file": target.name,
            "required_file_size_bytes": 6,
        },
        target,
    )

    assert observed_headers == {"Range": "bytes=3-"}
    assert target.read_bytes() == b"abcdef"


def test_preflight_rejects_missing_product_wheel(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("platform.system", lambda: "Windows")
    monkeypatch.setattr("platform.machine", lambda: "AMD64")
    manager = BootstrapManager(
        SOURCE_MANIFEST, tmp_path / "data", tmp_path / "status.json", tmp_path / "missing.whl"
    )
    with pytest.raises(BootstrapError) as raised:
        manager.preflight()
    assert raised.value.code == "BOOTSTRAP_PACKAGE_MISSING"


def test_network_failure_keeps_core_registry_inactive(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("platform.system", lambda: "Windows")
    monkeypatch.setattr("platform.machine", lambda: "AMD64")
    monkeypatch.setattr(
        shutil, "disk_usage", lambda _: shutil._ntuple_diskusage(30_000_000_000, 0, 30_000_000_000)
    )
    wheel = tmp_path / "visionguard.whl"
    wheel.write_bytes(b"wheel")

    def fail_download(_url: str, _target: Path) -> None:
        raise OSError("network unavailable")

    status = tmp_path / "status.json"
    manager = BootstrapManager(
        SOURCE_MANIFEST,
        tmp_path / "data",
        status,
        wheel,
        downloader=fail_download,
        gpu_probe=lambda: {"gpu_name": "test", "gpu_memory_mib": 8192},
    )
    with pytest.raises(BootstrapError) as raised:
        manager.install()
    assert raised.value.code == "BOOTSTRAP_FAILED"
    assert json.loads(status.read_text(encoding="utf-8"))["state"] == "Failed"
    assert not (tmp_path / "data/components/components.json").exists()


def test_atomic_install_activates_managed_environment(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("platform.system", lambda: "Windows")
    monkeypatch.setattr("platform.machine", lambda: "AMD64")
    monkeypatch.setattr(
        shutil, "disk_usage", lambda _: shutil._ntuple_diskusage(30_000_000_000, 0, 30_000_000_000)
    )
    payload = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    archive = tmp_path / "python.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("python.exe", b"python")
        output.writestr("python311._pth", "python311.zip\n.\n#import site\n")
    python_bytes = archive.read_bytes()
    get_pip_bytes = b"official-get-pip-fixture"
    payload["python"]["size_bytes"] = len(python_bytes)
    payload["python"]["sha256"] = hashlib.sha256(python_bytes).hexdigest()
    payload["python"]["pip_bootstrap"]["size_bytes"] = len(get_pip_bytes)
    payload["python"]["pip_bootstrap"]["sha256"] = hashlib.sha256(get_pip_bytes).hexdigest()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    wheel = tmp_path / "visionguard.whl"
    wheel.write_bytes(b"wheel")
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    validation_calls: list[tuple[Path, Path]] = []

    def download(url: str, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(get_pip_bytes if url.endswith("get-pip.py") else python_bytes)

    def run(args, **_kwargs):
        args = list(map(str, args))
        if "--report" in args:
            Path(args[args.index("--report") + 1]).write_text('{"install": []}', encoding="utf-8")
        if "visionguard.bootstrap.model_download" in args:
            output = Path(args[args.index("--output") + 1])
            (output / "vlm").mkdir(parents=True)
            (output / "manifest.json").write_text("{}", encoding="utf-8")
        stdout = '[["torch", "2.11.0+cu128"], ["transformers", "4.57.6"]]'
        return subprocess.CompletedProcess(args, 0, stdout=stdout)

    manager = BootstrapManager(
        manifest,
        tmp_path / "data",
        tmp_path / "status.json",
        wheel,
        prompts,
        downloader=download,
        runner=run,
        runtime_validator=lambda python, models, _env, _stage: validation_calls.append(
            (python, models)
        ),
        gpu_probe=lambda: {"gpu_name": "test", "gpu_memory_mib": 8192},
    )
    result = manager.install()
    registry = json.loads(
        (tmp_path / "data/components/components.json").read_text(encoding="utf-8")
    )
    assert result["environment_version"] == "vlm-v1"
    assert registry["distribution_mode"] == "online_bootstrap"
    assert (tmp_path / "data" / registry["python_executable"]).is_file()
    assert len(validation_calls) == 1
    assert json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))["state"] == "Ready"
