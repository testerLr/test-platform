import re

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