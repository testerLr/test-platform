import json

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.deps import CurrentUser, SessionDep
from app.models.pipeline import Pipeline, PipelineStep, StepType
from app.models.project import ProjectMember, ProjectRole
from app.schemas.pipeline import PipelineCreate, PipelineOut, PipelineUpdate, ReorderRequest, StepCreate, StepOut, StepUpdate, pick_node_config
from app.security.crypto import encrypt

router = APIRouter(prefix="/pipelines", tags=["pipelines"])


async def _require_role(session, project_id, user_id, *roles):
    m = await session.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id, ProjectMember.user_id == user_id
        )
    )
    if not m or (roles and m.role not in roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="permission denied")
    return m


@router.get("", response_model=list[PipelineOut])
async def list_pipelines(user: CurrentUser, session: SessionDep, project_id: int) -> list[Pipeline]:
    await _require_role(session, project_id, user.id,
                        ProjectRole.OWNER, ProjectRole.DEVELOPER, ProjectRole.VIEWER)
    rows = await session.scalars(
        select(Pipeline).where(Pipeline.project_id == project_id).order_by(Pipeline.id)
    )
    return list(rows.all())


@router.post("", response_model=PipelineOut, status_code=status.HTTP_201_CREATED)
async def create_pipeline(user: CurrentUser, session: SessionDep, body: PipelineCreate) -> Pipeline:
    await _require_role(session, body.project_id, user.id, ProjectRole.OWNER, ProjectRole.DEVELOPER)
    pipe = Pipeline(name=body.name, description=body.description, project_id=body.project_id, created_by=user.id)
    session.add(pipe)
    await session.commit()
    await session.refresh(pipe)
    return pipe


@router.get("/{pipeline_id}", response_model=PipelineOut)
async def get_pipeline(user: CurrentUser, session: SessionDep, pipeline_id: int) -> Pipeline:
    pipe = await session.get(Pipeline, pipeline_id)
    if not pipe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await _require_role(session, pipe.project_id, user.id,
                        ProjectRole.OWNER, ProjectRole.DEVELOPER, ProjectRole.VIEWER)
    return pipe


@router.patch("/{pipeline_id}", response_model=PipelineOut)
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


@router.delete("/{pipeline_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pipeline(user: CurrentUser, session: SessionDep, pipeline_id: int) -> None:
    pipe = await session.get(Pipeline, pipeline_id)
    if not pipe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await _require_role(session, pipe.project_id, user.id, ProjectRole.OWNER)
    await session.delete(pipe)
    await session.commit()


@router.get("/{pipeline_id}/steps", response_model=list[StepOut])
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


@router.post("/{pipeline_id}/steps", response_model=StepOut, status_code=status.HTTP_201_CREATED)
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


@router.patch("/{pipeline_id}/steps/{step_id}", response_model=StepOut)
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
        step.config = _encrypt_passwords(body.config, step.type)
    await session.commit()
    await session.refresh(step)
    return step


@router.delete("/{pipeline_id}/steps/{step_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_step(user: CurrentUser, session: SessionDep, pipeline_id: int, step_id: int) -> None:
    step = await session.get(PipelineStep, step_id)
    if not step or step.pipeline_id != pipeline_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await _require_role(session, step.pipeline_id, user.id, ProjectRole.OWNER, ProjectRole.DEVELOPER)
    await session.delete(step)
    await session.commit()


@router.post("/{pipeline_id}/steps/reorder", response_model=list[StepOut])
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
