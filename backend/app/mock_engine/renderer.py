import json
import random
import uuid
from datetime import datetime, timezone

from jinja2 import Environment, StrictUndefined

_ENV = Environment(
    autoescape=False,
    undefined=StrictUndefined,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return str(uuid.uuid4())


def _randint(a: int, b: int) -> int:
    return random.randint(a, b)


def render(
    text: str,
    *,
    path_params: dict[str, str],
    query: dict[str, str],
    headers: dict[str, str],
    body_text: str,
) -> str:
    body = None
    if body_text:
        try:
            body = json.loads(body_text)
        except json.JSONDecodeError:
            body = None

    class _BodyProxy:
        def __init__(self, data):
            self._data = data or {}

        def __getattr__(self, key):
            value = self._data.get(key)
            if isinstance(value, dict):
                return _BodyProxy(value)
            if value is None and key not in self._data:
                raise AttributeError(key)
            return value

    request = {
        "path": _BodyProxy(path_params),
        "query": _BodyProxy(query),
        "header": _BodyProxy(dict(headers)),
        "body": _BodyProxy(body if isinstance(body, dict) else {}),
    }

    template = _ENV.from_string(text)
    return template.render(
        request=request,
        now=_now,
        uuid=_uuid,
        randint=_randint,
    )