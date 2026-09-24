from __future__ import annotations

from threading import Lock
from time import perf_counter

from visionguard.moderation.policy import ModerationPolicy
from visionguard.vlm.config import VLMConfig
from visionguard.vlm.providers.local import LocalVLMProvider
from visionguard.vlm.schemas import VLMContext


class LazyVLMService:
    """Construct the model once on first inference and retain it until process exit."""

    def __init__(self, config) -> None:
        self.config = config
        self._provider = None
        self._lock = Lock()
        self.state = "installed"
        self.model_init_count = 0
        self.model_load_ms = 0.0

    @property
    def loaded(self) -> bool:
        return self._provider is not None

    def _load(self):
        if self._provider is not None:
            return self._provider
        with self._lock:
            if self._provider is not None:
                return self._provider
            self.state = "loading"
            started = perf_counter()
            settings = VLMConfig(
                provider="local",
                model_name_or_path=str(self.config.model_path),
                model_revision=self.config.model_revision,
                device=self.config.device,
                dtype=self.config.dtype,
                max_new_tokens=self.config.max_new_tokens,
                timeout_seconds=self.config.timeout_seconds,
                local_files_only=True,
                cache_dir=self.config.cache_root,
                prompts_dir=self.config.prompts_dir,
                artifacts_dir=self.config.log_root,
                prompt_version=self.config.prompt_version,
            )
            try:
                self._provider = LocalVLMProvider(settings)
            except Exception:
                self.state = "failed"
                raise
            self.model_init_count += 1
            self.model_load_ms = (perf_counter() - started) * 1000
            self.state = "ready"
            return self._provider

    def analyze(self, image, context: VLMContext, policy: ModerationPolicy):
        return self._load().analyze(image, context, policy)
