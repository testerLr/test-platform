from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

_fernet = Fernet(settings.encryption_key.encode())


def encrypt(plain: str) -> str:
    return _fernet.encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt(cipher: str) -> str:
    try:
        return _fernet.decrypt(cipher.encode("ascii")).decode("utf-8")
    except InvalidToken as e:
        raise ValueError("invalid encrypted token") from e
