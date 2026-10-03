from app.auth.security import hash_password
from app.mock_engine import get_engine
from app.models.project import Project, ProjectMember, ProjectRole
from app.models.user import User


async def _setup(client, session):
    owner = User(username="owner", password_hash=hash_password("owner123"), is_admin=False)
    viewer = User(username="viewer", password_hash=hash_password("viewer123"), is_admin=False)
    session.add_all([owner, viewer]); await session.commit()
    p = Project(name="P", created_by=owner.id)
    session.add(p); await session.flush()
    session.add_all([
        ProjectMember(project_id=p.id, user_id=owner.id, role=ProjectRole.OWNER),
        ProjectMember(project_id=p.id, user_id=viewer.id, role=ProjectRole.VIEWER),
    ])
    await session.commit()
    ot = (await client.post("/api/v1/auth/login", json={"username": "owner", "password": "owner123"})).json()["access_token"]
    vt = (await client.post("/api/v1/auth/login", json={"username": "viewer", "password": "viewer123"})).json()["access_token"]
    return p, owner, viewer, ot, vt


async def test_owner_creates_and_engine_loads(client, session):
    p, _, _, ot, _ = await _setup(client, session)
    r = await client.post(
        "/api/v1/mocks",
        json={"project_id": p.id, "name": "m1", "method": "GET", "path": "/api/u/{id}", "response_body": "{}"},
        headers={"Authorization": f"Bearer {ot}"},
    )
    assert r.status_code == 201
    mid = r.json()["id"]
    assert any(m.id == mid for m in get_engine().all())


async def test_viewer_cannot_create(client, session):
    p, _, _, _, vt = await _setup(client, session)
    r = await client.post(
        "/api/v1/mocks",
        json={"project_id": p.id, "name": "m", "method": "GET", "path": "/x"},
        headers={"Authorization": f"Bearer {vt}"},
    )
    assert r.status_code == 403


async def test_patch_toggles_enabled(client, session):
    p, _, _, ot, _ = await _setup(client, session)
    mid = (await client.post(
        "/api/v1/mocks",
        json={"project_id": p.id, "name": "m", "method": "GET", "path": "/x"},
        headers={"Authorization": f"Bearer {ot}"},
    )).json()["id"]
    r = await client.patch(f"/api/v1/mocks/{mid}", json={"enabled": False}, headers={"Authorization": f"Bearer {ot}"})
    assert r.status_code == 200
    assert all(m.id != mid for m in get_engine().all())
