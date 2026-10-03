from app.mock_engine.matcher import match_path


def test_exact_match():
    assert match_path("/api/user/1", "/api/user/1") == {}


def test_param_match():
    assert match_path("/api/user/{id}", "/api/user/42") == {"id": "42"}


def test_no_match_different_length():
    assert match_path("/api/{x}", "/api/a/b") is None


def test_no_match_static_segment():
    assert match_path("/api/{x}/list", "/api/42/detail") is None