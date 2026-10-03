from app.auth.security import hash_password
from app.mock_engine import get_engine
from app.models.mock_api import HttpMethod, MockAPI
from app.models.project import Project, ProjectMember, ProjectRole
from app.models.user import User


async def _seed_mock(client, session):
    owner = User(username="owner", password_hash=hash_password("owner123"), is_admin=False)
    session.add(owner); await session.commit()
    p = Project(name="P", created_by=owner.id)
    session.add(p); await session.flush()
    session.add(ProjectMember(project_id=p.id, user_id=owner.id, role=ProjectRole.OWNER))
    await session.commit()
    ot = (await client.post("/api/v1/auth/login", json={"username": "owner", "password": "owner123"})).json()["access_token"]
    return p, ot


async def test_runtime_static(client, session):
    p, ot = await _seed_mock(client, session)
    await client.post(
        "/api/v1/mocks",
        json={"project_id": p.id, "name": "m", "method": "GET", "path": "/ping", "response_body": '{"ok":true}', "response_status": 200},
        headers={"Authorization": f"Bearer {ot}"},
    )
    r = await client.get("/m/ping")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


async def test_runtime_path_param_and_body_field(client, session):
    p, ot = await _seed_mock(client, session)
    await client.post(
        "/api/v1/mocks",
        json={
            "project_id": p.id, "name": "m", "method": "POST", "path": "/u/{id}",
            "response_body": '{"id":"{{ request.path.id }}","user":"{{ request.body.name }}"}',
        },
        headers={"Authorization": f"Bearer {ot}"},
    )
    r = await client.post("/m/u/42", json={"name": "alice"})
    assert r.status_code == 200
    assert r.json() == {"id": "42", "user": "alice"}


async def test_runtime_not_found(client):
    r = await client.get("/m/nope")
    assert r.status_code == 404


async def test_disabled_mock_not_served(client, session):
    p, ot = await _seed_mock(client, session)
    mid = (await client.post(
        "/api/v1/mocks",
        json={"project_id": p.id, "name": "m", "method": "GET", "path": "/x", "response_body": "{}"},
        headers={"Authorization": f"Bearer {ot}"},
    )).json()["id"]
    await client.patch(f"/api/v1/mocks/{mid}", json={"enabled": False}, headers={"Authorization": f"Bearer {ot}"})
    r = await client.get("/m/x")
    assert r.status_code == 404


async def test_query_match(client, session):
    p, ot = await _seed_mock(client, session)
    await client.post(
        "/api/v1/mocks",
        json={
            "project_id": p.id, "name": "m", "method": "GET", "path": "/q",
            "request_match": {"query": {"token": "abc"}},
            "response_body": '{"ok":true}',
        },
        headers={"Authorization": f"Bearer {ot}"},
    )
    r = await client.get("/m/q?token=abc")
    assert r.status_code == 200
    r = await client.get("/m/q?token=zzz")
    assert r.status_code == 404
