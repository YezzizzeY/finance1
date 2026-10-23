"""The model behind a harness session: one chat-completions request per turn, with the pilot's retry rules and request log.

  vllm      our server at 127.0.0.1:<VLLM_PORT_<MODEL>>/v1/chat/completions; body = the S1 harness body (sampling, seed, token ids,
            thinking on); waits out 429 / 5xx / an unreachable server for up to give_up_after_s
  deepseek  chat completions; each turn's reasoning_content is sent back on the assistant message that carries its tool calls
            (DeepSeek's thinking-with-tools protocol), looked up by the turn's first tool-call id
  kimi      the same protocol, plus reasoning_effort, at most max_concurrent requests in flight, every response body kept
A 4xx answer is retried twice, then the session fails. API keys are read from the environment variable named by api_key_env.
make_chat(model, ctx) returns the session's chat(messages, tools, seed) -> choice; every request is logged in ctx["requests"],
together with the first user message and the latest tool messages as sent (ctx["sent_user"], ctx["sent_tool_msgs"]).
"""
from __future__ import annotations

import contextlib
import json
import os
import threading
import time

import requests

from finagent import config
from finagent.harness.session import Chat

_SEMAPHORES: dict[str, threading.BoundedSemaphore] = {}
_SEM_LOCK = threading.Lock()
API_LABEL = {"deepseek": "DeepSeek", "kimi": "Moonshot"}


class ServerUnavailable(RuntimeError):
    pass


# ================================================================================================== vLLM
def vllm_body(model_id: str, messages: list[dict], tools: list[dict], seed: int, h: dict) -> dict:
    """The S1 harness request body (key order as sent)."""
    return {"model": model_id, "messages": messages, "tools": tools, "tool_choice": "auto", "temperature": h["temperature"],
            "top_p": h["top_p"], "max_tokens": h["max_tokens"], "seed": seed, "return_token_ids": True,
            "chat_template_kwargs": {"enable_thinking": True}}


def vllm_choice(url: str, body: dict, timeout: float, give_up_after_s: float) -> dict:
    """The first choice, with the prompt and generated token ids as _prompt_ids / _gen_ids."""
    t0 = time.time(); attempt = 0; client_err = 0
    while True:
        try:
            r = requests.post(url, json=body, timeout=timeout)
            if r.status_code == 429 or r.status_code >= 500:
                raise requests.ConnectionError(f"server busy / error {r.status_code}: {r.text[:200]}")
            if r.status_code >= 400:
                client_err += 1
                if client_err >= 3:
                    raise RuntimeError(f"vLLM {r.status_code}: {r.text[:300]}")
                time.sleep(3 * client_err); continue
            j = r.json(); ch = j["choices"][0]
            ch["_prompt_ids"] = j.get("prompt_token_ids") or ch.get("prompt_token_ids"); ch["_gen_ids"] = ch.get("token_ids")
            return ch
        except (requests.ConnectionError, requests.Timeout) as e:
            if time.time() - t0 > give_up_after_s:
                raise ServerUnavailable(f"server unavailable for {give_up_after_s} s: {e}")
            attempt += 1; time.sleep(min(120, 5 * 2 ** min(attempt, 5)))


def _vllm_usage(ch: dict, model_id: str) -> dict:
    return {"input": len(ch.get("_prompt_ids") or []), "output": len(ch.get("_gen_ids") or []), "reasoning": None, "cached": None,
            "model": model_id}


# ================================================================================================== DeepSeek / Kimi
def _semaphore(key: str, n: int | None):
    if n is None:
        return contextlib.nullcontext()
    with _SEM_LOCK:
        return _SEMAPHORES.setdefault(key, threading.BoundedSemaphore(n))


def api_choice(key: str, messages: list[dict], tools: list[dict], reasoning: dict, ctx: dict) -> dict:
    """The first choice, with usage and reported model as _usage / _model; stores the turn's reasoning_content in `reasoning`."""
    m = config.MODELS[key]; h = m["harness"]; label = API_LABEL[m["provider"]]
    api_key = os.environ.get(m["api_key_env"])
    if not api_key:
        raise RuntimeError(f"set {m['api_key_env']} in the environment to call {label}")
    body_msgs = []
    for x in messages:
        x2 = dict(x)
        if x.get("role") == "assistant" and x.get("tool_calls"):
            rc = reasoning.get(x["tool_calls"][0].get("id"))
            if rc is not None:
                x2["reasoning_content"] = rc
        body_msgs.append(x2)
    body = {"model": m["model_id"], "messages": body_msgs, "tools": tools, "tool_choice": "auto", "max_tokens": h["max_tokens"]}
    if "reasoning_effort" in h:
        body["reasoning_effort"] = h["reasoning_effort"]
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    sem = _semaphore(key, h.get("max_concurrent"))
    t0, client_err, attempt = time.time(), 0, 0
    while True:
        try:
            with sem:
                r = requests.post(h["endpoint"], json=body, timeout=h["timeout_s"], headers=headers)
            if h.get("keep_raw_responses"):
                ctx.setdefault("raw_responses", []).append({"status": r.status_code, "t": time.time(), "body": r.text})
            if r.status_code == 429 or r.status_code >= 500:
                raise requests.ConnectionError(f"{label} busy / error {r.status_code}: {r.text[:200]}")
            if r.status_code >= 400:
                client_err += 1
                if client_err >= 3:
                    raise RuntimeError(f"{label} {r.status_code}: {r.text[:300]}")
                time.sleep(3 * client_err); continue
            j = r.json(); ch = j["choices"][0]; msg = ch["message"]
            if msg.get("tool_calls") and msg.get("reasoning_content"):
                reasoning[msg["tool_calls"][0]["id"]] = msg["reasoning_content"]
            ch["_usage"], ch["_model"] = j.get("usage"), j.get("model")
            return ch
        except (requests.ConnectionError, requests.Timeout) as e:
            if time.time() - t0 > h["give_up_after_s"]:
                raise RuntimeError(f"{label} unavailable for an hour: {e}")
            attempt += 1; time.sleep(min(120, 5 * 2 ** min(attempt, 5)))


def _deepseek_usage(ch: dict) -> dict:
    u = ch.get("_usage") or {}
    return {"input": u.get("prompt_tokens"), "output": u.get("completion_tokens"),
            "reasoning": (u.get("completion_tokens_details") or {}).get("reasoning_tokens"),
            "cached": u.get("prompt_cache_hit_tokens"), "model": ch.get("_model")}


def _kimi_usage(ch: dict) -> dict:
    u = ch.get("_usage") or {}
    pd_ = u.get("prompt_tokens_details") or {}
    return {"input": u.get("prompt_tokens"), "output": u.get("completion_tokens"),
            "reasoning": (u.get("completion_tokens_details") or {}).get("reasoning_tokens"),
            "cached": u.get("cached_tokens") if u.get("cached_tokens") is not None else pd_.get("cached_tokens"),
            "cache_write": pd_.get("cache_write_tokens"), "usage": u, "model": ch.get("_model")}


# ================================================================================================== the session's chat
def make_chat(key: str, ctx: dict) -> Chat:
    """chat(messages, tools, seed) -> choice for one session of model `key`, logging every request in ctx."""
    m = config.MODELS[key]; h = m["harness"]
    reasoning: dict[str, str] = {}                                            # tool-call id -> reasoning_content (APIs)
    url = f"http://{config.EXPERIMENT['vllm']['host']}:{config.port('VLLM', key)}/v1/chat/completions" if m["provider"] == "vllm" else None

    def call(messages: list[dict], tools: list[dict], seed: int) -> tuple[dict, dict]:
        if m["provider"] == "vllm":
            ch = vllm_choice(url, vllm_body(m["model_id"], messages, tools, seed, h), h["timeout_s"], h["give_up_after_s"])
            if h.get("keep_raw_choices"):
                raw = {k: v for k, v in ch.items() if k not in ("_prompt_ids", "_gen_ids", "prompt_token_ids")}
                ctx.setdefault("raw_choices", []).append(json.loads(json.dumps(raw, default=str)))
            return ch, _vllm_usage(ch, m["model_id"])
        ch = api_choice(key, messages, tools, reasoning, ctx)
        return ch, (_kimi_usage if m["provider"] == "kimi" else _deepseek_usage)(ch)

    def chat(messages: list[dict], tools: list[dict], seed: int) -> dict:
        t0 = time.time()
        ch, rec = call(messages, tools, seed)
        rec.update({"finish": ch.get("finish_reason"), "s": round(time.time() - t0, 2)})
        ctx["requests"].append(rec)
        ctx.setdefault("sent_user", next((x.get("content") for x in messages if x.get("role") == "user"), None))
        ctx["sent_tool_msgs"] = [{"name": x.get("name"), "content": x.get("content")} for x in messages if x.get("role") == "tool"]
        return ch
    return chat
