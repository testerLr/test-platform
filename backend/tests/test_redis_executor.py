import pytest

from app.pipeline_engine.errors import NodeExecutionError
from app.pipeline_engine.executors import redis_executor as mod
from app.pipeline_engine.executors.redis_executor import RedisExecutor


class FakeRedis:
    def __init__(self, **kw):
        self.kw = kw
        self.closed = False

    def set(self, key, value, ex=None):
        self.last = {"key": key, "value": value, "ex": ex}
        return True

    def close(self):
        self.closed = True


async def test_redis_executor_success(monkeypatch):
    monkeypatch.setattr(mod.redis, "Redis", FakeRedis)
    exe = RedisExecutor()
    out = await exe.run({
        "connection": {"host": "h", "port": 6379, "db": 0},
        "operation": "set",
        "key": "k",
        "value": "v",
        "ttl_seconds": 60,
    })
    assert out == {"key": "k", "operation": "set"}


async def test_redis_executor_connection_error_retryable(monkeypatch):
    import redis as _redis

    class BrokenRedis(FakeRedis):
        def set(self, *a, **kw):
            raise _redis.ConnectionError("nope")

    monkeypatch.setattr(mod.redis, "Redis", BrokenRedis)
    exe = RedisExecutor()
    with pytest.raises(NodeExecutionError) as exc:
        await exe.run({
            "connection": {"host": "h", "port": 6379, "db": 0},
            "operation": "set",
            "key": "k",
            "value": "v",
            "ttl_seconds": 0,
        })
    assert exc.value.retryable is True


async def test_redis_executor_rejects_non_set(monkeypatch):
    monkeypatch.setattr(mod.redis, "Redis", FakeRedis)
    exe = RedisExecutor()
    with pytest.raises(NodeExecutionError) as exc:
        await exe.run({
            "connection": {"host": "h", "port": 6379, "db": 0},
            "operation": "hset",
            "key": "k",
            "value": "v",
        })
    assert exc.value.retryable is False
