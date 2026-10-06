from datetime import datetime
from typing import Annotated, Any, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.pipeline import StepType


# ---------- Connections ----------

class MySQLConnection(BaseModel):
    host: str = Field(min_length=1)
    port: int = Field(default=3306, ge=1, le=65535)
    user: str = Field(min_length=1)
    password: str = Field(min_length=1)  # API 入参明文;handler 加密后存 DB
    database: str = Field(min_length=1)


class KafkaConnection(BaseModel):
    bootstrap_servers: str = Field(min_length=1)
    security_protocol: str = Field(default="PLAINTEXT")
    sasl_username: str | None = None
    sasl_password: str | None = None  # API 入参明文


class RedisConnection(BaseModel):
    host: str = Field(min_length=1)
    port: int = Field(default=6379, ge=1, le=65535)
    password: str | None = None  # API 入参明文
    db: int = Field(default=0, ge=0, le=15)


# ---------- Node configs ----------

class MySQLConfig(BaseModel):
    connection: MySQLConnection
    sql: str = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)


class KafkaConfig(BaseModel):
    connection: KafkaConnection
    topic: str = Field(min_length=1)
    key: str | None = None
    value: str  # 模板字符串


class RedisConfig(BaseModel):
    connection: RedisConnection
    operation: str = Field(default="set", pattern="^set$")  # v1 only set
    key: str = Field(min_length=1)
    value: str
    ttl_seconds: int = Field(default=0, ge=0, le=2592000)


class HttpConfig(BaseModel):
    method: str = Field(default="GET", pattern="^(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)$")
    url: str = Field(min_length=1)
    headers: dict[str, str] = Field(default_factory=dict)
    body: str | None = None
    timeout_seconds: int = Field(default=30, ge=1, le=600)


NodeConfig = Annotated[
    Union[MySQLConfig, KafkaConfig, RedisConfig, HttpConfig],
    Field(discriminator="type"),
]


def pick_node_config(type_value: str, raw: dict) -> BaseModel:
    """Route raw config dict to the right Pydantic class based on type."""
    cls = {
        StepType.MYSQL: MySQLConfig,
        StepType.KAFKA: KafkaConfig,
        StepType.REDIS: RedisConfig,
        StepType.HTTP: HttpConfig,
    }[StepType(type_value)]
    return cls.model_validate(raw)


# ---------- Pipeline / Step / Run DTOs ----------

class PipelineCreate(BaseModel):
    project_id: int
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None


class PipelineUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None


class StepCreate(BaseModel):
    type: StepType
    name: str = Field(min_length=1, max_length=128)
    enabled: bool = True
    config: dict[str, Any]  # validated per-type by API handler via pick_node_config

    @field_validator("config")
    @classmethod
    def _validate_config(cls, v, info):
        type_value = info.data.get("type")
        if type_value is not None:
            pick_node_config(type_value, v)  # raises ValidationError on mismatch
        return v


class StepUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    enabled: bool | None = None
    config: dict[str, Any] | None = None


class PipelineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    name: str
    description: str | None
    created_by: int
    created_at: datetime
    updated_at: datetime


class StepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    pipeline_id: int
    order_index: int
    type: StepType
    name: str
    enabled: bool
    config: dict[str, Any]


class ReorderRequest(BaseModel):
    order: list[int]  # step ids in desired order


class TestStepRequest(BaseModel):
    context: dict[str, Any] = Field(default_factory=dict)  # initial steps context for render


class RunStepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    run_id: int
    step_id: int
    order_index: int
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None
    input_rendered: dict[str, Any] | None
    output: dict[str, Any] | None
    error: str | None


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    pipeline_id: int
    triggered_by: int
    status: str
    started_at: datetime
    finished_at: datetime | None
    total_steps: int
    success_count: int
    failure_count: int
    skipped_count: int


class RunDetailOut(RunOut):
    steps: list[RunStepOut] = []
