import pytest

from app.pipeline_engine.errors import NodeExecutionError
from app.pipeline_engine.renderer import render_step_template


def test_static_passthrough():
    assert render_step_template("hello", {"steps": []}) == "hello"


def test_steps_reference():
    ctx = {"steps": [{"output": {"user_id": 42, "name": "alice"}}]}
    out = render_step_template("{{ steps.0.output.user_id }} {{ steps.0.output.name }}", ctx)
    assert out == "42 alice"


def test_renders_within_dict_value():
    ctx = {"steps": [{"output": {"x": "1"}}]}
    out = render_step_template('{"v": "{{ steps.0.output.x }}"}', ctx)
    assert out == '{"v": "1"}'


def test_now_uuid_randin():
    out = render_step_template("{{ now() }}|{{ uuid() }}|{{ randint(1,1) }}", {"steps": []})
    parts = out.split("|")
    assert "T" in parts[0]
    assert len(parts[1]) >= 32
    assert parts[2] == "1"


def test_ssti_blocked():
    with pytest.raises(NodeExecutionError):
        render_step_template("{{ ''.__class__.__mro__ }}", {"steps": []})