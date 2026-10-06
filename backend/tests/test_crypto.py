import pytest
from cryptography.fernet import Fernet

from app import config as config_module
from app.security.crypto import decrypt, encrypt


@pytest.fixture(autouse=True)
def _set_fernet_key(monkeypatch):
    monkeypatch.setattr(config_module.settings, "encryption_key", Fernet.generate_key().decode())


def test_encrypt_decrypt_roundtrip():
    plain = "my-secret-password"
    cipher = encrypt(plain)
    assert cipher != plain
    assert decrypt(cipher) == plain


def test_decrypt_invalid_token():
    with pytest.raises(ValueError):
        decrypt("not-a-real-token")
