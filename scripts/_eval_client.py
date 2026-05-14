"""Minimal GitHub Models API client — stdlib urllib only.

Requires GITHUB_TOKEN env var with models:read scope.
Gate call sites with XANAD_EVAL_ENABLED=1 before using in tests.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import NamedTuple

_ENDPOINT = "https://models.github.ai/inference/chat/completions"
_API_VERSION = "2026-03-10"


class CallResult(NamedTuple):
    content: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    model: str


def call(
    messages: list[dict],
    model: str,
    *,
    temperature: float = 0.0,
    max_tokens: int = 512,
) -> CallResult:
    """Send a chat completion request and return content + usage metadata.

    Raises RuntimeError if GITHUB_TOKEN is unset.
    Raises urllib.error.HTTPError on non-2xx responses.
    """
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise RuntimeError(
            "GITHUB_TOKEN is not set. Provide a token with models:read scope."
        )

    payload = json.dumps({
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }).encode("utf-8")

    req = urllib.request.Request(
        _ENDPOINT,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": _API_VERSION,
        },
        method="POST",
    )

    t0 = time.perf_counter_ns()
    with urllib.request.urlopen(req) as resp:
        body = json.loads(resp.read())
    latency_ms = round((time.perf_counter_ns() - t0) / 1e6, 1)

    usage = body.get("usage", {})
    return CallResult(
        content=body["choices"][0]["message"]["content"],
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
        latency_ms=latency_ms,
        model=body.get("model", model),
    )
