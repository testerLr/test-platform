import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.db.session as session_module
import app.models  # noqa: F401,F403
from app.db.base import Base
from app.models.pipeline import (
    Pipeline, PipelineRun, PipelineStep, StepType, RunStatus,
)
from app.models.project import Project, ProjectMember, ProjectRole
from app.models.user import User
from app.pipeline_engine.errors import NodeExecutionError
from app.pipeline_engine.executor import PipelineExecutor


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    TestSession = async_sessionmaker(engine, expire_on_commit=False)
    session_module.AsyncSessionLocal = TestSession
    async with TestSession() as s:
        yield s
    await engine.dispose()


async def _seed(session):
    u = User(username="u", password_hash="x", is_admin=False)
    session.add(u); await session.flush()
    p = Project(name="P", created_by=u.id)
    session.add(p); await session.flush()
    session.add(ProjectMember(project_id=p.id, user_id=u.id, role=ProjectRole.OWNER))
    pipe = Pipeline(project_id=p.id, name="pipe", created_by=u.id)
    session.add(pipe); await session.flush()
    step = PipelineStep(
        pipeline_id=pipe.id, order_index=0, type=StepType.MYSQL,
        name="ok", enabled=True,
        config={"connection": {"host": "h", "user": "u", "password": "p", "database": "d"}, "sql": "SELECT 1"},
    )
    session.add(step); await session.flush()
    run = PipelineRun(pipeline_id=pipe.id, triggered_by=u.id, status=RunStatus.RUNNING)
    session.add(run); await session.flush()
    return pipe, [step], run


class FakeExecutor:
    def __init__(self, outputs=None, raise_exc=None):
        self.outputs = outputs or [{"affected_rows": 1, "inserted_id": 42}]
        self.raise_exc = raise_exc

    async def run(self, rendered_config):
        if self.raise_exc:
            raise self.raise_exc
        return self.outputs.pop(0)


async def test_executor_success_writes_run_step(session):
    pipe, steps, run = await _seed(session)
    exe = PipelineExecutor(session, run, pipe, steps, executor_registry={"mysql": FakeExecutor()})
    result = await exe.execute()
    assert result["status"] == "success"
    assert result["success_count"] == 1
    assert run.status == RunStatus.SUCCESS


async def test_executor_failure_breaks_and_marks_skipped(session):
    pipe, [step_ok], run = await _seed(session)
    step_skip = PipelineStep(
        pipeline_id=pipe.id, order_index=1, type=StepType.KAFKA,
        name="should_skip", enabled=True,
        config={"connection": {"bootstrap_servers": "h:9092"}, "topic": "t", "value": "{}"},
    )
    session.add(step_skip); await session.flush()
    await session.refresh(run)
    failing = FakeExecutor(raise_exc=NodeExecutionError("boom", retryable=True))
    exe = PipelineExecutor(session, run, pipe, [step_ok, step_skip],
                           executor_registry={"mysql": failing, "kafka": FakeExecutor()})
    result = await exe.execute()
    assert result["status"] == "failed"
    assert result["success_count"] == 0
    assert result["failure_count"] == 1
    assert result["skipped_count"] == 1


async def test_disabled_step_skipped_without_executor(session):
    pipe, [step], run = await _seed(session)
    step.enabled = False
    await session.flush()
    exe = PipelineExecutor(session, run, pipe, [step], executor_registry={})
    result = await exe.execute()
    assert result["skipped_count"] == 1
    assert result["success_count"] == 0