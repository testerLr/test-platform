from app.auth.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify_password():
    h = hash_password("hello-world")
    assert h != "hello-world"
    assert verify_password("hello-world", h)
    assert not verify_password("wrong", h)


def test_jwt_roundtrip():
    token = create_access_token("42")
    decoded = decode_token(token)
    assert decoded["sub"] == "42"
