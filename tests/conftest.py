"""Shared test fixtures: no network at all, and a scripted HTTP transport that replays the golden model replies."""
from __future__ import annotations

import socket

import pytest
import requests


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Every socket connect fails: no test may reach a model, a server or the internet."""
    def refuse(*args, **kwargs):
        raise OSError("network access is blocked in the tests")
    monkeypatch.setattr(socket.socket, "connect", refuse)


class FakeTransport:
    """requests' HTTPAdapter.send replaced: answers with the scripted replies in order and records every request sent.
    A reply {"error": ...} raises requests.ConnectionError; with repeat_last the last reply repeats forever."""

    def __init__(self):
        self.replies, self.repeat_last, self.sent = [], False, []

    def load(self, replies: list[dict], repeat_last: bool = False) -> None:
        self.replies, self.repeat_last, self.sent = list(replies), repeat_last, []

    def send(self, request, timeout=None, **kwargs):
        headers = {k: "<redacted>" if k.lower() == "authorization" else v for k, v in request.headers.items()}
        body = request.body.decode("utf-8") if isinstance(request.body, bytes) else request.body
        self.sent.append({"method": request.method, "url": request.url, "headers": headers, "timeout": timeout, "body": body})
        reply = self.replies[0] if self.repeat_last and len(self.replies) == 1 else self.replies.pop(0)
        if "error" in reply:
            raise requests.ConnectionError(reply["error"])
        r = requests.Response()
        r.status_code, r._content, r.encoding = reply["status"], reply["body"].encode("utf-8"), "utf-8"
        r.url, r.request = request.url, request
        return r


@pytest.fixture
def fake_http(monkeypatch):
    transport = FakeTransport()
    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", lambda adapter, request, **kw: transport.send(request, **kw))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "DUMMY")
    monkeypatch.setenv("MOONSHOT_API_KEY", "DUMMY")
    return transport
