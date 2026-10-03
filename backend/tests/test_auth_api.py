import pytest

from app.auth.security import hash_password
from app.models.user import User


@pytest.fixture
async def admin_user(session):
    u = User(username="admin", password_hash=hash_password("admin123"), is_admin=True)
    session.add(u)
    await session.commit()
    await session.refresh(u)
    return u


async def test_login_success(client, admin_user):
    r = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


async def test_login_wrong_password(client, admin_user):
    r = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


async def test_me_requires_token(client):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 401


async def test_me_with_token(client, admin_user):
    token = (await client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})).json()["access_token"]
    r = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["username"] == "admin"