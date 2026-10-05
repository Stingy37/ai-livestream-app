"""Unified caller for local LLMs. Owned by the RAG team.

Shared: other teams may import from here.

Two backends, one call site. Both are driven exactly like the OpenAI client:

    from models.local_llm_api import MODEL, get_client

    client = get_client()  # BACKEND ("vllm") unless you pass "hf"
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=256,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
    resp.choices[0].message.content

or, for the common case, ``chat(messages, **kwargs) -> str``.

    vllm ... an ``openai.OpenAI`` client pointed at the local vLLM server. Start and
             stop that server with scripts/vllm_start.sh and scripts/vllm_stop.sh.
             Use this backend for the pipeline: every scene process shares the one
             server instead of loading its own copy of the weights.
    hf ..... loads the weights in *this* process with Hugging Face transformers,
             straight onto the GPU, and exposes the same ``chat.completions.create``
             surface. The loaded ``model`` and ``tokenizer`` are reachable on the
             client for poking at internals from a notebook. Each process that
             uses it holds its own ~16 GB copy, so keep it out of multi-process runs.

Qwen3 thinks by default (in both backends). Pass
``extra_body={"chat_template_kwargs": {"enable_thinking": False}}`` to turn it off.
When it is on, the reasoning comes back separately on ``message.reasoning`` (or
``delta.reasoning`` when streaming) and ``content`` holds only the answer. As with
vLLM, ``reasoning`` is only present when there is some, so read it with
``getattr(message, "reasoning", None)``.

Configuration is the constants below the imports; edit them there.

Nothing is loaded or connected at import time; ``get_client`` builds each backend
on first use and reuses it for the rest of the process.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from openai import OpenAI
from openai.types import CompletionUsage
from openai.types.chat import ChatCompletion, ChatCompletionChunk, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice
from openai.types.chat.chat_completion_chunk import Choice as ChunkChoice
from openai.types.chat.chat_completion_chunk import ChoiceDelta

if TYPE_CHECKING:
    from transformers import PreTrainedModel, PreTrainedTokenizerBase

# Keep MODEL_PATH, MODEL, the port in BASE_URL, and MAX_MODEL_LEN in step with
# scripts/vllm_start.sh (LOCAL_LLM_MODEL_PATH, LOCAL_LLM_MODEL, VLLM_PORT,
# LOCAL_LLM_MAX_MODEL_LEN).
BACKEND = "vllm"                                  # default for get_client(): "vllm" or "hf"
USER = "andyshi2"
MODEL_PATH = f"/home/{USER}/pre-models/Qwen3-8B"  # weights folder (hf backend)
MODEL = "qwen3-8b"                                # name callers pass as model=
BASE_URL = "http://127.0.0.1:8000/v1"             # vLLM server
MAX_MODEL_LEN = 8192                              # prompt + completion token budget

_THINK_OPEN = "<think>"
_THINK_CLOSE = "</think>"


# ─────────────────────────────────────────────────────────────────────────────
# Public entry points
# ─────────────────────────────────────────────────────────────────────────────

_clients: dict[str, OpenAI | HFClient] = {}
_clients_lock = threading.Lock()


def get_client(backend: str | None = None) -> OpenAI | HFClient:
    """Return this process's client for ``backend`` (default ``BACKEND``).

    The first call per backend builds it (for "hf", that loads the weights onto
    the GPU); later calls return the same object.
    """
    backend = backend or BACKEND
    with _clients_lock:
        client = _clients.get(backend)
        if client is None or (isinstance(client, HFClient) and client.closed):
            if backend == "vllm":
                # vLLM does not check the key, but the client insists on one.
                client = OpenAI(base_url=BASE_URL, api_key="EMPTY")
            elif backend == "hf":
                client = HFClient(MODEL_PATH, served_model_name=MODEL)
            else:
                raise ValueError(f"unknown local LLM backend {backend!r}; expected 'vllm' or 'hf'")
            _clients[backend] = client
        return client


def chat(messages: list[dict[str, Any]], *, backend: str | None = None, **kwargs: Any) -> str:
    """Send one chat request and return just the answer text.

    ``kwargs`` are passed through to ``chat.completions.create`` (temperature,
    max_tokens, extra_body, ...).
    """
    resp = get_client(backend).chat.completions.create(model=MODEL, messages=messages, **kwargs)
    return resp.choices[0].message.content or ""


# ─────────────────────────────────────────────────────────────────────────────
# Hugging Face backend
# ─────────────────────────────────────────────────────────────────────────────


class HFClient:
    """In-process transformers model behind an OpenAI-shaped ``chat.completions.create``.

    Supports the parameters the pipeline uses: ``messages``, ``temperature``,
    ``top_p``, ``max_tokens`` / ``max_completion_tokens``, ``stop``, ``seed``,
    ``stream``, and in ``extra_body``: ``chat_template_kwargs``, ``top_k``,
    ``min_p``, ``repetition_penalty``. Anything else raises rather than being
    silently ignored. Unset sampling parameters fall back to the model's
    generation_config.json, which is what vLLM does too.

    Requests are served one at a time; concurrent callers wait their turn.
    """

    def __init__(self, model_path: str, *, served_model_name: str) -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        if not torch.cuda.is_available():
            raise RuntimeError("the hf backend needs a CUDA GPU")

        self.model_path = model_path
        self.served_model_name = served_model_name
        self.tokenizer: PreTrainedTokenizerBase = AutoTokenizer.from_pretrained(model_path)
        # device_map puts each tensor on the GPU as it is read from the safetensors
        # shards, so the full model never sits in CPU RAM (the box has very little).
        self.model: PreTrainedModel = AutoModelForCausalLM.from_pretrained(
            model_path,
            dtype=torch.bfloat16,
            device_map="cuda",
        )
        self.model.eval()
        self.closed = False
        self._lock = threading.Lock()
        self.chat = _Chat(self)

    def close(self) -> None:
        """Drop the weights and release their GPU memory."""
        import gc

        import torch

        self.closed = True
        del self.model
        gc.collect()
        torch.cuda.empty_cache()

    # The pieces chat.completions.create is built from.

    def _prepare(self, request: dict[str, Any]) -> tuple[Any, dict[str, Any], bool]:
        """Turn an OpenAI-style request into (input_ids, generate kwargs, thinking)."""
        import torch
        from transformers import GenerationConfig

        if self.closed:
            raise RuntimeError("this HFClient has been closed")

        request = dict(request)
        model = request.pop("model", None)
        if model not in (None, self.served_model_name):
            raise ValueError(f"model {model!r} is not loaded; this client serves {self.served_model_name!r}")
        messages = request.pop("messages")
        n = request.pop("n", None)
        if n not in (None, 1):
            raise NotImplementedError("the hf backend only supports n=1")

        extra_body = dict(request.pop("extra_body", None) or {})
        template_kwargs = extra_body.pop("chat_template_kwargs", None) or {}
        # Qwen3's chat template thinks unless told otherwise; mirror that here.
        thinking = template_kwargs.get("enable_thinking", True)

        # Start from the model's own defaults, then layer the request on top.
        gen_config = GenerationConfig.from_dict(self.model.generation_config.to_dict())
        sampling = {
            "temperature": request.pop("temperature", None),
            "top_p": request.pop("top_p", None),
            "top_k": extra_body.pop("top_k", None),
            "min_p": extra_body.pop("min_p", None),
            "repetition_penalty": extra_body.pop("repetition_penalty", None),
        }
        for name, value in sampling.items():
            if value is not None:
                setattr(gen_config, name, value)
        if gen_config.temperature == 0:  # OpenAI's spelling of greedy decoding
            gen_config.do_sample = False
            # generate() refills None from the model's sampling defaults and then warns
            # they are unused; transformers' own neutral values keep it quiet.
            gen_config.temperature, gen_config.top_p, gen_config.top_k, gen_config.min_p = 1.0, 1.0, 50, None

        input_ids = self.tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,
            return_tensors="pt",
            return_dict=True,
            **template_kwargs,
        )["input_ids"].to(self.model.device)
        prompt_len = input_ids.shape[-1]
        if prompt_len >= MAX_MODEL_LEN:
            raise ValueError(f"prompt is {prompt_len} tokens; MAX_MODEL_LEN is {MAX_MODEL_LEN}")

        max_tokens = request.pop("max_completion_tokens", None) or request.pop("max_tokens", None)
        request.pop("max_tokens", None)
        # Like vLLM: with no limit given, generate until the context is full.
        gen_config.max_new_tokens = min(max_tokens or MAX_MODEL_LEN, MAX_MODEL_LEN - prompt_len)
        gen_config.max_length = None

        stop = request.pop("stop", None)
        if isinstance(stop, str):
            stop = [stop]
        if stop:
            gen_config.stop_strings = stop

        seed = request.pop("seed", None)
        if seed is not None:
            torch.manual_seed(seed)

        unsupported = sorted(set(request) | set(extra_body))
        if unsupported:
            raise NotImplementedError(f"the hf backend does not support: {', '.join(unsupported)}")

        generate_kwargs = {
            "input_ids": input_ids,
            "attention_mask": torch.ones_like(input_ids),
            "generation_config": gen_config,
            "tokenizer": self.tokenizer,  # needed by stop_strings
        }
        return input_ids, generate_kwargs, thinking

    def _create(self, request: dict[str, Any]) -> ChatCompletion:
        import torch

        input_ids, generate_kwargs, thinking = self._prepare(request)
        gen_config = generate_kwargs["generation_config"]
        with self._lock, torch.inference_mode():
            output = self.model.generate(**generate_kwargs)

        new_tokens = output[0, input_ids.shape[-1]:].tolist()
        eos_ids = set(_as_list(gen_config.eos_token_id))
        hit_eos = bool(new_tokens) and new_tokens[-1] in eos_ids
        text = self.tokenizer.decode(new_tokens, skip_special_tokens=True)
        text, hit_stop = _trim_stop(text, gen_config.stop_strings)
        reasoning, content = _split_reasoning(text, thinking)

        finish_reason = "stop" if hit_eos or hit_stop else "length"
        message = ChatCompletionMessage(role="assistant", content=content)
        if reasoning is not None:
            message.reasoning = reasoning
        return ChatCompletion(
            id=f"chatcmpl-{uuid.uuid4().hex}",
            object="chat.completion",
            created=int(time.time()),
            model=self.served_model_name,
            choices=[Choice(index=0, finish_reason=finish_reason, message=message)],
            usage=CompletionUsage(
                prompt_tokens=input_ids.shape[-1],
                completion_tokens=len(new_tokens),
                total_tokens=input_ids.shape[-1] + len(new_tokens),
            ),
        )

    def _stream(self, request: dict[str, Any]) -> Iterator[ChatCompletionChunk]:
        import torch
        from transformers import StoppingCriteria, StoppingCriteriaList, TextIteratorStreamer

        input_ids, generate_kwargs, thinking = self._prepare(request)
        gen_config = generate_kwargs["generation_config"]
        streamer = TextIteratorStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True)

        # Lets the caller abandon the stream (break out of the loop, or an
        # exception) without generate() running on in the background.
        cancelled = threading.Event()

        class _StopWhenCancelled(StoppingCriteria):
            def __call__(self, input_ids: torch.Tensor, scores: torch.Tensor, **kwargs: Any) -> torch.Tensor:
                return torch.full((input_ids.shape[0],), cancelled.is_set(), dtype=torch.bool, device=input_ids.device)

        generate_kwargs["stopping_criteria"] = StoppingCriteriaList([_StopWhenCancelled()])
        completion_id = f"chatcmpl-{uuid.uuid4().hex}"
        created = int(time.time())

        def chunk(delta: ChoiceDelta, finish_reason: str | None = None) -> ChatCompletionChunk:
            return ChatCompletionChunk(
                id=completion_id,
                object="chat.completion.chunk",
                created=created,
                model=self.served_model_name,
                choices=[ChunkChoice(index=0, delta=delta, finish_reason=finish_reason)],
            )

        result: dict[str, Any] = {}

        def run() -> None:
            try:
                with torch.inference_mode():
                    result["output"] = self.model.generate(**generate_kwargs, streamer=streamer)
            except BaseException as exc:
                result["error"] = exc
                streamer.end()

        with self._lock:
            worker = threading.Thread(target=run, daemon=True)
            worker.start()
            try:
                yield chunk(ChoiceDelta(role="assistant", content=""))
                # Re-split the whole text each time and send only what is new, so a
                # tag that straddles two streamer pieces is still routed correctly.
                text = ""
                sent_reasoning = sent_content = 0
                for piece in streamer:
                    text += piece
                    reasoning, content = _split_reasoning(_trim_stop(text, gen_config.stop_strings)[0], thinking)
                    reasoning, content = reasoning or "", content or ""
                    new_reasoning, new_content = reasoning[sent_reasoning:], content[sent_content:]
                    sent_reasoning, sent_content = len(reasoning), len(content)
                    # Like vLLM, a delta only carries the fields that have new text.
                    delta = ChoiceDelta()
                    if new_reasoning:
                        delta.reasoning = new_reasoning
                    if new_content:
                        delta.content = new_content
                    if new_reasoning or new_content:
                        yield chunk(delta)
            finally:
                cancelled.set()  # no-op if generation already finished
                worker.join()

        if "error" in result:
            raise result["error"]
        new_tokens = result["output"][0, input_ids.shape[-1]:].tolist()
        hit_eos = bool(new_tokens) and new_tokens[-1] in set(_as_list(gen_config.eos_token_id))
        hit_stop = _trim_stop(text, gen_config.stop_strings)[1]
        yield chunk(ChoiceDelta(), finish_reason="stop" if hit_eos or hit_stop else "length")


class _Chat:
    def __init__(self, client: HFClient) -> None:
        self.completions = _Completions(client)


class _Completions:
    def __init__(self, client: HFClient) -> None:
        self._client = client

    def create(self, *, stream: bool = False, **request: Any) -> ChatCompletion | Iterator[ChatCompletionChunk]:
        if stream:
            return self._client._stream(request)
        return self._client._create(request)


def _split_reasoning(text: str, thinking: bool) -> tuple[str | None, str | None]:
    """Split Qwen3 output into (reasoning, answer), as vLLM's qwen3 reasoning parser does.

    With thinking on, everything before ``</think>`` is reasoning; output cut off
    before the tag closes is all reasoning.
    """
    if not thinking:
        return None, text
    text = text.removeprefix(_THINK_OPEN)
    reasoning, closed, content = text.partition(_THINK_CLOSE)
    if not closed:
        return reasoning or None, None
    return reasoning or None, content or None


def _trim_stop(text: str, stop_strings: list[str] | None) -> tuple[str, bool]:
    """Cut ``text`` at the first stop string. OpenAI never includes the stop string."""
    cuts = [i for s in stop_strings or () if (i := text.find(s)) != -1]
    if not cuts:
        return text, False
    return text[: min(cuts)], True


def _as_list(value: int | list[int] | None) -> list[int]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]
