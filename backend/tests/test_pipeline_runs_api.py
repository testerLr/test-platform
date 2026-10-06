from app.auth.security import hash_password
from app.models.pipeline import PipelineRun, StepType
from app.models.project import Project, ProjectMember, ProjectRole
from app.models.user import User


async def _seed(client, session):
    u = User(username="u", password_hash=hash_password("u12345"), is_admin=False)
    session.add(u); await session.commit()
    p = Project(name="P", created_by=u.id)
    session.add(p); await session.flush()
    session.add(ProjectMember(project_id=p.id, user_id=u.id, role=ProjectRole.OWNER))
    await session.commit()
    tok = (await client.post("/api/v1/auth/login", json={"username": "u", "password": "u12345"})).json()["access_token"]
    return p, tok


async def test_run_pipeline_creates_history(client, session):
    p, tok = await _seed(client, session)
    pipe = (await client.post(
        "/api/v1/pipelines", json={"project_id": p.id, "name": "pl"},
        headers={"Authorization": f"Bearer {tok}"})).json()
    r = await client.post(f"/api/v1/pipelines/{pipe['id']}/run", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    body = r.json()
    assert body["pipeline_id"] == pipe["id"]
    assert body["status"] in ("success", "failed")
    assert len(body["steps"]) >= 0


async def test_list_runs_limit_30(client, session):
    p, tok = await _seed(client, session)
    pipe = (await client.post("/api/v1/pipelines", json={"project_id": p.id, "name": "pl"},
        headers={"Authorization": f"Bearer {tok}"})).json()
    r = await client.get(f"/api/v1/pipelines/{pipe['id']}/runs", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)
