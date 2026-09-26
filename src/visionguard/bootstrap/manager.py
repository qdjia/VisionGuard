"""Atomic, resumable Advanced AI online bootstrap orchestration."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import threading
import time
import urllib.request
import uuid
import zipfile
from collections.abc import Callable
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path

from .manifest import load_manifest


class BootstrapError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class BootstrapManager:
    def __init__(
        self,
        manifest_path: Path,
        data_dir: Path,
        status_path: Path,
        wheel_path: Path,
        prompts_path: Path | None = None,
        cancel_path: Path | None = None,
        *,
        downloader: Callable[[str, Path], None] | None = None,
        runner: Callable[..., subprocess.CompletedProcess] | None = None,
        runtime_validator: Callable[[Path, Path, dict[str, str], Path], None] | None = None,
        gpu_probe: Callable[[], dict[str, object]] | None = None,
    ) -> None:
        self.manifest = load_manifest(manifest_path)
        self.data_dir = data_dir.resolve()
        self.status_path = status_path.resolve()
        self.wheel_path = wheel_path.resolve()
        self.prompts_path = prompts_path.resolve() if prompts_path else None
        self.downloader = downloader or self._download
        self.runner = runner or subprocess.run
        self._uses_default_runner = runner is None
        self.runtime_validator = runtime_validator or self._validate_runtime_startup
        self.gpu_probe = gpu_probe or self._probe_nvidia_gpu
        self.cancel_path = cancel_path.resolve() if cancel_path else None
        self.root = self.data_dir / "advanced-ai"
        self.cache = self.root / "staging" / "download-cache"
        self._sizing: dict[str, object] = {}
        self._status_lock = threading.Lock()

    def _status(self, state: str, **values) -> None:
        payload = {
            "schema_version": 1,
            "state": state,
            "updated_at": datetime.now(UTC).isoformat(),
            **values,
        }
        with self._status_lock:
            self.status_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.status_path.with_suffix(self.status_path.suffix + ".tmp")
            temporary.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            temporary.replace(self.status_path)

    @staticmethod
    def _directory_bytes(*roots: Path) -> int:
        total = 0
        for root in roots:
            if not root.exists():
                continue
            for directory, _, filenames in os.walk(root, onerror=lambda _: None):
                for filename in filenames:
                    try:
                        total += (Path(directory) / filename).stat().st_size
                    except OSError:
                        # Package installers constantly create and remove metadata/temp
                        # files. Progress accounting must tolerate that race.
                        continue
        return total

    @staticmethod
    def _download(url: str, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_suffix(target.suffix + ".partial")
        request = urllib.request.Request(url, headers={"User-Agent": "VisionGuard-bootstrap/1"})
        with urllib.request.urlopen(request, timeout=60) as response, partial.open("wb") as output:
            shutil.copyfileobj(response, output, length=1024 * 1024)
        partial.replace(target)

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _probe_nvidia_gpu() -> dict[str, object]:
        executable = shutil.which("nvidia-smi")
        if executable is None:
            raise BootstrapError(
                "GPU_REQUIREMENT_NOT_SATISFIED",
                "Advanced AI requires a supported NVIDIA GPU; nvidia-smi was not found",
            )
        result = subprocess.run(
            [
                executable,
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0 or not result.stdout.strip():
            raise BootstrapError(
                "GPU_REQUIREMENT_NOT_SATISFIED",
                "Unable to validate an NVIDIA GPU with nvidia-smi",
            )
        name, memory_mib, driver = [
            part.strip() for part in result.stdout.splitlines()[0].split(",")
        ]
        return {
            "gpu_name": name,
            "gpu_memory_mib": int(memory_mib),
            "gpu_driver_version": driver,
        }

    def _run(
        self,
        args: list[str],
        *,
        env: dict[str, str] | None = None,
        state: str | None = None,
        component: str | None = None,
        progress_paths: tuple[Path, ...] = (),
    ) -> None:
        stopped = threading.Event()

        def report_progress() -> None:
            while not stopped.wait(0.5):
                self._status(
                    state or "Preparing",
                    component=component,
                    bytes_completed=self._directory_bytes(self.cache, *progress_paths),
                    bytes_total=self._sizing.get("download_bytes", 0),
                    **self._sizing,
                )

        watcher = None
        if state and not self._uses_default_runner:
            watcher = threading.Thread(target=report_progress, daemon=True)
            watcher.start()
        try:
            if self._uses_default_runner:
                child = subprocess.Popen(args, env=env)
                while child.poll() is None:
                    if self.cancel_path is not None and self.cancel_path.exists():
                        child.terminate()
                        try:
                            child.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            child.kill()
                            child.wait(timeout=5)
                        raise BootstrapError(
                            "ADVANCED_AI_INSTALL_CANCELLED", "Installation cancelled safely"
                        )
                    if state:
                        self._status(
                            state,
                            component=component,
                            bytes_completed=self._directory_bytes(self.cache, *progress_paths),
                            bytes_total=self._sizing.get("download_bytes", 0),
                            **self._sizing,
                        )
                    time.sleep(0.5)
                result = subprocess.CompletedProcess(args, child.returncode)
            else:
                result = self.runner(args, check=False, env=env)
        finally:
            stopped.set()
            if watcher:
                watcher.join(timeout=2)
        if result.returncode:
            raise BootstrapError(
                "BOOTSTRAP_COMMAND_FAILED", f"bootstrap step exited with {result.returncode}"
            )

    @staticmethod
    def _extract_python(archive: Path, target: Path) -> None:
        target.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as source:
            for item in source.infolist():
                relative = Path(item.filename)
                if relative.is_absolute() or ".." in relative.parts:
                    raise BootstrapError("RUNTIME_ARCHIVE_INVALID", "unsafe Python archive path")
            source.extractall(target)
        pth = target / "python311._pth"
        if not pth.is_file():
            raise BootstrapError("PYTHON_INSTALL_FAILED", "embedded Python path file is missing")
        contents = pth.read_text(encoding="utf-8")
        if "#import site" not in contents:
            raise BootstrapError("PYTHON_INSTALL_FAILED", "embedded Python site hook is missing")
        pth.write_text(contents.replace("#import site", "import site"), encoding="utf-8")

    def preflight(self) -> dict:
        if platform.system() != "Windows" or platform.machine().lower() not in {"amd64", "x86_64"}:
            raise BootstrapError("PLATFORM_NOT_SUPPORTED", "Advanced AI requires 64-bit Windows")
        estimates = self.manifest["estimates"]
        required = (
            estimates["installed_bytes"]
            + estimates["temporary_bytes"]
            + estimates["safety_margin_bytes"]
        )
        self.root.mkdir(parents=True, exist_ok=True)
        available = shutil.disk_usage(self.root).free
        if available < required:
            raise BootstrapError("INSUFFICIENT_DISK", f"Advanced AI requires {required} free bytes")
        if not self.wheel_path.is_file():
            raise BootstrapError("BOOTSTRAP_PACKAGE_MISSING", "VisionGuard VLM wheel is missing")
        if self.prompts_path is not None and not self.prompts_path.is_dir():
            raise BootstrapError("BOOTSTRAP_PACKAGE_MISSING", "VLM prompt resources are missing")
        gpu = self.gpu_probe()
        return {
            "required_free_bytes": required,
            "available_free_bytes": available,
            "download_bytes": estimates["download_bytes"],
            "installed_bytes": estimates["installed_bytes"],
            **gpu,
        }

    def install(self) -> dict:
        stage: Path | None = None
        started = time.perf_counter()
        timings: dict[str, float] = {}
        try:
            sizing = self.preflight()
            self._sizing = sizing
            env_version = self.manifest["environment_version"]
            stage = self.root / ".staging" / uuid.uuid4().hex[:8]
            env_dir = stage / "e"
            models_dir = stage / "m"
            stage.mkdir(parents=True)
            python_spec = self.manifest["python"]
            archive = self.cache / Path(python_spec["url"]).name
            pip_spec = python_spec["pip_bootstrap"]
            get_pip = self.cache / Path(pip_spec["url"]).name
            self._status("DownloadingRuntime", component="python", **sizing)
            step_started = time.perf_counter()
            for spec, target in ((python_spec, archive), (pip_spec, get_pip)):
                if not target.is_file() or self._sha256(target) != spec["sha256"]:
                    self.downloader(spec["url"], target)
                if (
                    target.stat().st_size != spec["size_bytes"]
                    or self._sha256(target) != spec["sha256"]
                ):
                    raise BootstrapError(
                        "RUNTIME_HASH_MISMATCH", f"verification failed: {target.name}"
                    )
            timings["python_acquire_seconds"] = time.perf_counter() - step_started
            self._status("CreatingEnvironment", component="python", **sizing)
            step_started = time.perf_counter()
            self._extract_python(archive, env_dir)
            python = env_dir / "python.exe"
            if not python.is_file():
                raise BootstrapError(
                    "PYTHON_INSTALL_FAILED", "managed Python executable is missing"
                )
            python_runtime_bytes = self._directory_bytes(env_dir)
            timings["environment_create_seconds"] = time.perf_counter() - step_started
            clean_env = os.environ.copy()
            clean_env.update(
                {
                    "PIP_DISABLE_PIP_VERSION_CHECK": "1",
                    "PYTHONNOUSERSITE": "1",
                    "HF_HOME": str(self.root / "cache" / "huggingface"),
                    "HF_HUB_DISABLE_XET": "1",
                    "TEMP": str(self.cache / "tmp"),
                    "TMP": str(self.cache / "tmp"),
                    "TMPDIR": str(self.cache / "tmp"),
                }
            )
            (self.cache / "tmp").mkdir(parents=True, exist_ok=True)
            indexes = self.manifest["indexes"]
            pip_cache_args = ["--cache-dir", str(self.cache / "pip")]
            pytorch_report = stage / "pytorch-install-report.json"
            runtime_report = stage / "runtime-install-report.json"
            product_report = stage / "visionguard-install-report.json"
            self._status("InstallingDependencies", component="pip", **sizing)
            step_started = time.perf_counter()
            self._run(
                [
                    str(python),
                    str(get_pip),
                    "--index-url",
                    indexes["pypi"],
                    *pip_cache_args,
                    *pip_spec["packages"],
                ],
                env=clean_env,
                state="InstallingDependencies",
                component="pip",
            )
            self._status("InstallingDependencies", component="pytorch", **sizing)
            self._run(
                [
                    str(python),
                    "-m",
                    "pip",
                    "install",
                    "--isolated",
                    "--no-deps",
                    "--index-url",
                    indexes["pytorch"],
                    "--report",
                    str(pytorch_report),
                    *pip_cache_args,
                    *self.manifest["packages"]["pytorch"],
                ],
                env=clean_env,
                state="InstallingDependencies",
                component="pytorch",
            )
            self._run(
                [
                    str(python),
                    "-m",
                    "pip",
                    "install",
                    "--isolated",
                    "--no-deps",
                    "--index-url",
                    indexes["pypi"],
                    "--report",
                    str(runtime_report),
                    *pip_cache_args,
                    *self.manifest["packages"]["runtime"],
                ],
                env=clean_env,
                state="InstallingDependencies",
                component="runtime-dependencies",
            )
            self._run(
                [
                    str(python),
                    "-m",
                    "pip",
                    "install",
                    "--isolated",
                    "--no-deps",
                    "--report",
                    str(product_report),
                    *pip_cache_args,
                    str(self.wheel_path),
                ],
                env=clean_env,
                state="InstallingDependencies",
                component="visionguard-vlm",
            )
            self._run([str(python), "-m", "pip", "check"], env=clean_env)
            timings["dependency_install_seconds"] = time.perf_counter() - step_started
            model_spec = stage / "model-spec.json"
            model_spec.write_text(json.dumps(self.manifest["model"], indent=2), encoding="utf-8")
            model_download_dir = (
                self.cache / "model-download" / self.manifest["model"]["bundle_version"]
            )
            self._status("DownloadingModel", component="model", **sizing)
            step_started = time.perf_counter()
            self._run(
                [
                    str(python),
                    "-m",
                    "visionguard.bootstrap.model_download",
                    "--spec",
                    str(model_spec),
                    "--output",
                    str(model_download_dir),
                ],
                env=clean_env,
                state="DownloadingModel",
                component="model",
            )
            models_dir.parent.mkdir(parents=True, exist_ok=True)
            model_download_dir.replace(models_dir)
            timings["model_download_seconds"] = time.perf_counter() - step_started
            self._status("Validating", component="environment", **sizing)
            step_started = time.perf_counter()
            self._run(
                [
                    str(python),
                    "-c",
                    "import importlib.metadata as m, torch, transformers, visionguard.vlm_runtime; "
                    "assert torch.__version__ == '2.11.0+cu128'; "
                    "assert torch.cuda.is_available(), 'managed PyTorch CUDA is unavailable'; "
                    "assert transformers.__version__ == '4.57.6'; "
                    f"assert m.version('visionguard-moderation') == "
                    f"'{self.manifest['visionguard_package_version']}'",
                ],
                env=clean_env,
            )
            if self.prompts_path is not None:
                self.runtime_validator(python, models_dir, clean_env, stage)
            timings["validation_seconds"] = time.perf_counter() - step_started
            timings["total_install_seconds"] = time.perf_counter() - started
            measurements = {
                "downloaded_artifact_bytes": self._directory_bytes(self.cache, models_dir),
                "managed_python_bytes": python_runtime_bytes,
                "dependency_bytes": max(0, self._directory_bytes(env_dir) - python_runtime_bytes),
                "model_bytes": self._directory_bytes(models_dir),
                "installed_bytes": self._directory_bytes(env_dir, models_dir),
                "observed_peak_bytes": self._directory_bytes(self.root),
            }
            env_target = self.root / "envs" / env_version
            model_target = self.root / "models" / self.manifest["model"]["bundle_version"]
            env_target.parent.mkdir(parents=True, exist_ok=True)
            model_target.parent.mkdir(parents=True, exist_ok=True)
            if env_target.exists() or model_target.exists():
                raise BootstrapError(
                    "VERSION_ALREADY_INSTALLED", "target Advanced AI version already exists"
                )
            env_dir.replace(env_target)
            try:
                models_dir.replace(model_target)
                installed = self._installed_manifest(
                    env_target,
                    model_target,
                    (pytorch_report, runtime_report, product_report),
                    timings,
                    measurements,
                )
                (self.root / "advanced-ai-env.json").write_text(
                    json.dumps(installed, indent=2) + "\n", encoding="utf-8"
                )
                (self.root / "advanced-ai-installed-bom.json").write_text(
                    json.dumps(installed["bom"], indent=2) + "\n", encoding="utf-8"
                )
                self._activate(env_target, model_target)
                shutil.rmtree(self.cache / "pip", ignore_errors=True)
                shutil.rmtree(self.cache / "tmp", ignore_errors=True)
            except Exception:
                shutil.rmtree(env_target, ignore_errors=True)
                shutil.rmtree(model_target, ignore_errors=True)
                raise
            shutil.rmtree(stage, ignore_errors=True)
            self._status("Ready", component="complete", **sizing)
            return installed
        except BootstrapError as exc:
            if stage is not None:
                shutil.rmtree(stage, ignore_errors=True)
            self._status("Failed", error_code=exc.code, error_message=str(exc))
            raise
        except Exception as exc:
            if stage is not None:
                shutil.rmtree(stage, ignore_errors=True)
            wrapped = BootstrapError("BOOTSTRAP_FAILED", f"{type(exc).__name__}: {exc}")
            self._status("Failed", error_code=wrapped.code, error_message=str(wrapped))
            raise wrapped from exc

    def _validate_runtime_startup(
        self, python: Path, models_dir: Path, environment: dict[str, str], stage: Path
    ) -> None:
        token = uuid.uuid4().hex
        config = stage / "runtime-validation.json"
        status = stage / "runtime-validation-status.json"
        config.write_text(
            json.dumps(
                {
                    "host": "127.0.0.1",
                    "port": 0,
                    "model_path": str((models_dir / "vlm").resolve()),
                    "cache_root": str((self.root / "cache/vlm").resolve()),
                    "log_root": str((self.root / "logs/vlm").resolve()),
                    "prompts_dir": str(self.prompts_path),
                    "prompt_version": "v1",
                    "model_bundle_version": self.manifest["model"]["bundle_version"],
                    "model_revision": self.manifest["model"]["revision"],
                    "device": "auto",
                    "dtype": "auto",
                    "timeout_seconds": 120,
                    "load_timeout_seconds": 300,
                    "max_new_tokens": 512,
                }
            ),
            encoding="utf-8",
        )
        child_environment = environment.copy()
        child_environment["VISIONGUARD_VLM_SESSION_TOKEN"] = token
        child_environment["HF_HUB_OFFLINE"] = "1"
        child_environment["TRANSFORMERS_OFFLINE"] = "1"
        child = subprocess.Popen(
            [
                str(python),
                "-m",
                "visionguard.vlm_runtime",
                "--config",
                str(config),
                "--status-file",
                str(status),
            ],
            env=child_environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            deadline = time.monotonic() + 30
            endpoint = None
            while time.monotonic() < deadline:
                if child.poll() is not None:
                    raise BootstrapError("VLM_STARTUP_FAILED", "VLM validation process exited")
                if status.is_file():
                    payload = json.loads(status.read_text(encoding="utf-8"))
                    endpoint = payload.get("endpoint")
                    if payload.get("state") == "failed":
                        raise BootstrapError("VLM_STARTUP_FAILED", "VLM validation status failed")
                    if endpoint:
                        break
                time.sleep(0.2)
            if not endpoint:
                raise BootstrapError("VLM_STARTUP_TIMEOUT", "VLM validation startup timed out")
            with urllib.request.urlopen(f"{endpoint}/health/live", timeout=5) as response:
                health = json.load(response)
            request = urllib.request.Request(
                f"{endpoint}/v1/meta", headers={"X-VisionGuard-Session": token}
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                meta = json.load(response)
            if health.get("status") != "ok" or meta.get("api_version") != 1:
                raise BootstrapError("VLM_CONTRACT_INCOMPATIBLE", "VLM health/meta mismatch")
            shutdown = urllib.request.Request(
                f"{endpoint}/_runtime/shutdown",
                data=b"",
                method="POST",
                headers={"X-VisionGuard-Session": token},
            )
            with urllib.request.urlopen(shutdown, timeout=5):
                pass
            child.wait(timeout=10)
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)

    def _installed_manifest(
        self,
        env_dir: Path,
        model_dir: Path,
        reports: tuple[Path, ...],
        timings: dict[str, float],
        measurements: dict[str, int],
    ) -> dict:
        script = (
            "import importlib.metadata as m,json;"
            "print(json.dumps(sorted((d.metadata['Name'],d.version) "
            "for d in m.distributions())))"
        )
        result = self.runner(
            [str(env_dir / "python.exe"), "-c", script],
            check=True,
            capture_output=True,
            text=True,
        )
        packages = [
            {"name": name, "version": version} for name, version in json.loads(result.stdout)
        ]
        acquisitions = []
        for report_path in reports:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            for item in report.get("install", []):
                download = item.get("download_info", {})
                source = str(download.get("url", ""))
                if not source.startswith("https://"):
                    source = "bundled://visionguard-vlm-wheel"
                acquisitions.append(
                    {
                        "name": item.get("metadata", {}).get("name"),
                        "version": item.get("metadata", {}).get("version"),
                        "source": source,
                        "hash": download.get("archive_info", {}).get("hash"),
                    }
                )
        return {
            "schema_version": 1,
            "environment_version": self.manifest["environment_version"],
            "python_version": self.manifest["python"]["version"],
            "packages": packages,
            "model": {
                key: self.manifest["model"][key]
                for key in ("id", "revision", "source", "bundle_version")
            },
            "installed_at": datetime.now(UTC).isoformat(),
            "sources": self.manifest["indexes"],
            "hardware_validation": {
                key: self._sizing[key]
                for key in ("gpu_name", "gpu_memory_mib", "gpu_driver_version")
                if key in self._sizing
            },
            "acquisitions": acquisitions,
            "timings": timings,
            "measurements": measurements,
            "bom": {
                "bomFormat": "CycloneDX",
                "specVersion": "1.6",
                "version": 1,
                "components": [{"type": "library", **item} for item in packages]
                + [
                    {
                        "type": "machine-learning-model",
                        "name": self.manifest["model"]["id"],
                        "version": self.manifest["model"]["revision"],
                    }
                ],
            },
        }

    def _activate(self, env_dir: Path, model_dir: Path) -> None:
        components = self.data_dir / "components"
        components.mkdir(parents=True, exist_ok=True)
        active = components / "components.json"
        previous = components / "components.previous.json"
        if active.is_file():
            shutil.copy2(active, previous)

        def relative(path: Path) -> str:
            return path.relative_to(self.data_dir).as_posix()

        registry = {
            "schema_version": 2,
            "distribution_mode": "online_bootstrap",
            "environment_version": self.manifest["environment_version"],
            "python_executable": relative(env_dir / "python.exe"),
            "vlm_models_version": self.manifest["model"]["bundle_version"],
            "vlm_models_directory": relative(model_dir),
            "model_revision": self.manifest["model"]["revision"],
            "visionguard_package_version": self.manifest["visionguard_package_version"],
        }
        temporary = active.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
        temporary.replace(active)


def installed_package_version() -> str:
    try:
        return metadata.version("visionguard-moderation")
    except metadata.PackageNotFoundError:
        return "source"
