from app.auth.security import hash_password
from app.models.user import User


async def _user(client, session, name, *, admin=False):
    u = User(username=name, password_hash=hash_password(name + "123"), is_admin=admin)
    session.add(u); await session.commit(); await session.refresh(u)
    token = (await client.post("/api/v1/auth/login", json={"username": name, "password": name + "123"})).json()["access_token"]
    return u, token


async def test_create_and_list(client, session):
    _, token = await _user(client, session, "alice")
    h = {"Authorization": f"Bearer {token}"}
    r = await client.post("/api/v1/projects", json={"name": "P1"}, headers=h)
    assert r.status_code == 201
    pid = r.json()["id"]
    r = await client.get("/api/v1/projects", headers=h)
    assert any(p["id"] == pid for p in r.json())


async def test_only_owner_can_add_member(client, session):
    owner, ot = await _user(client, session, "owner")
    other, _ = await _user(client, session, "other")
    h = {"Authorization": f"Bearer {ot}"}
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h)).json()["id"]
    r = await client.post(
        f"/api/v1/projects/{pid}/members",
        json={"user_id": other.id, "role": "developer"},
        headers=h,
    )
    assert r.status_code == 201


async def test_non_member_cannot_see_project(client, session):
    owner, ot = await _user(client, session, "owner")
    outsider, out_t = await _user(client, session, "outsider")
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers={"Authorization": f"Bearer {ot}"})).json()["id"]
    r = await client.get(f"/api/v1/projects/{pid}", headers={"Authorization": f"Bearer {out_t}"})
    assert r.status_code == 403


async def test_last_owner_cannot_be_removed(client, session):
    owner, ot = await _user(client, session, "owner")
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers={"Authorization": f"Bearer {ot}"})).json()["id"]
    r = await client.delete(
        f"/api/v1/projects/{pid}/members/{owner.id}",
        headers={"Authorization": f"Bearer {ot}"},
    )
    assert r.status_code == 400