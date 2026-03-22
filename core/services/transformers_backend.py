"""HuggingFace Transformers fallback backend for GGUF models with unsupported architectures.

Used when llama-cpp-python raises 'unknown model architecture' (e.g. qwen35).
The GGUF file is dequantized on load, so RAM usage is higher and inference is
slower than llama-cpp-python — this is a temporary workaround.
"""

import logging
import time
import uuid
from pathlib import Path
from threading import Thread
from typing import Any, Generator

logger = logging.getLogger(__name__)


def _register_gguf_architecture_aliases() -> None:
    """
    Patch the transformers GGUF loader to recognise architectures it's missing.

    qwen3.5 GGUF files report general.architecture = 'qwen35'. Transformers 5.x
    knows 'qwen3_5' (with underscore). Three separate registries must be patched:

    1. GGUF_TO_TRANSFORMERS_MAPPING["config"] — field-name mapping used by
       load_gguf_checkpoint to translate GGUF tensor names to transformers names.
    2. GGUF_SUPPORTED_ARCHITECTURES — a list built once at import time from the
       dict keys; load_gguf_checkpoint checks the list, not the dict.
    3. CONFIG_MAPPING — used by AutoConfig.for_model() / AutoTokenizer.from_pretrained()
       to map model_type strings to config classes.
    """
    try:
        import transformers.modeling_gguf_pytorch_utils as gguf_utils
        from transformers.modeling_gguf_pytorch_utils import GGUF_TO_TRANSFORMERS_MAPPING

        # ── 1 & 2: GGUF field mapping + supported-architectures list ──────────
        cfg = GGUF_TO_TRANSFORMERS_MAPPING["config"]
        if "qwen35" not in cfg:
            # Prefer qwen3_5 (Transformers 5.x) over qwen3 (older)
            source_arch = next(
                (k for k in ("qwen3_5", "qwen3") if k in cfg), None
            )
            if source_arch:
                cfg["qwen35"] = cfg[source_arch]
                if "qwen35" not in gguf_utils.GGUF_SUPPORTED_ARCHITECTURES:
                    gguf_utils.GGUF_SUPPORTED_ARCHITECTURES.append("qwen35")
                logger.debug(
                    f"Registered 'qwen35' in GGUF mapping as alias for '{source_arch}'"
                )

        # ── 3: AutoConfig / AutoTokenizer registry ────────────────────────────
        # AutoTokenizer.from_pretrained reads model_type="qwen35" from the GGUF
        # and calls AutoConfig.for_model(model_type="qwen35"), which fails unless
        # CONFIG_MAPPING knows "qwen35".
        from transformers.models.auto.configuration_auto import CONFIG_MAPPING

        if "qwen35" not in CONFIG_MAPPING:
            config_source = next(
                (k for k in ("qwen3_5", "qwen3") if k in CONFIG_MAPPING), None
            )
            if config_source:
                config_cls = CONFIG_MAPPING[config_source]
                # _LazyConfigMapping stores custom entries in _extra_content
                if hasattr(CONFIG_MAPPING, "_extra_content"):
                    CONFIG_MAPPING._extra_content["qwen35"] = config_cls
                else:
                    CONFIG_MAPPING["qwen35"] = config_cls
                logger.debug(
                    f"Registered 'qwen35' in CONFIG_MAPPING as alias for '{config_source}'"
                )

        # ── 4: GGUF fast-tokenizer converter registry ─────────────────────────
        # convert_gguf_tokenizer() in transformers/integrations/ggml.py looks up
        # GGUF_TO_FAST_CONVERTERS[architecture] to convert raw GGUF token data
        # into a HuggingFace fast tokenizer. "qwen35" must be registered here too.
        from transformers.integrations.ggml import GGUF_TO_FAST_CONVERTERS

        if "qwen35" not in GGUF_TO_FAST_CONVERTERS:
            converter_source = next(
                (k for k in ("qwen3_5", "qwen3") if k in GGUF_TO_FAST_CONVERTERS), None
            )
            if converter_source:
                GGUF_TO_FAST_CONVERTERS["qwen35"] = GGUF_TO_FAST_CONVERTERS[converter_source]
                logger.debug(
                    f"Registered 'qwen35' in GGUF_TO_FAST_CONVERTERS as alias for '{converter_source}'"
                )

        # ── 5: gguf-py MODEL_ARCH_NAMES — used by get_gguf_hf_weights_map ────
        # get_gguf_hf_weights_map (transformers) searches MODEL_ARCH_NAMES for an
        # entry whose value equals hf_model.config.model_type. Qwen3_5Config has
        # model_type = "qwen3_5_text". gguf-py 0.18 maps MODEL_ARCH.QWEN35 → "qwen35".
        # We remap it to "qwen3_5_text" so the weight-name lookup succeeds.
        # get_tensor_name_map(MODEL_ARCH.QWEN35, n) still works correctly after this.
        try:
            from gguf import MODEL_ARCH, MODEL_ARCH_NAMES
            if (
                hasattr(MODEL_ARCH, "QWEN35")
                and MODEL_ARCH_NAMES.get(MODEL_ARCH.QWEN35) != "qwen3_5_text"
            ):
                MODEL_ARCH_NAMES[MODEL_ARCH.QWEN35] = "qwen3_5_text"
                logger.debug("Updated MODEL_ARCH_NAMES[QWEN35] to 'qwen3_5_text'")
        except Exception as e:
            logger.warning(f"Could not update gguf-py MODEL_ARCH_NAMES: {e}")

    except Exception as e:
        logger.warning(f"Could not register GGUF architecture aliases: {e}")


# Parameters that llama-cpp-python supports but transformers does not.
_UNSUPPORTED_PARAMS = frozenset({
    "tools", "tool_choice", "response_format",
    "logprobs", "top_logprobs",
    "presence_penalty", "frequency_penalty",
    "n",
})


class TransformersLlama:
    """
    Drop-in replacement for llama_cpp.Llama for models with unsupported architectures.

    Implements the same create_chat_completion() interface so the rest of the
    inference pipeline (model_cache, inference_service) requires no changes.
    """

    def __init__(
        self,
        model_path: str,
        model_id: str | None = None,
        n_ctx: int = 4096,
        n_gpu_layers: int = 0,
        n_threads: int | None = None,
        embedding: bool = False,
        **_: Any,
    ) -> None:
        if embedding:
            raise NotImplementedError(
                "TransformersLlama does not support embedding mode; "
                "use a dedicated embedding model."
            )

        gguf_path = Path(model_path)
        if not gguf_path.exists():
            raise FileNotFoundError(f"GGUF file not found: {model_path}")

        # Ensure architectures like qwen35 are recognised before any from_pretrained call
        _register_gguf_architecture_aliases()

        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        device = "cuda" if n_gpu_layers > 0 and torch.cuda.is_available() else "cpu"
        # bfloat16 is safer than float16 on CPU (avoids NaN on non-AVX512 hardware)
        dtype = torch.bfloat16

        logger.info(
            f"Loading model {model_id or gguf_path.name} via TransformersLlama backend "
            f"from {gguf_path} (device={device}, dtype={dtype})"
        )

        if n_threads is not None:
            torch.set_num_threads(n_threads)

        parent_dir = str(gguf_path.parent)
        filename = gguf_path.name

        self.tokenizer = self._load_tokenizer(AutoTokenizer, parent_dir, filename)
        self.model = self._load_model(
            AutoModelForCausalLM, parent_dir, filename, dtype, device
        )

        self.device = device
        self.dtype = dtype
        self.n_ctx = n_ctx
        self.model_path = model_path
        self._model_id = model_id or gguf_path.name

        logger.info(
            f"TransformersLlama loaded {self._model_id} (dtype={dtype}, device={device})"
        )

    # ── Private loaders ──────────────────────────────────────────────────────

    def _load_tokenizer(
        self, AutoTokenizer: Any, parent_dir: str, filename: str
    ) -> Any:
        try:
            return AutoTokenizer.from_pretrained(
                parent_dir,
                gguf_file=filename,
                local_files_only=True,
            )
        except Exception as e:
            logger.error(f"TransformersLlama: failed to load tokenizer from {parent_dir}/{filename}: {e}")
            raise RuntimeError(
                f"Model '{filename}' could not be loaded locally. "
                "Please visit the Models page to download the model."
            ) from e

    def _load_model(
        self,
        AutoModelForCausalLM: Any,
        parent_dir: str,
        filename: str,
        dtype: Any,
        device: str,
    ) -> Any:
        try:
            return AutoModelForCausalLM.from_pretrained(
                parent_dir,
                gguf_file=filename,
                torch_dtype=dtype,
                local_files_only=True,
            ).to(device)
        except Exception as e:
            logger.error(f"TransformersLlama: failed to load model from {parent_dir}/{filename}: {e}")
            raise RuntimeError(
                f"Model '{filename}' could not be loaded locally. "
                "Please visit the Models page to download the model."
            ) from e

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _apply_chat_template(self, messages: list[dict]) -> str:
        """Apply the model's chat template; fall back to a simple format if unavailable."""
        try:
            return self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
        except Exception as e:
            logger.warning(
                f"TransformersLlama: chat template unavailable for {self._model_id} ({e}), "
                "falling back to simple USER/ASSISTANT format"
            )
            parts = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "system":
                    parts.append(f"System: {content}")
                elif role == "user":
                    parts.append(f"User: {content}")
                elif role == "assistant":
                    parts.append(f"Assistant: {content}")
            parts.append("Assistant:")
            return "\n".join(parts)

    def _build_generate_kwargs(self, kwargs: dict) -> dict:
        """Map create_chat_completion kwargs → model.generate() kwargs."""
        import torch

        temperature = float(kwargs.get("temperature", 0.7))
        top_p = float(kwargs.get("top_p", 1.0))
        top_k = int(kwargs.get("top_k", 50))
        max_tokens = int(kwargs.get("max_tokens", 512))
        seed = kwargs.get("seed")

        if seed is not None:
            torch.manual_seed(int(seed))

        for key in kwargs:
            if key in _UNSUPPORTED_PARAMS:
                logger.debug(f"TransformersLlama: ignoring unsupported param '{key}'")

        gen_kwargs: dict[str, Any] = {"max_new_tokens": max_tokens}

        if temperature > 0:
            gen_kwargs["do_sample"] = True
            gen_kwargs["temperature"] = temperature
            gen_kwargs["top_p"] = top_p
            gen_kwargs["top_k"] = top_k
        else:
            gen_kwargs["do_sample"] = False  # greedy

        return gen_kwargs

    @staticmethod
    def _truncate_stop(text: str, stop: Any) -> str:
        """Truncate text at the first occurrence of any stop sequence."""
        if not stop:
            return text
        stop_list = [stop] if isinstance(stop, str) else stop
        for seq in stop_list:
            idx = text.find(seq)
            if idx != -1:
                text = text[:idx]
        return text

    # ── Public interface (mirrors llama_cpp.Llama) ───────────────────────────

    def create_chat_completion(
        self,
        messages: list[dict],
        functions: Any = None,  # noqa: ARG002 — mirrors llama_cpp.Llama interface
        extra_body: Any = None,
        stream: bool = False,
        **kwargs: Any,
    ):
        """
        Run chat completion; mirrors llama_cpp.Llama.create_chat_completion().

        extra_body: dict passed as 3rd positional arg by inference_service.py's
                    non-streaming run_in_executor call — merged into kwargs.
        stream: bool — if True, returns a generator of chunk dicts.
        """
        # Merge extra_body dict (non-streaming run_in_executor calling convention)
        if isinstance(extra_body, dict):
            merged: dict[str, Any] = {**extra_body, **kwargs}
        else:
            merged = dict(kwargs)

        # stream may be inside extra_body
        stream = bool(merged.pop("stream", stream))
        stop = merged.get("stop")

        logger.debug(
            f"TransformersLlama generate: {len(messages)} messages, "
            f"max_new_tokens={merged.get('max_tokens', 512)}, stream={stream}"
        )

        prompt = self._apply_chat_template(messages)
        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            truncation=True,
            max_length=self.n_ctx,
        ).to(self.device)
        prompt_tokens: int = inputs["input_ids"].shape[1]
        gen_kwargs = self._build_generate_kwargs(merged)

        if stream:
            return self._stream(inputs, gen_kwargs, stop, prompt_tokens)
        return self._generate(inputs, gen_kwargs, stop, prompt_tokens)

    # ── Generation implementations ───────────────────────────────────────────

    def _generate(
        self,
        inputs: dict,
        gen_kwargs: dict,
        stop: Any,
        prompt_tokens: int,
    ) -> dict:
        """Blocking (non-streaming) generation."""
        import torch

        completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        created = int(time.time())

        try:
            with torch.inference_mode():
                output_ids = self.model.generate(**inputs, **gen_kwargs)
        except RuntimeError as e:
            if "out of memory" in str(e).lower():
                raise RuntimeError(
                    "TransformersLlama OOM during generation — "
                    "reduce max_tokens or use a smaller model"
                ) from e
            raise

        new_ids = output_ids[0][prompt_tokens:]
        text = self.tokenizer.decode(new_ids, skip_special_tokens=True)
        text = self._truncate_stop(text, stop)
        completion_tokens = int(new_ids.shape[0])

        if not text:
            logger.warning(
                f"TransformersLlama: empty generation output for {self._model_id}"
            )

        finish_reason = (
            "length" if completion_tokens >= gen_kwargs["max_new_tokens"] else "stop"
        )
        logger.info(
            f"TransformersLlama generation complete: "
            f"{prompt_tokens} prompt, {completion_tokens} completion tokens"
        )

        return {
            "id": completion_id,
            "object": "chat.completion",
            "created": created,
            "model": self.model_path,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": finish_reason,
                }
            ],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }

    def _stream(
        self,
        inputs: dict,
        gen_kwargs: dict,
        stop: Any,
        prompt_tokens: int,
    ) -> Generator[dict, None, None]:
        """Streaming generation via TextIteratorStreamer."""
        import torch
        from transformers import TextIteratorStreamer

        completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        created = int(time.time())
        error_holder: list[Exception] = []

        streamer = TextIteratorStreamer(
            self.tokenizer,
            skip_prompt=True,
            skip_special_tokens=True,
        )
        thread_kwargs = {**inputs, **gen_kwargs, "streamer": streamer}

        def _run() -> None:
            try:
                with torch.inference_mode():
                    self.model.generate(**thread_kwargs)
            except Exception as e:
                error_holder.append(e)
            finally:
                # Always unblock the streamer iterator, even on error
                try:
                    streamer.text_queue.put(streamer.stop_signal)
                except Exception:
                    pass

        thread = Thread(target=_run, daemon=True)
        thread.start()

        accumulated = ""
        completion_tokens = 0
        stop_list = (
            ([stop] if isinstance(stop, str) else list(stop)) if stop else []
        )

        try:
            for token_text in streamer:
                if error_holder:
                    break

                accumulated += token_text
                completion_tokens += 1

                # Check stop sequences on the accumulated buffer
                stop_hit = any(seq in accumulated for seq in stop_list)

                yield {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": self.model_path,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": token_text},
                            "finish_reason": None,
                        }
                    ],
                }

                if stop_hit:
                    break

        except Exception as e:
            error_holder.append(e)

        # Final chunk signals end of stream
        finish_reason = (
            "length" if completion_tokens >= gen_kwargs["max_new_tokens"] else "stop"
        )
        yield {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": self.model_path,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": ""},
                    "finish_reason": finish_reason,
                }
            ],
        }

        thread.join(timeout=5)

        if error_holder:
            exc = error_holder[0]
            if "out of memory" in str(exc).lower():
                raise RuntimeError(
                    "TransformersLlama OOM during generation — "
                    "reduce max_tokens or use a smaller model"
                ) from exc
            raise RuntimeError(
                f"TransformersLlama streaming error: {exc}"
            ) from exc

        logger.info(
            f"TransformersLlama generation complete: "
            f"{prompt_tokens} prompt, {completion_tokens} completion tokens"
        )
