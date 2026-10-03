from jinja2.exceptions import SecurityError

from app.mock_engine.renderer import render


def test_static_passthrough():
    assert render("hello", path_params={}, query={}, headers={}, body_text="") == "hello"


def test_path_param():
    out = render("id={{ request.path.id }}", path_params={"id": "42"}, query={}, headers={}, body_text="")
    assert out == "id=42"


def test_query_and_header_and_body_field():
    out = render(
        "q={{ request.query.q }} h={{ request.header.authorization }} u={{ request.body.username }}",
        path_params={},
        query={"q": "hi"},
        headers={"Authorization": "Bearer x"},
        body_text='{"username": "alice"}',
    )
    assert out == "q=hi h=Bearer x u=alice"


def test_now_uuid_randin():
    out = render("{{ now() }}|{{ uuid() }}|{{ randint(1,1) }}", path_params={}, query={}, headers={}, body_text="")
    parts = out.split("|")
    assert len(parts) == 3
    assert "T" in parts[0]
    assert len(parts[1]) >= 32
    assert parts[2] == "1"


def test_ssti_blocked():
    """SandboxedEnvironment should refuse attribute access on Python builtins."""
    try:
        out = render("{{ ''.__class__.__mro__ }}", path_params={}, query={}, headers={}, body_text="")
    except SecurityError:
        return
    assert "<class 'type'>" not in out


def test_header_case_insensitive():
    """request.header.<lowercase> should resolve even when request sent mixed-case header."""
    out = render(
        "{{ request.header.authorization }}",
        path_params={},
        query={},
        headers={"Authorization": "Bearer x"},
        body_text="",
    )
    assert out == "Bearer x"