"""Local HTTP relay between a coding agent and its model (the only TCP port the agent's sandbox may connect to).

  * forwards every request to --upstream (path and query unchanged) and streams the answer back chunk by chunk;
  * holds the API key: the incoming Authorization header is dropped and, with --key-env NAME, replaced by 'Bearer $NAME' read
    from the relay's own environment at start (the agent and its commands never have the key; the key is never logged);
  * logs every request: <log-dir>/requests.jsonl (time, run id from the X-Cxp-Run header -- 'NO_RUN_HEADER' when missing, e.g.
    a command of the agent calling the relay --, method, path, status, sizes, model, token usage parsed from the Responses API
    'response.completed' event or a JSON body), and the full request body and answer in <log-dir>/<run>/<seq>_{req.json,resp.txt}
    (the agent's own payloads; they never contain the key).
Bound to 127.0.0.1 only; imports nothing from finagent (finagent.coding.codex starts and stops it).

    python -m finagent.coding.relay --port 18592 --upstream https://api.deepseek.com --key-env DEEPSEEK_API_KEY \
        --log-dir runs/pilot/relay/deepseek [--max-concurrent N]
"""
from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import os
import time
from pathlib import Path

import aiohttp
from aiohttp import web

HOP = {"host", "content-length", "transfer-encoding", "connection", "keep-alive", "authorization", "accept-encoding", "upgrade",
       "proxy-authorization", "te", "trailer"}
RUN_HEADER = "x-cxp-run"
NO_RUN_HEADER = "NO_RUN_HEADER"
MAX_SAVED_BYTES = 64 * 2 ** 20                                                # of one answer, in <seq>_resp.txt
SEQ = itertools.count(1)


def usage_from(text: str) -> tuple[dict | None, str | None]:
    """(usage, model) from a Responses API SSE stream or a JSON body."""
    usage = model = None
    if "data:" in text:
        for ln in text.splitlines():
            if not ln.startswith("data:"):
                continue
            s = ln[5:].strip()
            if not s or s == "[DONE]":
                continue
            try:
                j = json.loads(s)
            except json.JSONDecodeError:
                continue
            r = j.get("response") if isinstance(j, dict) else None
            if isinstance(r, dict):
                usage = r.get("usage") or usage; model = r.get("model") or model
            elif isinstance(j, dict) and j.get("usage"):
                usage = j["usage"]; model = j.get("model") or model
    else:
        try:
            j = json.loads(text)
            if isinstance(j, dict):
                usage, model = j.get("usage"), j.get("model")
        except json.JSONDecodeError:
            pass
    return usage, model


class Relay:
    def __init__(self, upstream: str, key: str | None, log_dir: Path, max_concurrent: int | None = None):
        self.upstream = upstream.rstrip("/")
        self.sem = asyncio.Semaphore(max_concurrent) if max_concurrent else None   # upstream requests in flight (None: no cap)
        self.key = key
        self.log_dir = log_dir; log_dir.mkdir(parents=True, exist_ok=True)
        self.session: aiohttp.ClientSession | None = None
        self.lock = asyncio.Lock()

    async def start(self, app):
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=None, sock_connect=60, sock_read=1800),
                                             auto_decompress=True)

    async def stop(self, app):
        await self.session.close()

    async def log(self, rec: dict):
        async with self.lock:
            with open(self.log_dir / "requests.jsonl", "a") as f:
                f.write(json.dumps(rec) + "\n")

    async def handle(self, req: web.Request) -> web.StreamResponse:
        seq = next(SEQ); t0 = time.time()
        run = req.headers.get(RUN_HEADER, NO_RUN_HEADER)
        run = "".join(c for c in run if c.isalnum() or c in "-_")[:80] or NO_RUN_HEADER
        body = await req.read()
        headers = {k: v for k, v in req.headers.items() if k.lower() not in HOP and k.lower() != RUN_HEADER}
        if self.key:
            headers["Authorization"] = f"Bearer {self.key}"
        url = self.upstream + req.rel_url.path_qs
        rd = self.log_dir / run; rd.mkdir(parents=True, exist_ok=True)
        try:
            (rd / f"{seq:05d}_req.json").write_bytes(body)
        except OSError:
            pass
        rec = {"seq": seq, "t0": t0, "run": run, "method": req.method, "path": req.rel_url.path, "req_bytes": len(body)}
        try:
            j = json.loads(body) if body else {}
            rec["req_model"] = j.get("model"); rec["n_input_items"] = len(j.get("input") or j.get("messages") or [])
            rec["stream"] = bool(j.get("stream"))
        except (json.JSONDecodeError, AttributeError):
            pass
        chunks, n = [], 0
        if self.sem is not None:
            await self.sem.acquire()
        try:
            async with self.session.request(req.method, url, data=body if body else None, headers=headers) as up:
                resp = web.StreamResponse(status=up.status)
                for k, v in up.headers.items():
                    if k.lower() not in HOP and k.lower() != "content-encoding":
                        resp.headers[k] = v
                await resp.prepare(req)
                # Codex closes the connection as soon as it has read response.completed, while Moonshot (and at times DeepSeek)
                # still sends a last chunk: the rest of the upstream answer is still read and saved, the request is logged with
                # the upstream status, and client_closed_early notes the early close.
                gone = None
                async for chunk in up.content.iter_any():
                    n += len(chunk)
                    if n <= MAX_SAVED_BYTES:
                        chunks.append(chunk)
                    if gone is None:
                        try:
                            await resp.write(chunk)
                        except ConnectionResetError as e:
                            gone = f"{type(e).__name__}: {str(e)[:120]}"
                if gone is None:
                    try:
                        await resp.write_eof()
                    except ConnectionResetError as e:
                        gone = f"{type(e).__name__}: {str(e)[:120]}"
                if gone is not None:
                    rec["client_closed_early"] = gone
                rec["status"] = up.status
        except Exception as e:                                                # noqa: BLE001  (logged and answered with 502)
            rec["status"] = "relay_error"; rec["error"] = f"{type(e).__name__}: {str(e)[:300]}"
            resp = web.Response(status=502, text=json.dumps({"error": {"message": rec["error"]}}), content_type="application/json")
        finally:
            if self.sem is not None:
                self.sem.release()
        text = b"".join(chunks).decode("utf-8", "replace")
        try:
            (rd / f"{seq:05d}_resp.txt").write_text(text)
        except OSError:
            pass
        rec["usage"], rec["model"] = usage_from(text)
        rec["resp_bytes"] = n; rec["t1"] = time.time()
        await self.log(rec)
        return resp


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--upstream", required=True)
    ap.add_argument("--key-env", default=None, help="environment variable holding the upstream API key")
    ap.add_argument("--log-dir", required=True)
    ap.add_argument("--max-concurrent", type=int, default=None)
    a = ap.parse_args(argv)
    key = os.environ.get(a.key_env) if a.key_env else None
    if a.key_env and not key:
        raise SystemExit(f"environment variable {a.key_env} is empty")
    if a.key_env:
        os.environ.pop(a.key_env, None)                                       # kept only in the Relay object from here on
    r = Relay(a.upstream, key, Path(a.log_dir), a.max_concurrent)
    app = web.Application(client_max_size=256 * 2 ** 20)
    app.on_startup.append(r.start); app.on_cleanup.append(r.stop)
    app.router.add_route("*", "/{tail:.*}", r.handle)
    web.run_app(app, host="127.0.0.1", port=a.port, print=None, access_log=None)


if __name__ == "__main__":
    main()
