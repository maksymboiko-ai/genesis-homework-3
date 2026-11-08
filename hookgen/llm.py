"""OpenRouter client: one chat call -> validated Generation, with one retry on bad output."""

import json
import os
import re
import time
from dataclasses import dataclass, field

import httpx
from pydantic import ValidationError

from .prompt import build_messages
from .schema import Generation

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "deepseek/deepseek-v4.1-flash"  # eval winner, see evals/RESULTS.md
FALLBACK_MODEL = "z-ai/glm-5.3-flash"  # eval runner-up: 3x cheaper, 2x faster
TIMEOUT_S = 90


class LLMError(Exception):
    """Raised with a message that is safe to show to the user."""


@dataclass
class CallResult:
    generation: Generation
    model: str
    cost_usd: float = 0.0
    latency_s: float = 0.0
    attempts: int = 1
    raw: list[str] = field(default_factory=list)


def model_from_env() -> str:
    return os.getenv("HOOKGEN_MODEL") or DEFAULT_MODEL


def _extract_json(text: str) -> dict:
    """Accept bare JSON or JSON wrapped in ``` fences / surrounding prose."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in model output")
    return json.loads(text[start:end + 1])


def chat(messages: list[dict], model: str, *, temperature: float = 0.9, max_tokens: int = 12000,
         json_mode: bool = True, reasoning_effort: str = "low",
         client: httpx.Client | None = None) -> tuple[str, float]:
    """Single OpenRouter call. Returns (content, cost_usd).

    Many cheap models now reason before answering; reasoning tokens count against max_tokens, so we keep
    effort low (ignored by non-reasoning models) and leave generous headroom.
    """
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise LLMError("OPENROUTER_API_KEY is not set. Put it in .env or run with MOCK_LLM=1.")
    body = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens,
            "usage": {"include": True}, "reasoning": {"effort": reasoning_effort, "exclude": True}}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    headers = {"Authorization": f"Bearer {key}", "X-Title": "SockLock Hook Lab"}
    own = client is None
    client = client or httpx.Client(timeout=TIMEOUT_S)
    try:
        r = client.post(OPENROUTER_URL, json=body, headers=headers)
    except httpx.TimeoutException as e:
        raise LLMError(f"Model {model} timed out after {TIMEOUT_S}s") from e
    except httpx.HTTPError as e:
        raise LLMError(f"Network error calling OpenRouter: {e}") from e
    finally:
        if own:
            client.close()
    if r.status_code != 200:
        try:
            msg = r.json().get("error", {}).get("message", r.text[:300])
        except ValueError:
            msg = r.text[:300]
        raise LLMError(f"OpenRouter returned {r.status_code}: {msg}")
    data = r.json()
    if "error" in data:
        raise LLMError(f"OpenRouter error: {data['error'].get('message', data['error'])}")
    try:
        choice = data["choices"][0]
        content = choice["message"]["content"] or ""
    except (KeyError, IndexError) as e:
        raise LLMError("OpenRouter response had no message content") from e
    cost = float((data.get("usage") or {}).get("cost") or 0.0)
    if not content.strip() and choice.get("finish_reason") == "length":
        raise LLMError(f"Model {model} hit the token limit before answering (cost ${cost:.4f})")
    return content, cost


def generate(script: str, n_variants: int = 10, *, hook_types: list[str] | None = None,
             notes: str | None = None, facts: str | None = None, model: str | None = None,
             temperature: float = 0.9) -> CallResult:
    """Generate variants; retries once if the output is not valid JSON in the expected shape."""
    model = model or model_from_env()
    if os.getenv("MOCK_LLM") == "1":
        return _mock(n_variants, model)
    messages = build_messages(script, n_variants, hook_types, notes, facts)
    total_cost, raws, last_err = 0.0, [], None
    t0 = time.perf_counter()
    for attempt in (1, 2):
        content, cost = chat(messages, model, temperature=temperature)
        total_cost += cost
        raws.append(content)
        try:
            gen = Generation.model_validate(_extract_json(content))
            return CallResult(gen, model, total_cost, time.perf_counter() - t0, attempt, raws)
        except (ValueError, ValidationError) as e:
            last_err = e
            messages = messages + [
                {"role": "assistant", "content": content},
                {"role": "user", "content": "That was not valid JSON in the required shape "
                                            f"({str(e)[:200]}). Return ONLY the JSON object."},
            ]
    raise LLMError(f"Model {model} returned invalid output twice: {str(last_err)[:200]}")


def _mock(n: int, model: str) -> CallResult:
    from .mock import mock_generation
    return CallResult(mock_generation(n), f"mock:{model}", 0.0, 0.0, 1, [])
