from app.mock_engine.renderer import render


def test_static_passthrough():
    assert render("hello", path_params={}, query={}, headers={}, body_text="") == "hello"


def test_path_param():
    out = render("id={{ request.path.id }}", path_params={"id": "42"}, query={}, headers={}, body_text="")
    assert out == "id=42"


def test_query_and_header_and_body_field():
    out = render(
        "q={{ request.query.q }} h={{ request.header.Authorization }} u={{ request.body.username }}",
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