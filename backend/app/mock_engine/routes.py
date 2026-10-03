import asyncio
import json

from fastapi import APIRouter, Request, Response

from app.mock_engine import get_engine
from app.mock_engine.renderer import render

router = APIRouter()

_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]


async def _handle(request: Request) -> Response:
    body_bytes = await request.body()
    body_text = body_bytes.decode("utf-8", errors="replace")
    headers = {k: v for k, v in request.headers.items()}
    headers.pop("host", None)
    headers.pop("content-length", None)
    query = {k: v for k, v in request.query_params.items()}
    full_path = "/" + request.path_params["full_path"]

    engine = get_engine()
    matched = engine.find(
        request.method,
        full_path,
        query=query,
        headers=headers,
        body_text=body_text,
    )
    if not matched:
        return Response(
            content=json.dumps({"detail": "Mock not found"}),
            media_type="application/json",
            status_code=404,
        )

    mock = matched.mock
    if mock.delay_ms:
        await asyncio.sleep(mock.delay_ms / 1000)

    rendered_headers = {
        k: render(v, path_params=matched.path_params, query=query, headers=headers, body_text=body_text)
        for k, v in (mock.response_headers or {}).items()
    }
    rendered_body = render(
        mock.response_body,
        path_params=matched.path_params,
        query=query,
        headers=headers,
        body_text=body_text,
    )
    content_type = rendered_headers.pop("Content-Type", "application/json")
    return Response(content=rendered_body, headers=rendered_headers, media_type=content_type, status_code=mock.response_status)


for method in _METHODS:
    router.add_api_route(
        path="/m/{full_path:path}",
        endpoint=_handle,
        methods=[method],
    )
