from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.deps import CurrentUser, SessionDep
from app.models.pipeline import Pipeline
from app.models.project import ProjectMember, ProjectRole
from app.schemas.pipeline import PipelineCreate, PipelineOut, PipelineUpdate

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
