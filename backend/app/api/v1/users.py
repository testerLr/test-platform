from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.auth.security import hash_password
from app.deps import CurrentUser, SessionDep
from app.models.user import User
from app.schemas.user import PasswordReset, UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


def require_admin(user: CurrentUser) -> None:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin required")


_AdminDep = Annotated[None, Depends(require_admin)]


@router.get("", response_model=list[UserOut])
async def list_users(_: _AdminDep, session: SessionDep) -> list[User]:
    return list((await session.scalars(select(User).order_by(User.id))).all())


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    _: _AdminDep, session: SessionDep, body: UserCreate
) -> User:
    if await session.scalar(select(User).where(User.username == body.username)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="username exists")
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        is_admin=body.is_admin,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    _: _AdminDep, session: SessionDep, user_id: int, body: UserUpdate
) -> User:
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.is_admin is not None:
        user.is_admin = body.is_admin
    await session.commit()
    await session.refresh(user)
    return user


@router.post("/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(
    _: _AdminDep, session: SessionDep, user_id: int, body: PasswordReset
) -> None:
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    user.password_hash = hash_password(body.new_password)
    await session.commit()