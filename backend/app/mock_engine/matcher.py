import json
import re

from jsonpath_ng.ext import parse as jp_parse  # type: ignore

_PARAM_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def match_path(template: str, actual: str) -> dict[str, str] | None:
    tpl_parts = template.strip("/").split("/")
    act_parts = actual.strip("/").split("/")
    if len(tpl_parts) != len(act_parts):
        return None
    params: dict[str, str] = {}
    for t, a in zip(tpl_parts, act_parts):
        m = _PARAM_RE.fullmatch(t)
        if m:
            params[m.group(1)] = a
        elif t != a:
            return None
    return params


def match_request(
    spec: dict | None,
    *,
    query: dict[str, str],
    headers: dict[str, str],
    body_text: str,
) -> bool:
    if not spec:
        return True
    if q := spec.get("query"):
        for k, v in q.items():
            if query.get(k) != v:
                return False
    if h := spec.get("headers"):
        lower = {k.lower(): v for k, v in headers.items()}
        for k, v in h.items():
            if lower.get(k.lower()) != v:
                return False
    if "body_contains" in spec:
        if not body_text or spec["body_contains"] not in body_text:
            return False
    if "body_jsonpath" in spec:
        try:
            data = json.loads(body_text) if body_text else None
        except json.JSONDecodeError:
            return False
        if data is None:
            return False
        expr_str = spec["body_jsonpath"]
        # jsonpath_ng requires a leading '$' before filter expressions.
        is_filter = "[?(" in expr_str
        if is_filter and not expr_str.lstrip().startswith("$"):
            expr_str = "$" + expr_str
        expr = jp_parse(expr_str)
        matches = expr.find(data)
        if not matches:
            return False
        val = matches[0].value
        if isinstance(val, bool):
            return val
        # Filter expressions like [?(@.x == 'y')] return matched items (not bools);
        # non-empty match is considered truthy. All other expressions must yield bool.
        if is_filter:
            return True
        return False
    return True