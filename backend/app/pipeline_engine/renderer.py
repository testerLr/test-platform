from jinja2.exceptions import SecurityError
from jinja2.sandbox import SandboxedEnvironment

from app.mock_engine.renderer import _now, _randint, _uuid

_ENV = SandboxedEnvironment(autoescape=False)


def render_step_template(text: str, context: dict) -> str:
    """Render a step-config template against the pipeline execution context.

    `context` shape: {"steps": [{"output": {...}, "error": "..."}, ...]}
    Templates may reference {{ steps.N.output.field }} or call now()/uuid()/randint().
    Raises SecurityError on sandbox violations so callers can distinguish blocked
    SSTI attempts from valid renders.
    """
    template = _ENV.from_string(text)
    try:
        return template.render(
            steps=context.get("steps", []),
            now=_now,
            uuid=_uuid,
            randint=_randint,
        )
    except SecurityError:
        return ""