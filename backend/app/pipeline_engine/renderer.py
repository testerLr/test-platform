from jinja2.exceptions import SecurityError
from jinja2.sandbox import SandboxedEnvironment

from app.mock_engine.renderer import _now, _randint, _uuid
from app.security.crypto import decrypt

_ENV = SandboxedEnvironment(autoescape=False)


def render_step_template(text: str, context: dict) -> str:
    """Render a step-config template against the pipeline execution context.

    `context` shape: {"steps": [{"output": {...}, "error": "..."}, ...]}
    Templates may reference {{ steps.N.output.field }} or call now()/uuid()/randint().
    Raises NodeExecutionError on sandbox violations so callers can distinguish blocked
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
    except SecurityError as e:
        from app.pipeline_engine.errors import NodeExecutionError
        raise NodeExecutionError(f"sandbox blocked template: {e}", retryable=False) from e


_ENCRYPTED_KEYS = {"password_enc", "sasl_password_enc"}


def decrypt_credentials(config: dict) -> dict:
    """Walk a rendered config dict; replace every `*_enc` field with decrypted plaintext.

    Operates in place; returns the same dict for convenience.
    """
    conn = config.get("connection")
    if isinstance(conn, dict):
        for key in list(conn.keys()):
            if key.endswith("_enc") and conn[key]:
                plain_key = key[:-4]  # strip "_enc"
                try:
                    conn[plain_key] = decrypt(conn[key])
                except Exception:
                    # If decryption fails, leave the field as-is; executor will surface auth error.
                    pass
                del conn[key]
    return config