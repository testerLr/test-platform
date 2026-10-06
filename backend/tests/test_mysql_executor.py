import pytest

from app.pipeline_engine.errors import NodeExecutionError
from app.pipeline_engine.executors.mysql_executor import MySQLExecutor, _named_to_positional


def test_named_to_positional_replaces_in_order():
    sql = "INSERT INTO x (a, b) VALUES (%(a)s, %(b)s)"
    out = _named_to_positional(sql, ["a", "b"])
    assert out == "INSERT INTO x (a, b) VALUES (%s, %s)"


async def test_mysql_executor_connection_error_is_retryable(monkeypatch):
    import asyncmy

    async def _boom(*a, **kw):
        raise asyncmy.errors.OperationalError(2003, "can't connect")

    class FakeMod:
        errors = asyncmy.errors
        connect = staticmethod(_boom)

    monkeypatch.setattr("app.pipeline_engine.executors.mysql_executor.asyncmy", FakeMod)

    exe = MySQLExecutor()
    rendered = {
        "connection": {"host": "h", "port": 3306, "user": "u", "password": "p", "database": "d"},
        "sql": "SELECT 1", "params": {},
    }
    with pytest.raises(NodeExecutionError) as exc:
        await exe.run(rendered)
    assert exc.value.retryable is True


async def test_mysql_executor_sql_error_not_retryable(monkeypatch):
    import asyncmy

    class FakeConn:
        def cursor(self):
            return FakeCursor()
        async def ensure_closed(self):
            return None

    class FakeCursor:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return None
        async def execute(self, sql, params=None):
            raise asyncmy.errors.ProgrammingError(1064, "syntax error")
        @property
        def rowcount(self): return 0
        @property
        def lastrowid(self): return None

    async def _connect(*a, **kw):
        return FakeConn()

    class FakeMod:
        errors = asyncmy.errors
        connect = staticmethod(_connect)

    monkeypatch.setattr("app.pipeline_engine.executors.mysql_executor.asyncmy", FakeMod)

    exe = MySQLExecutor()
    rendered = {
        "connection": {"host": "h", "port": 3306, "user": "u", "password": "p", "database": "d"},
        "sql": "BAD", "params": {},
    }
    with pytest.raises(NodeExecutionError) as exc:
        await exe.run(rendered)
    assert exc.value.retryable is False