from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.mock_api import HttpMethod


class MockRequestMatch(BaseModel):
    query: dict[str, str] | None = None
    headers: dict[str, str] | None = None
    body_contains: str | None = None
    body_jsonpath: str | None = None


class MockCreate(BaseModel):
    project_id: int
    name: str = Field(min_length=1, max_length=128)
    method: HttpMethod
    path: str = Field(min_length=1, max_length=255)
    enabled: bool = True
    request_match: MockRequestMatch | None = None
    response_status: int = Field(default=200, ge=100, le=599)
    response_headers: dict[str, str] | None = None
    response_body: str = ""
    delay_ms: int = Field(default=0, ge=0, le=60000)
    description: str | None = None

    @model_validator(mode="after")
    def _validate_path(self) -> "MockCreate":
        if "{" in self.path and not all(c.isalnum() or c in "{}_-" for c in self.path):
            raise ValueError("invalid path template")
        return self


class MockUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    method: HttpMethod | None = None
    path: str | None = Field(default=None, min_length=1, max_length=255)
    enabled: bool | None = None
    request_match: MockRequestMatch | None = None
    response_status: int | None = Field(default=None, ge=100, le=599)
    response_headers: dict[str, str] | None = None
    response_body: str | None = None
    delay_ms: int | None = Field(default=None, ge=0, le=60000)
    description: str | None = None


class MockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    name: str
    method: HttpMethod
    path: str
    enabled: bool
    request_match: MockRequestMatch | None
    response_status: int
    response_headers: dict[str, str] | None
    response_body: str
    delay_ms: int
    description: str | None


class MockTestRequest(BaseModel):
    method: HttpMethod
    path: str
    headers: dict[str, str] = {}
    query: dict[str, str] = {}
    body: str | None = None  # raw text; will be parsed as JSON if possible


class MockTestResponse(BaseModel):
    status: int
    headers: dict[str, str]
    body: str