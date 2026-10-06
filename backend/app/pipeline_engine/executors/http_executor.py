import json

import httpx

from app.pipeline_engine.errors import NodeExecutionError


class HttpExecutor:
    type = "http"

    async def run(self, rendered_config: dict) -> dict:
        method = rendered_config["method"]
        url = rendered_config["url"]
        headers = rendered_config.get("headers") or {}
        body = rendered_config.get("body")
        timeout = rendered_config.get("timeout_seconds", 30)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.request(method, url, headers=headers, content=body)
        except httpx.ConnectError as e:
            raise NodeExecutionError(f"http connection error: {e}", retryable=True) from e
        except httpx.TimeoutException as e:
            raise NodeExecutionError(f"http timeout: {e}", retryable=True) from e

        status = resp.status_code
        resp_headers = dict(resp.headers)
        text = resp.text
        try:
            parsed = resp.json()
        except (json.JSONDecodeError, ValueError):
            parsed = text

        if 400 <= status < 500:
            raise NodeExecutionError(
                f"http {status}: {text[:200]}",
                retryable=False,
                details={"status": status, "headers": resp_headers, "body": parsed},
            )
        if status >= 500:
            raise NodeExecutionError(
                f"http {status}: {text[:200]}",
                retryable=True,
                details={"status": status, "headers": resp_headers, "body": parsed},
            )

        return {"status": status, "headers": resp_headers, "body": parsed}
