"""Qwen3-VL backend, isolated from all upstream inference engines."""

import logging
import os
from time import perf_counter

from visionguard.vlm.exceptions import VLMInferenceError, VLMProviderLoadError, VLMTimeoutError
from visionguard.vlm.retry import StructuredProvider

LOGGER = logging.getLogger(__name__)


class LocalVLMProvider(StructuredProvider):
    def __init__(self, config) -> None:
        super().__init__(config)
        try:
            # Plain HTTP transfers avoid Windows Xet hangs; callers may explicitly override.
            os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
            os.environ.setdefault("HF_HOME", str(config.cache_dir.resolve()))
            import torch
            from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

            self.torch = torch
            self.device = (
                ("cuda:0" if torch.cuda.is_available() else "cpu")
                if config.device == "auto"
                else config.device
            )
            if config.dtype == "auto":
                self.dtype = (
                    torch.bfloat16
                    if self.device.startswith("cuda") and torch.cuda.is_bf16_supported()
                    else (torch.float16 if self.device.startswith("cuda") else torch.float32)
                )
            else:
                self.dtype = getattr(torch, config.dtype)
            LOGGER.info(
                "Loading local VLM model=%s device=%s dtype=%s",
                config.model_name_or_path,
                self.device,
                self.dtype,
            )
            self.processor = AutoProcessor.from_pretrained(
                config.model_name_or_path,
                cache_dir=str(config.cache_dir),
                trust_remote_code=False,
                revision=config.model_revision,
            )
            self.model = (
                Qwen3VLForConditionalGeneration.from_pretrained(
                    config.model_name_or_path,
                    cache_dir=str(config.cache_dir),
                    dtype=self.dtype,
                    attn_implementation="sdpa",
                    trust_remote_code=False,
                    revision=config.model_revision,
                )
                .to(self.device)
                .eval()
            )
            if config.warmup_enabled:
                from PIL import Image

                self.generate(
                    Image.new("RGB", (112, 112), "white"),
                    "Describe this image.",
                    perf_counter() + config.timeout_seconds,
                )
                LOGGER.info("VLM warmup completed")
        except Exception as exc:
            raise VLMProviderLoadError(
                f"provider=local model={config.model_name_or_path} "
                f"prompt={config.prompt_version} loading failed"
            ) from exc

    def generate(self, image, prompt, deadline):
        from transformers import StoppingCriteria, StoppingCriteriaList

        torch = self.torch

        class DeadlineStop(StoppingCriteria):
            def __call__(self, input_ids, scores, **kwargs):
                return perf_counter() >= deadline

        try:
            messages = [
                {"role": "system", "content": [{"type": "text", "text": self.builder.system}]},
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": image},
                        {"type": "text", "text": prompt},
                    ],
                },
            ]
            inputs = self.processor.apply_chat_template(
                messages,
                tokenize=True,
                add_generation_prompt=True,
                return_dict=True,
                return_tensors="pt",
            ).to(self.device)
            input_tokens = inputs["input_ids"].shape[-1]
            if perf_counter() >= deadline:
                raise VLMTimeoutError("VLM tokenization deadline exceeded")
            options = {
                "max_new_tokens": self.config.max_new_tokens,
                "do_sample": self.config.temperature > 0,
                "stopping_criteria": StoppingCriteriaList([DeadlineStop()]),
            }
            if self.config.temperature > 0:
                options["temperature"] = self.config.temperature
            with torch.inference_mode():
                output = self.model.generate(**inputs, **options)
            if self.device.startswith("cuda"):
                torch.cuda.synchronize()
            if perf_counter() >= deadline:
                raise VLMTimeoutError("VLM generation deadline exceeded")
            generated = output[:, input_tokens:]
            raw = self.processor.batch_decode(generated, skip_special_tokens=True)[0]
            return raw, {
                "input_tokens": input_tokens,
                "output_tokens": generated.shape[-1],
                "device": self.device,
                "dtype": str(self.dtype),
                "model_revision": getattr(getattr(self.model, "config", None), "_commit_hash", None)
                or self.config.model_revision,
            }
        except VLMTimeoutError:
            raise
        except Exception as exc:
            raise VLMInferenceError(
                f"provider=local model={self.config.model_name_or_path} "
                f"prompt={self.config.prompt_version} generation failed"
            ) from exc
