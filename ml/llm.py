"""Optional local LLM, with a zero-cost default of "no LLM".

Set ML_LLM_URL to an OpenAI-compatible server running on this machine. No API
key and no paid host:

  ollama serve
  ML_LLM_URL=http://127.0.0.1:11434/v1 ML_LLM_MODEL=llama3.2

  llama-server -m model.gguf --port 8080
  ML_LLM_URL=http://127.0.0.1:8080/v1 ML_LLM_MODEL=local

If ML_LLM_URL is unset or the call fails, callers fall back to extractive methods.
"""
from __future__ import annotations

import json
import os
import urllib.request


def llm_available() -> bool:
    return bool(os.getenv("ML_LLM_URL"))


def chat_complete(messages: list[dict], max_tokens: int = 300, timeout: float = 30) -> str | None:
    url = os.getenv("ML_LLM_URL")
    if not url:
        return None
    body = json.dumps({"model": os.getenv("ML_LLM_MODEL", "llama3.2"), "messages": messages,
                       "max_tokens": max_tokens, "temperature": 0.2}).encode()
    req = urllib.request.Request(url.rstrip("/") + "/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    key = os.getenv("ML_LLM_API_KEY")
    if key:
        req.add_header("Authorization", f"Bearer {key}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read())
        return data["choices"][0]["message"]["content"].strip() or None
    except Exception:
        return None
