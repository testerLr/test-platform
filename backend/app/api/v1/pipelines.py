import json

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.deps import CurrentUser, SessionDep
from app.models.pipeline import Pipeline, PipelineStep, StepType
from app.models.project import ProjectMember, ProjectRole
from app.schemas.pipeline import PipelineCreate, PipelineOut, PipelineUpdate, ReorderRequest, StepCreate, StepOut, StepUpdate, pick_node_config
from app.security.crypto import encrypt

pipelines_v1_router = APIRouter(prefix="/pipelines", tags=["pipelines"])


async def _require_role(session, project_id, user_id, *roles):
    m = await session.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id, ProjectMember.user_id == user_id
        )
    )
    if not m or (roles and m.role not in roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="permission denied")
    return m


@pipelines_v1_router.get("", response_model=list[PipelineOut])
async def list_pipelines(user: CurrentUser, session: SessionDep, project_id: int) -> list[Pipeline]:
    await _require_role(session, project_id, user.id,
                        ProjectRole.OWNER, ProjectRole.DEVELOPER, ProjectRole.VIEWER)
    rows = await session.scalars(
        select(Pipeline).where(Pipeline.project_id == project_id).order_by(Pipeline.id)
    )
    return list(rows.all())


@pipelines_v1_router.post("", response_model=PipelineOut, status_code=status.HTTP_201_CREATED)
async def create_pipeline(user: CurrentUser, session: SessionDep, body: PipelineCreate) -> Pipeline:
    await _require_role(session, body.project_id, user.id, ProjectRole.OWNER, ProjectRole.DEVELOPER)
    pipe = Pipeline(name=body.name, description=body.description, project_id=body.project_id, created_by=user.id)
    session.add(pipe)
    await session.commit()
    await session.refresh(pipe)
    return pipe


@pipelines_v1_router.get("/{pipeline_id}", response_model=PipelineOut)
async def get_pipeline(user: CurrentUser, session: SessionDep, pipeline_id: int) -> Pipeline:
    pipe = await session.get(Pipeline, pipeline_id)
    if not pipe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await _require_role(session, pipe.project_id, user.id,
                        ProjectRole.OWNER, ProjectRole.DEVELOPER, ProjectRole.VIEWER)
    return pipe


@pipelines_v1_router.patch("/{pipeline_id}", response_model=PipelineOut)
async def update_pipeline(user: CurrentUser, session: SessionDep, pipeline_id: int, body: PipelineUpdate) -> Pipeline:
    pipe = await session.get(Pipeline, pipeline_id)
    if not pipe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await _require_role(session, pipe.project_id, user.id, ProjectRole.OWNER, ProjectRole.DEVELOPER)
    if body.name is not None:
        pipe.name = body.name
    if body.description is not None:
        pipe.description = body.description
    await session.commit()
    await session.refresh(pipe)
    return pipe


@pipelines_v1_router.delete("/{pipeline_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pipeline(user: CurrentUser, session: SessionDep, pipeline_id: int) -> None:
    pipe = await session.get(Pipeline, pipeline_id)
    if not pipe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await _require_role(session, pipe.project_id, user.id, ProjectRole.OWNER)
    await session.delete(pipe)
    await session.commit()


@pipelines_v1_router.get("/{pipeline_id}/steps", response_model=list[StepOut])
async def list_steps(user: CurrentUser, session: SessionDep, pipeline_id: int) -> list[PipelineStep]:
    pipe = await session.get(Pipeline, pipeline_id)
    if not pipe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await _require_role(session, pipe.project_id, user.id,
                        ProjectRole.OWNER, ProjectRole.DEVELOPER, ProjectRole.VIEWER)
    rows = await session.scalars(
        select(PipelineStep).where(PipelineStep.pipeline_id == pipeline_id).order_by(PipelineStep.order_index)
    )
    return list(rows.all())


@pipelines_v1_router.post("/{pipeline_id}/steps", response_model=StepOut, status_code=status.HTTP_201_CREATED)
async def create_step(user: CurrentUser, session: SessionDep, pipeline_id: int, body: StepCreate) -> PipelineStep:
    pipe = await session.get(Pipeline, pipeline_id)
    if not pipe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await _require_role(session, pipe.project_id, user.id, ProjectRole.OWNER, ProjectRole.DEVELOPER)
    encrypted = _encrypt_passwords(body.config, body.type)
    last = await session.scalar(
        select(PipelineStep.order_index)
        .where(PipelineStep.pipeline_id == pipeline_id)
        .order_by(PipelineStep.order_index.desc())
        .limit(1)
    )
    next_order = (last or -1) + 1
    step = PipelineStep(
        pipeline_id=pipeline_id,
        order_index=next_order,
        type=body.type,
        name=body.name,
        enabled=body.enabled,
        config=encrypted,
    )
    session.add(step)
    await session.commit()
    await session.refresh(step)
    return step


@pipelines_v1_router.patch("/{pipeline_id}/steps/{step_id}", response_model=StepOut)
async def update_step(user: CurrentUser, session: SessionDep, pipeline_id: int, step_id: int, body: StepUpdate) -> PipelineStep:
    step = await session.get(PipelineStep, step_id)
    if not step or step.pipeline_id != pipeline_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await _require_role(session, step.pipeline_id, user.id, ProjectRole.OWNER, ProjectRole.DEVELOPER)
    if body.name is not None:
        step.name = body.name
    if body.enabled is not None:
        step.enabled = body.enabled
    if body.config is not None:
        # Merge request body over existing config (preserves existing *_enc fields).
        merged = json.loads(json.dumps(step.config))  # deep copy of current
        def _overlay(dst, src):
            for k, v in src.items():
                if isinstance(v, dict) and isinstance(dst.get(k), dict):
                    _overlay(dst[k], v)
                else:
                    dst[k] = v
        _overlay(merged, body.config)
        step.config = _encrypt_passwords(merged, step.type)
    await session.commit()
    await session.refresh(step)
    return step


@pipelines_v1_router.delete("/{pipeline_id}/steps/{step_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_step(user: CurrentUser, session: SessionDep, pipeline_id: int, step_id: int) -> None:
    step = await session.get(PipelineStep, step_id)
    if not step or step.pipeline_id != pipeline_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await _require_role(session, step.pipeline_id, user.id, ProjectRole.OWNER, ProjectRole.DEVELOPER)
    await session.delete(step)
    await session.commit()


@pipelines_v1_router.post("/{pipeline_id}/steps/reorder", response_model=list[StepOut])
async def reorder_steps(user: CurrentUser, session: SessionDep, pipeline_id: int, body: ReorderRequest) -> list[PipelineStep]:
    pipe = await session.get(Pipeline, pipeline_id)
    if not pipe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await _require_role(session, pipe.project_id, user.id, ProjectRole.OWNER, ProjectRole.DEVELOPER)
    rows = await session.scalars(
        select(PipelineStep).where(PipelineStep.pipeline_id == pipeline_id)
    )
    steps_by_id = {s.id: s for s in rows.all()}
    for new_idx, sid in enumerate(body.order):
        if sid not in steps_by_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"step {sid} not in pipeline")
        steps_by_id[sid].order_index = new_idx
    await session.commit()
    rows = await session.scalars(
        select(PipelineStep).where(PipelineStep.pipeline_id == pipeline_id).order_by(PipelineStep.order_index)
    )
    return list(rows.all())


_PASSWORD_KEYS = {"password", "sasl_password"}


def _encrypt_passwords(raw: dict, type_value: StepType) -> dict:
    pick_node_config(type_value.value, raw)
    out = json.loads(json.dumps(raw))  # deep copy via JSON
    conn = out.get("connection")
    if isinstance(conn, dict):
        for key in _PASSWORD_KEYS:
            if key in conn and conn[key]:
                conn[key + "_enc"] = encrypt(conn[key])
                del conn[key]
    return out


from app.models.pipeline import PipelineRun, PipelineRunStep, RunStatus
from app.pipeline_engine import default_executor_registry
from app.pipeline_engine.errors import NodeExecutionError
from app.pipeline_engine.executor import PipelineExecutor
from app.pipeline_engine.renderer import render_step_template
from app.schemas.pipeline import RunDetailOut, RunOut, RunStepOut, TestStepRequest


@pipelines_v1_router.post("/{pipeline_id}/run", response_model=RunDetailOut)
async def run_pipeline(user: CurrentUser, session: SessionDep, pipeline_id: int) -> RunDetailOut:
    pipe = await session.get(Pipeline, pipeline_id)
    if not pipe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await _require_role(session, pipe.project_id, user.id, ProjectRole.OWNER, ProjectRole.DEVELOPER)
    rows = await session.scalars(
        select(PipelineStep).where(PipelineStep.pipeline_id == pipeline_id).order_by(PipelineStep.order_index)
    )
    steps = list(rows.all())
    run = PipelineRun(pipeline_id=pipeline_id, triggered_by=user.id, status=RunStatus.RUNNING)
    session.add(run)
    await session.flush()
    exe = PipelineExecutor(session, run, pipe, steps, executor_registry=default_executor_registry())
    await exe.execute()
    rs_rows = await session.scalars(
        select(PipelineRunStep).where(PipelineRunStep.run_id == run.id).order_by(PipelineRunStep.order_index)
    )
    step_outs = [RunStepOut.model_validate(r) for r in rs_rows.all()]
    return RunDetailOut(
        id=run.id, pipeline_id=run.pipeline_id, triggered_by=run.triggered_by,
        status=run.status.value, started_at=run.started_at, finished_at=run.finished_at,
        total_steps=run.total_steps, success_count=run.success_count,
        failure_count=run.failure_count, skipped_count=run.skipped_count,
        steps=step_outs,
    )


@pipelines_v1_router.get("/{pipeline_id}/runs", response_model=list[RunOut])
async def list_runs(user: CurrentUser, session: SessionDep, pipeline_id: int) -> list[PipelineRun]:
    pipe = await session.get(Pipeline, pipeline_id)
    if not pipe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await _require_role(session, pipe.project_id, user.id,
                        ProjectRole.OWNER, ProjectRole.DEVELOPER, ProjectRole.VIEWER)
    rows = await session.scalars(
        select(PipelineRun)
        .where(PipelineRun.pipeline_id == pipeline_id)
        .order_by(PipelineRun.id.desc())
        .limit(30)
    )
    return list(rows.all())


@pipelines_v1_router.delete("/{pipeline_id}/runs", status_code=status.HTTP_204_NO_CONTENT)
async def clear_runs(user: CurrentUser, session: SessionDep, pipeline_id: int) -> None:
    pipe = await session.get(Pipeline, pipeline_id)
    if not pipe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await _require_role(session, pipe.project_id, user.id, ProjectRole.OWNER, ProjectRole.DEVELOPER)
    rows = await session.scalars(select(PipelineRun).where(PipelineRun.pipeline_id == pipeline_id))
    for r in rows.all():
        await session.delete(r)
    await session.commit()


@pipelines_v1_router.post("/{pipeline_id}/steps/{step_id}/test")
async def test_step(user: CurrentUser, session: SessionDep, pipeline_id: int, step_id: int, body: TestStepRequest):
    step = await session.get(PipelineStep, step_id)
    if not step or step.pipeline_id != pipeline_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await _require_role(session, step.pipeline_id, user.id,
                        ProjectRole.OWNER, ProjectRole.DEVELOPER, ProjectRole.VIEWER)
    render_ctx = body.context if "steps" in body.context else {"steps": body.context.get("steps", [])}
    try:
        pick_node_config(step.type.value, step.config)
        rendered = await _render_with(step.config, render_ctx)
        exe = default_executor_registry()[step.type.value]
        output = await exe.run(rendered)
        return {"ok": True, "output": output, "rendered_config": rendered}
    except NodeExecutionError as e:
        return {"ok": False, "error": str(e), "retryable": e.retryable}
    except Exception as e:
        return {"ok": False, "error": f"unexpected: {e}", "retryable": False}


async def _render_with(raw: dict, ctx: dict) -> dict:
    def _walk(node):
        if isinstance(node, str):
            return render_step_template(node, ctx)
        if isinstance(node, dict):
            return {k: _walk(v) for k, v in node.items()}
        if isinstance(node, list):
            return [_walk(x) for x in node]
        return node
    return _walk(raw)


runs_v1_router = APIRouter(prefix="/runs", tags=["runs"])


@runs_v1_router.get("/{run_id}", response_model=RunDetailOut)
async def get_run(user: CurrentUser, session: SessionDep, run_id: int) -> RunDetailOut:
    run = await session.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    pipe = await session.get(Pipeline, run.pipeline_id)
    await _require_role(session, pipe.project_id, user.id,
                        ProjectRole.OWNER, ProjectRole.DEVELOPER, ProjectRole.VIEWER)
    rs_rows = await session.scalars(
        select(PipelineRunStep).where(PipelineRunStep.run_id == run_id).order_by(PipelineRunStep.order_index)
    )
    step_outs = [RunStepOut.model_validate(r) for r in rs_rows.all()]
    return RunDetailOut(
        id=run.id, pipeline_id=run.pipeline_id, triggered_by=run.triggered_by,
        status=run.status.value, started_at=run.started_at, finished_at=run.finished_at,
        total_steps=run.total_steps, success_count=run.success_count,
        failure_count=run.failure_count, skipped_count=run.skipped_count,
        steps=step_outs,
    )
