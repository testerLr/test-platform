import asyncio

import redis

from app.pipeline_engine.errors import NodeExecutionError


class RedisExecutor:
    type = "redis"

    async def run(self, rendered_config: dict) -> dict:
        conn = rendered_config["connection"]
        operation = rendered_config["operation"]
        if operation != "set":
            raise NodeExecutionError(f"unsupported operation {operation!r}", retryable=False)

        client = redis.Redis(
            host=conn["host"],
            port=conn["port"],
            password=conn.get("password"),
            db=conn.get("db", 0),
            decode_responses=True,
        )
        try:
            key = rendered_config["key"]
            value = rendered_config["value"]
            ttl = rendered_config.get("ttl_seconds", 0)

            def _do_set():
                if ttl > 0:
                    return client.set(key, value, ex=ttl)
                return client.set(key, value)

            ok = await asyncio.to_thread(_do_set)
            if not ok:
                raise NodeExecutionError(f"redis SET returned falsy for key {key!r}", retryable=False)
            return {"key": key, "operation": "set"}
        except redis.ConnectionError as e:
            raise NodeExecutionError(f"redis connection error: {e}", retryable=True) from e
        except redis.RedisError as e:
            raise NodeExecutionError(f"redis error: {e}", retryable=False) from e
        finally:
            await asyncio.to_thread(client.close)
