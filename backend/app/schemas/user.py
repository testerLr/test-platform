from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    is_admin: bool = False


class UserUpdate(BaseModel):
    is_active: bool | None = None
    is_admin: bool | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    is_admin: bool
    is_active: bool


class PasswordReset(BaseModel):
    new_password: str = Field(min_length=6, max_length=128)