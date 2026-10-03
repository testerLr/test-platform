from app.mock_engine.matcher import match_request


def test_none_spec_always_matches():
    assert match_request(None, query={}, headers={}, body_text="")


def test_query_match():
    spec = {"query": {"token": "abc"}}
    assert match_request(spec, query={"token": "abc"}, headers={}, body_text="")
    assert not match_request(spec, query={"token": "xyz"}, headers={}, body_text="")


def test_header_match_case_insensitive():
    spec = {"headers": {"Authorization": "Bearer x"}}
    assert match_request(spec, query={}, headers={"authorization": "Bearer x"}, body_text="")


def test_body_contains_substring():
    assert match_request({"body_contains": "login"}, query={}, headers={}, body_text="action=login")
    assert not match_request({"body_contains": "logout"}, query={}, headers={}, body_text="action=login")


def test_body_jsonpath_true():
    spec = {"body_jsonpath": "[?(@.action == 'login')]"}
    assert match_request(spec, query={}, headers={}, body_text='[{"action": "login"}]')


def test_body_jsonpath_non_bool_expression_rejected():
    """Non-boolean JSONPath expressions (e.g. simple field access) must NOT match."""
    spec = {"body_jsonpath": "$.action"}
    assert not match_request(spec, query={}, headers={}, body_text='{"action": "login"}')


def test_body_jsonpath_invalid_body_fails():
    assert not match_request({"body_jsonpath": "$.x"}, query={}, headers={}, body_text="not-json")