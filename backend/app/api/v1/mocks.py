from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.deps import CurrentUser, SessionDep
from app.mock_engine import get_engine
from app.models.mock_api import MockAPI
from app.models.project import ProjectMember, ProjectRole
from app.schemas.mock_api import (
    MockCreate,
    MockOut,
    MockTestRequest,
    MockTestResponse,
    MockUpdate,
)

router = APIRouter(prefix="/mocks", tags=["mocks"])


async def _ensure_role(session, project_id: int, user_id: int, *roles: ProjectRole) -> ProjectMember:
    m = await session.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id, ProjectMember.user_id == user_id
        )
    )
    if not m or m.role not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="permission denied")
    return m


@router.get("", response_model=list[MockOut])
async def list_mocks(
    user: CurrentUser, session: SessionDep, project_id: int | None = None
) -> list[MockAPI]:
    stmt = select(MockAPI).order_by(MockAPI.id)
    if project_id is not None:
        await _ensure_role(session, project_id, user.id, ProjectRole.OWNER, ProjectRole.DEVELOPER, ProjectRole.VIEWER)
        stmt = stmt.where(MockAPI.project_id == project_id)
    elif not user.is_admin:
        member_project_ids = select(ProjectMember.project_id).where(ProjectMember.user_id == user.id)
        stmt = stmt.where(MockAPI.project_id.in_(member_project_ids))
    return list((await session.scalars(stmt)).all())


@router.post("", response_model=MockOut, status_code=status.HTTP_201_CREATED)
async def create_mock(
    user: CurrentUser, session: SessionDep, body: MockCreate
) -> MockAPI:
    await _ensure_role(
        session, body.project_id, user.id, ProjectRole.OWNER, ProjectRole.DEVELOPER
    )
    mock = MockAPI(
        project_id=body.project_id,
        name=body.name,
        method=body.method,
        path=body.path,
        enabled=body.enabled,
        request_match=body.request_match.model_dump(exclude_none=True) if body.request_match else None,
        response_status=body.response_status,
        response_headers=body.response_headers,
        response_body=body.response_body,
        delay_ms=body.delay_ms,
        description=body.description,
        created_by=user.id,
    )
    session.add(mock)
    await session.commit()
    await session.refresh(mock)
    await get_engine().upsert(mock)
    return mock


@router.get("/{mock_id}", response_model=MockOut)
async def get_mock(user: CurrentUser, session: SessionDep, mock_id: int) -> MockAPI:
    mock = await session.get(MockAPI, mock_id)
    if not mock:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await _ensure_role(session, mock.project_id, user.id, ProjectRole.OWNER, ProjectRole.DEVELOPER, ProjectRole.VIEWER)
    return mock


@router.patch("/{mock_id}", response_model=MockOut)
async def update_mock(
    user: CurrentUser, session: SessionDep, mock_id: int, body: MockUpdate
) -> MockAPI:
    mock = await session.get(MockAPI, mock_id)
    if not mock:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await _ensure_role(
        session, mock.project_id, user.id, ProjectRole.OWNER, ProjectRole.DEVELOPER
    )
    data = body.model_dump(exclude_unset=True)
    if "request_match" in data and body.request_match is not None:
        data["request_match"] = body.request_match.model_dump(exclude_none=True)
    for k, v in data.items():
        setattr(mock, k, v)
    await session.commit()
    await session.refresh(mock)
    await get_engine().upsert(mock)
    return mock


@router.delete("/{mock_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mock(user: CurrentUser, session: SessionDep, mock_id: int) -> None:
    mock = await session.get(MockAPI, mock_id)
    if not mock:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await _ensure_role(
        session, mock.project_id, user.id, ProjectRole.OWNER, ProjectRole.DEVELOPER
    )
    await session.delete(mock)
    await session.commit()
    await get_engine().remove(mock_id)


@router.post("/{mock_id}/test", response_model=MockTestResponse)
async def test_mock(
    user: CurrentUser, session: SessionDep, mock_id: int, body: MockTestRequest
) -> MockTestResponse:
    mock = await session.get(MockAPI, mock_id)
    if not mock:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await _ensure_role(session, mock.project_id, user.id, ProjectRole.OWNER, ProjectRole.DEVELOPER, ProjectRole.VIEWER)

    from app.mock_engine.renderer import render

    rendered_headers = {
        k: render(v, path_params={}, query=body.query, headers=body.headers, body_text=body.body or "")
        for k, v in (mock.response_headers or {}).items()
    }
    rendered_body = render(
        mock.response_body,
        path_params={},
        query=body.query,
        headers=body.headers,
        body_text=body.body or "",
    )
    content_type = rendered_headers.pop("Content-Type", "application/json")
    return MockTestResponse(
        status=mock.response_status,
        headers={**rendered_headers, "Content-Type": content_type},
        body=rendered_body,
    )
