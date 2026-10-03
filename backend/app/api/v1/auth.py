from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.auth.security import create_access_token, hash_password, verify_password
from app.deps import CurrentUser, SessionDep
from app.models.user import User
from app.schemas.auth import ChangePasswordRequest, LoginRequest, UserPublic
from app.schemas.common import TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(session: SessionDep, body: LoginRequest) -> TokenResponse:
    user = await session.scalar(select(User).where(User.username == body.username))
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.get("/me", response_model=UserPublic)
async def me(user: CurrentUser) -> UserPublic:
    return UserPublic(id=user.id, username=user.username, is_admin=user.is_admin)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    session: SessionDep, user: CurrentUser, body: ChangePasswordRequest
) -> None:
    if not verify_password(body.old_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="wrong old password")
    user.password_hash = hash_password(body.new_password)
    await session.commit()