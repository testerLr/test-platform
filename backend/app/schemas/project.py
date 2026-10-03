from pydantic import BaseModel, ConfigDict, Field

from app.models.project import ProjectRole


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None


class MemberAdd(BaseModel):
    user_id: int
    role: ProjectRole = ProjectRole.DEVELOPER


class MemberUpdate(BaseModel):
    role: ProjectRole


class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_id: int
    username: str
    role: ProjectRole