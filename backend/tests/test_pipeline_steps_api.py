from app.auth.security import hash_password
from app.models.pipeline import StepType
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
    pipe = (await client.post(
        "/api/v1/pipelines",
        json={"project_id": p.id, "name": "pl"},
        headers={"Authorization": f"Bearer {tok}"},
    )).json()
    return p, tok, pipe


async def test_create_mysql_step_encrypts_password(client, session):
    p, tok, pipe = await _setup(client, session)
    cfg = {
        "connection": {"host": "h", "port": 3306, "user": "u", "password": "plain", "database": "d"},
        "sql": "INSERT INTO x VALUES (%s)",
        "params": {"v": 1},
    }
    r = await client.post(
        f"/api/v1/pipelines/{pipe['id']}/steps",
        json={"type": "mysql", "name": "s1", "config": cfg},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 201
    assert "password_enc" in r.json()["config"]["connection"]
    assert "password" not in r.json()["config"]["connection"]


async def test_create_kafka_step(client, session):
    p, tok, pipe = await _setup(client, session)
    cfg = {"connection": {"bootstrap_servers": "h:9092"}, "topic": "t", "value": "{}"}
    r = await client.post(
        f"/api/v1/pipelines/{pipe['id']}/steps",
        json={"type": "kafka", "name": "s2", "config": cfg},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 201


async def test_reorder_steps(client, session):
    p, tok, pipe = await _setup(client, session)
    s1 = (await client.post(f"/api/v1/pipelines/{pipe['id']}/steps",
        json={"type": "kafka", "name": "a", "config": {"connection": {"bootstrap_servers": "h:9092"}, "topic": "t", "value": "{}"}},
        headers={"Authorization": f"Bearer {tok}"})).json()
    s2 = (await client.post(f"/api/v1/pipelines/{pipe['id']}/steps",
        json={"type": "kafka", "name": "b", "config": {"connection": {"bootstrap_servers": "h:9092"}, "topic": "t", "value": "{}"}},
        headers={"Authorization": f"Bearer {tok}"})).json()
    r = await client.post(
        f"/api/v1/pipelines/{pipe['id']}/steps/reorder",
        json={"order": [s2["id"], s1["id"]]},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200
    assert r.json()[0]["id"] == s2["id"]
