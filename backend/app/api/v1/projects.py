from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.deps import CurrentUser, SessionDep
from app.models.project import Project, ProjectMember, ProjectRole
from app.models.user import User
from app.schemas.project import (
    MemberAdd,
    MemberOut,
    MemberUpdate,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
)

router = APIRouter(prefix="/projects", tags=["projects"])


async def _get_member(session, project_id: int, user_id: int) -> ProjectMember | None:
    return await session.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id, ProjectMember.user_id == user_id
        )
    )


async def _require_member(session, project_id: int, user_id: int) -> ProjectMember:
    m = await _get_member(session, project_id, user_id)
    if not m:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="not a project member")
    return m


async def _require_owner(session, project_id: int, user_id: int) -> ProjectMember:
    m = await _require_member(session, project_id, user_id)
    if m.role != ProjectRole.OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="owner required")
    return m


@router.get("", response_model=list[ProjectOut])
async def list_projects(user: CurrentUser, session: SessionDep) -> list[Project]:
    if user.is_admin:
        rows = await session.scalars(select(Project).order_by(Project.id))
    else:
        rows = await session.scalars(
            select(Project)
            .join(ProjectMember, ProjectMember.project_id == Project.id)
            .where(ProjectMember.user_id == user.id)
            .order_by(Project.id)
        )
    return list(rows.all())


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    user: CurrentUser, session: SessionDep, body: ProjectCreate
) -> Project:
    project = Project(name=body.name, description=body.description, created_by=user.id)
    session.add(project)
    await session.flush()
    session.add(ProjectMember(project_id=project.id, user_id=user.id, role=ProjectRole.OWNER))
    await session.commit()
    await session.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(user: CurrentUser, session: SessionDep, project_id: int) -> Project:
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if not user.is_admin:
        await _require_member(session, project_id, user.id)
    return project


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    user: CurrentUser, session: SessionDep, project_id: int, body: ProjectUpdate
) -> Project:
    if not user.is_admin:
        await _require_owner(session, project_id, user.id)
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if body.name is not None:
        project.name = body.name
    if body.description is not None:
        project.description = body.description
    await session.commit()
    await session.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(user: CurrentUser, session: SessionDep, project_id: int) -> None:
    if not user.is_admin:
        await _require_owner(session, project_id, user.id)
    project = await session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await session.delete(project)
    await session.commit()


@router.get("/{project_id}/members", response_model=list[MemberOut])
async def list_members(user: CurrentUser, session: SessionDep, project_id: int) -> list[MemberOut]:
    if not user.is_admin:
        await _require_member(session, project_id, user.id)
    rows = await session.scalars(
        select(ProjectMember, User)
        .join(User, User.id == ProjectMember.user_id)
        .where(ProjectMember.project_id == project_id)
        .order_by(ProjectMember.id)
    )
    out: list[MemberOut] = []
    for member, u in rows.all():
        out.append(MemberOut(user_id=u.id, username=u.username, role=member.role))
    return out


@router.post(
    "/{project_id}/members",
    response_model=MemberOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    user: CurrentUser, session: SessionDep, project_id: int, body: MemberAdd
) -> MemberOut:
    if not user.is_admin:
        await _require_owner(session, project_id, user.id)
    if not await session.get(Project, project_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if not await session.get(User, body.user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    if await _get_member(session, project_id, body.user_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="already a member")
    member = ProjectMember(project_id=project_id, user_id=body.user_id, role=body.role)
    session.add(member)
    await session.commit()
    u = await session.get(User, body.user_id)
    return MemberOut(user_id=u.id, username=u.username, role=member.role)


@router.patch("/{project_id}/members/{user_id}", response_model=MemberOut)
async def update_member(
    user: CurrentUser, session: SessionDep, project_id: int, user_id: int, body: MemberUpdate
) -> MemberOut:
    if not user.is_admin:
        await _require_owner(session, project_id, user.id)
    member = await _get_member(session, project_id, user_id)
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    member.role = body.role
    await session.commit()
    u = await session.get(User, user_id)
    return MemberOut(user_id=u.id, username=u.username, role=member.role)


@router.delete("/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    user: CurrentUser, session: SessionDep, project_id: int, user_id: int
) -> None:
    if not user.is_admin:
        await _require_owner(session, project_id, user.id)
    member = await _get_member(session, project_id, user_id)
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if member.role == ProjectRole.OWNER:
        owners = await session.scalars(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id, ProjectMember.role == ProjectRole.OWNER
            )
        )
        if len(owners.all()) <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="cannot remove last owner"
            )
    await session.delete(member)
    await session.commit()