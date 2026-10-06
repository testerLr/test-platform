from app.auth.security import hash_password
from app.models.project import Project, ProjectMember, ProjectRole
from app.models.user import User


async def _setup(client, session):
    u = User(username="u", password_hash=hash_password("u12345"), is_admin=False)
    session.add(u); await session.commit()
    p = Project(name="P", created_by=u.id)
    session.add(p); await session.flush()
    session.add(ProjectMember(project_id=p.id, user_id=u.id, role=ProjectRole.OWNER))
    await session.commit()
    tok = (await client.post("/api/v1/auth/login", json={"username": "u", "password": "u12345"})).json()["access_token"]
    return p, tok


async def test_create_pipeline(client, session):
    p, tok = await _setup(client, session)
    r = await client.post(
        "/api/v1/pipelines",
        json={"project_id": p.id, "name": "pl1", "description": "x"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 201
    assert r.json()["name"] == "pl1"


async def test_list_pipelines(client, session):
    p, tok = await _setup(client, session)
    await client.post("/api/v1/pipelines", json={"project_id": p.id, "name": "pl"}, headers={"Authorization": f"Bearer {tok}"})
    r = await client.get(f"/api/v1/pipelines?project_id={p.id}", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert len(r.json()) == 1


async def test_delete_pipeline(client, session):
    p, tok = await _setup(client, session)
    pid = (await client.post("/api/v1/pipelines", json={"project_id": p.id, "name": "pl"}, headers={"Authorization": f"Bearer {tok}"})).json()["id"]
    r = await client.delete(f"/api/v1/pipelines/{pid}", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 204
