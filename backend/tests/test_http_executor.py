import json

import httpx
import pytest

from app.pipeline_engine.errors import NodeExecutionError
from app.pipeline_engine.executors import http_executor as mod
from app.pipeline_engine.executors.http_executor import HttpExecutor


def _handler_200(request):
    return httpx.Response(200, json={"ok": True, "echo": request.content.decode() if request.content else ""})


def _handler_500(request):
    return httpx.Response(500, text="oops")


def _handler_404(request):
    return httpx.Response(404, text="nope")


def _patch_httpx(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    orig_client = httpx.AsyncClient

    def factory(*a, **kw):
        kw["transport"] = transport
        return orig_client(*a, **kw)

    monkeypatch.setattr(mod.httpx, "AsyncClient", factory)


async def test_http_executor_success(monkeypatch):
    _patch_httpx(monkeypatch, _handler_200)
    exe = HttpExecutor()
    out = await exe.run({
        "method": "POST",
        "url": "http://x/y",
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"a": 1}),
        "timeout_seconds": 5,
    })
    assert out["status"] == 200
    assert out["body"]["ok"] is True


async def test_http_executor_4xx_not_retryable(monkeypatch):
    _patch_httpx(monkeypatch, _handler_404)
    exe = HttpExecutor()
    with pytest.raises(NodeExecutionError) as exc:
        await exe.run({"method": "GET", "url": "http://x/y", "timeout_seconds": 5})
    assert exc.value.retryable is False


async def test_http_executor_5xx_retryable(monkeypatch):
    _patch_httpx(monkeypatch, _handler_500)
    exe = HttpExecutor()
    with pytest.raises(NodeExecutionError) as exc:
        await exe.run({"method": "GET", "url": "http://x/y", "timeout_seconds": 5})
    assert exc.value.retryable is True
