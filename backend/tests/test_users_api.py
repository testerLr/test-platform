from app.auth.security import hash_password
from app.models.user import User


async def _admin_token(client, session) -> str:
    u = User(username="admin", password_hash=hash_password("admin123"), is_admin=True)
    session.add(u); await session.commit(); await session.refresh(u)
    r = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    return r.json()["access_token"]


async def _auth(client, token):
    client.headers["Authorization"] = f"Bearer {token}"


async def test_list_users_requires_admin(client, session):
    token = await _admin_token(client, session)
    await _auth(client, token)
    r = await client.get("/api/v1/users")
    assert r.status_code == 200
    assert any(u["username"] == "admin" for u in r.json())


async def test_non_admin_cannot_list(client, session):
    u = User(username="alice", password_hash=hash_password("alice123"), is_admin=False)
    session.add(u); await session.commit()
    token = (await client.post("/api/v1/auth/login", json={"username": "alice", "password": "alice123"})).json()["access_token"]
    r = await client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


async def test_admin_creates_user(client, session):
    token = await _admin_token(client, session)
    r = await client.post(
        "/api/v1/users",
        json={"username": "bob", "password": "bob12345", "is_admin": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    assert r.json()["username"] == "bob"