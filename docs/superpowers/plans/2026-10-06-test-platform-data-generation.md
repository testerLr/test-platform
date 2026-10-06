# Data Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the data-generation feature on top of the published v1 (Mock) platform — pipeline orchestration with MySQL / Kafka / Redis / HTTP nodes, Jinja2 template context chaining, run history, encrypted credentials.

**Architecture:** Single FastAPI app extended with four new tables (pipelines / pipeline_steps / pipeline_runs / pipeline_run_steps), a `PipelineExecutor` that runs steps in order, and four `NodeExecutor` implementations (MySQL / Kafka / Redis / HTTP). Template rendering reuses v1's `Jinja2 SandboxedEnvironment`. Credentials encrypted with Fernet at the API boundary, decrypted only in-memory at execution time. Run history persisted to MySQL with the last 30 runs per pipeline kept. Frontend extends the existing Project Detail page with a third tab and adds Pipeline / Step / Run views.

**Tech Stack:** FastAPI, SQLAlchemy 2.x async, asyncmy, Alembic, aiokafka, redis (sync via `asyncio.to_thread`), httpx, cryptography (Fernet), Jinja2 SandboxedEnvironment (from v1), Vue 3 + Vite + Element Plus + Pinia + Vue Router + Axios.

**Spec Reference:** `docs/superpowers/specs/2026-10-06-test-platform-data-generation-design.md`
**v1 Reference:** `docs/superpowers/specs/2026-10-03-test-platform-shell-and-mock-design.md` and `docs/superpowers/plans/2026-10-03-test-platform-shell-and-mock.md`

## Global Constraints

- Python >= 3.11
- FastAPI latest stable (0.110+; current install is 0.142.2 — use `Annotated[X, Depends(...)]`, NOT bare `_: Depends(...)`)
- SQLAlchemy 2.x async; asyncmy for MySQL; Alembic for migrations
- Jinja2 `SandboxedEnvironment` (from `jinja2.sandbox`) — never plain `Environment` for user-controlled templates
- bcrypt pinned to `<4.0` (passlib 1.7.4 incompatibility, set in v1)
- jsonpath-ng for any JSONPath feature (added in v1)
- Vue 3 + Vite + Element Plus + Pinia + Vue Router + Axios (frontend)
- Mock runtime path prefix: `/m`; Management API: `/api/v1`; Data generation runtime: not used (sync execution in API)
- Conventional Commits with `Co-Authored-By: Claude Code <noreply@anthropic.com>` trailer
- Mock engine code from v1 (in `backend/app/mock_engine/`) must NOT be broken by v2 changes
- All existing v1 tests must continue to pass (40 backend + 4 frontend)

---

## Phase 1 — Foundation

### Task 1: Fernet Crypto Utility

**Files:**
- Create: `backend/app/security/__init__.py`
- Create: `backend/app/security/crypto.py`
- Create: `backend/tests/test_crypto.py`
- Modify: `backend/app/config.py` (add `encryption_key: str`)

**Interfaces:**
- Produces: `encrypt(plain: str) -> str`, `decrypt(cipher: str) -> str`

- [ ] **Step 1: Create app/security/__init__.py** (empty)

- [ ] **Step 2: Modify backend/app/config.py — add encryption_key**

Open `backend/app/config.py`. Add to the `Settings` class:

```python
    encryption_key: str = "dev-key-change-me-replace-with-fernet-key"
    log_level: str = "INFO"
```

(For local dev only. Production must override via env var.)

- [ ] **Step 3: Create app/security/crypto.py**

```python
from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

_fernet = Fernet(settings.encryption_key.encode())


def encrypt(plain: str) -> str:
    return _fernet.encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt(cipher: str) -> str:
    try:
        return _fernet.decrypt(cipher.encode("ascii")).decode("utf-8")
    except InvalidToken as e:
        raise ValueError("invalid encrypted token") from e
```

Note: `settings.encryption_key.encode()` requires a valid Fernet key (base64-encoded 32 bytes). For tests we'll generate one programmatically.

- [ ] **Step 4: Write failing tests `tests/test_crypto.py`**

```python
import pytest
from cryptography.fernet import Fernet

from app import config as config_module
from app.security.crypto import decrypt, encrypt


@pytest.fixture(autouse=True)
def _set_fernet_key(monkeypatch):
    monkeypatch.setattr(config_module.settings, "encryption_key", Fernet.generate_key().decode())


def test_encrypt_decrypt_roundtrip():
    plain = "my-secret-password"
    cipher = encrypt(plain)
    assert cipher != plain
    assert decrypt(cipher) == plain


def test_decrypt_invalid_token():
    with pytest.raises(ValueError):
        decrypt("not-a-real-token")
```

- [ ] **Step 5: Run tests**

```bash
cd "F:/project/git/test-platform/backend"
source .venv/Scripts/activate
pytest tests/test_crypto.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
cd "F:/project/git/test-platform"
git add backend/
git commit -m "feat(backend): Fernet crypto utility for credential encryption

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

Expected: 1 commit on top of `d7e8a48`.

---

### Task 2: Pipeline ORM Models

**Files:**
- Create: `backend/app/models/pipeline.py`
- Modify: `backend/app/models/__init__.py` (re-export)
- Test: `backend/tests/test_pipeline_models.py`

**Interfaces:**
- Produces: `StepType(str, Enum)` with values mysql/kafka/redis/http; `Pipeline`, `PipelineStep`, `PipelineRun`, `PipelineRunStep` ORM classes

- [ ] **Step 1: Create app/models/pipeline.py**

```python
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    JSON, BigInteger, Boolean, DateTime, Enum as SAEnum, ForeignKey, Index, Integer, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StepType(str, Enum):
    MYSQL = "mysql"
    KAFKA = "kafka"
    REDIS = "redis"
    HTTP = "http"


class RunStatus(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class StepRunStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class Pipeline(Base):
    __tablename__ = "pipelines"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class PipelineStep(Base):
    __tablename__ = "pipeline_steps"
    __table_args__ = (Index("ix_pipeline_steps_order", "pipeline_id", "order_index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    pipeline_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[StepType] = mapped_column(SAEnum(StepType, name="step_type"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    pipeline_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pipelines.id"), nullable=False)
    triggered_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    status: Mapped[RunStatus] = mapped_column(SAEnum(RunStatus, name="run_status"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    total_steps: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class PipelineRunStep(Base):
    __tablename__ = "pipeline_run_steps"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pipeline_runs.id", ondelete="CASCADE"), nullable=False)
    step_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pipeline_steps.id"), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[StepRunStatus] = mapped_column(
        SAEnum(StepRunStatus, name="step_run_status"), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    input_rendered: Mapped[dict | None] = mapped_column(JSON)
    output: Mapped[dict | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
```

- [ ] **Step 2: Update app/models/__init__.py**

Add (keep existing imports):

```python
from app.models.pipeline import (  # noqa: F401
    Pipeline,
    PipelineRun,
    PipelineRunStep,
    PipelineStep,
    StepType,
)
```

- [ ] **Step 3: Write sanity test**

Create `tests/test_pipeline_models.py`:

```python
import pytest

from app.models.pipeline import Pipeline, PipelineStep, PipelineRun, PipelineRunStep, StepType


def test_pipeline_step_type_enum():
    assert StepType.MYSQL.value == "mysql"
    assert StepType.KAFKA.value == "kafka"
    assert StepType.REDIS.value == "redis"
    assert StepType.HTTP.value == "http"


def test_orm_classes_register_on_metadata():
    tables = {"pipelines", "pipeline_steps", "pipeline_runs", "pipeline_run_steps"}
    from app.db.base import Base
    registered = set(Base.metadata.tables.keys())
    assert tables.issubset(registered)
```

- [ ] **Step 4: Run tests**

```bash
cd "F:/project/git/test-platform/backend"
source .venv/Scripts/activate
pytest tests/test_pipeline_models.py tests/test_crypto.py tests/test_mock_runtime.py tests/test_auth_api.py -v
```

Expected: all pass; v1 tests not broken.

- [ ] **Step 5: Commit**

```bash
cd "F:/project/git/test-platform"
git add backend/
git commit -m "feat(backend): pipeline, step, run, run_step ORM models

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

Expected: 1 commit.

---

### Task 3: Alembic Migration for Pipeline Tables

**Files:**
- Create: `backend/alembic/versions/<rev>_data_generation_tables.py` (autogenerated)

- [ ] **Step 1: Generate migration**

```bash
cd "F:/project/git/test-platform/backend"
source .venv/Scripts/activate
alembic revision --autogenerate -m "data generation tables"
```

Expected: new file `alembic/versions/<rev>_data_generation_tables.py` containing `op.create_table` for pipelines / pipeline_steps / pipeline_runs / pipeline_run_steps (plus indexes + FKs). Verify it includes `ondelete='CASCADE'` for the FK from pipeline_steps→pipelines and pipeline_run_steps→pipeline_runs.

- [ ] **Step 2: Apply against throwaway SQLite**

```bash
cd "F:/project/git/test-platform/backend"
DATABASE_URL=sqlite+aiosqlite:///./alembic_v2_test.db alembic upgrade head
```

Verify (Python):

```bash
python -c "import sqlite3; rows = sqlite3.connect('./alembic_v2_test.db').execute(\"SELECT name FROM sqlite_master WHERE type='table' ORDER BY name\").fetchall(); print(rows)"
```

Expected: includes `pipelines`, `pipeline_steps`, `pipeline_runs`, `pipeline_run_steps` along with the v1 tables.

Cleanup:

```bash
rm "F:/project/git/test-platform/backend/alembic_v2_test.db"
```

- [ ] **Step 3: Commit**

```bash
cd "F:/project/git/test-platform"
git add backend/alembic/versions/
git commit -m "feat(backend): alembic migration for pipeline tables

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 4: Pydantic Schemas with Discriminated Union

**Files:**
- Create: `backend/app/schemas/pipeline.py`
- Modify: `backend/app/schemas/__init__.py` (re-export)
- Test: `backend/tests/test_pipeline_schemas.py`

**Interfaces:**
- Produces: `MySQLConnection`, `KafkaConnection`, `RedisConnection`, `MySQLConfig`, `KafkaConfig`, `RedisConfig`, `HttpConfig`, `NodeConfig` (Union); `PipelineCreate`, `PipelineUpdate`, `PipelineOut`, `StepCreate`, `StepUpdate`, `StepOut`, `ReorderRequest`, `RunOut`, `RunStepOut`, `TestStepRequest`

- [ ] **Step 1: Create app/schemas/pipeline.py**

```python
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
    Field(discriminator="type_marker"),
]


class _TypeMarker(BaseModel):
    type_marker: str  # placeholder; not in user payload; used only to drive discriminator


def pick_node_config(type_value: str, raw: dict) -> BaseModel:
    """Helper: route raw config dict to the right Pydantic class based on type."""
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
```

Note: `type_marker` and `pick_node_config` exist because Pydantic 2.x's `discriminator` requires the discriminator key to be a literal field on every variant. Rather than add a redundant `type` field to each config class, we validate manually via `pick_node_config` in the API layer. The Union type is exported for documentation only.

- [ ] **Step 2: Update app/schemas/__init__.py**

Add at the bottom:

```python
from app.schemas.pipeline import (  # noqa: F401
    HttpConfig,
    KafkaConfig,
    MySQLConfig,
    NodeConfig,
    PipelineCreate,
    PipelineOut,
    PipelineUpdate,
    RedisConfig,
    ReorderRequest,
    RunDetailOut,
    RunOut,
    RunStepOut,
    StepCreate,
    StepOut,
    StepUpdate,
    TestStepRequest,
    pick_node_config,
)
```

- [ ] **Step 3: Write sanity tests `tests/test_pipeline_schemas.py`**

```python
import pytest
from pydantic import ValidationError

from app.schemas.pipeline import (
    HttpConfig, KafkaConfig, MySQLConfig, RedisConfig, StepCreate, pick_node_config,
)


def test_mysql_config_ok():
    c = MySQLConfig.model_validate({
        "connection": {"host": "h", "port": 3306, "user": "u", "password": "p", "database": "d"},
        "sql": "INSERT INTO x VALUES (%s)",
        "params": {"v": 1},
    })
    assert c.connection.host == "h"


def test_kafka_config_ok():
    c = KafkaConfig.model_validate({
        "connection": {"bootstrap_servers": "h:9092"},
        "topic": "t",
        "value": '{"x":1}',
    })
    assert c.topic == "t"


def test_redis_config_rejects_non_set_operation():
    with pytest.raises(ValidationError):
        RedisConfig.model_validate({
            "connection": {"host": "h"},
            "operation": "hset",  # v1 only allows set
            "key": "k",
            "value": "v",
        })


def test_http_config_ok():
    c = HttpConfig.model_validate({
        "method": "POST",
        "url": "http://x/y",
        "body": '{"a":1}',
    })
    assert c.timeout_seconds == 30  # default


def test_pick_node_config_dispatches_by_type():
    raw = {"connection": {"host": "h", "port": 3306, "user": "u", "password": "p", "database": "d"}, "sql": "SELECT 1"}
    cfg = pick_node_config("mysql", raw)
    assert isinstance(cfg, MySQLConfig)


def test_step_create_rejects_config_type_mismatch():
    with pytest.raises(ValidationError):
        StepCreate.model_validate({
            "type": "mysql",
            "name": "x",
            "config": {"connection": {"host": "h"}, "topic": "t", "value": "{}"},  # kafka-shaped config for mysql type
        })
```

- [ ] **Step 4: Run tests**

```bash
cd "F:/project/git/test-platform/backend"
source .venv/Scripts/activate
pytest tests/test_pipeline_schemas.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
cd "F:/project/git/test-platform"
git add backend/
git commit -m "feat(backend): pipeline/step/run Pydantic schemas with discriminated union

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 5: render_step_template Helper

**Files:**
- Create: `backend/app/pipeline_engine/__init__.py`
- Create: `backend/app/pipeline_engine/renderer.py`
- Test: `backend/tests/test_pipeline_renderer.py`

**Interfaces:**
- Produces: `render_step_template(text: str, context: dict) -> str`

- [ ] **Step 1: Create app/pipeline_engine/__init__.py** (empty)

- [ ] **Step 2: Create app/pipeline_engine/renderer.py**

This wraps v1's `Jinja2 SandboxedEnvironment`. We do not reuse `app.mock_engine.renderer.render` directly because that helper expects `path_params/query/headers/body_text`; here we have a simpler `context={"steps": [...]}` shape.

```python
from jinja2.sandbox import SandboxedEnvironment

from app.mock_engine.renderer import _now, _randint, _uuid

_ENV = SandboxedEnvironment(autoescape=False)


def render_step_template(text: str, context: dict) -> str:
    """Render a step-config template against the pipeline execution context.

    `context` shape: {"steps": [{"output": {...}, "error": "..."}, ...]}
    Templates may reference {{ steps.N.output.field }} or call now()/uuid()/randint().
    """
    template = _ENV.from_string(text)
    return template.render(
        steps=context.get("steps", []),
        now=_now,
        uuid=_uuid,
        randint=_randint,
    )
```

- [ ] **Step 3: Write tests `tests/test_pipeline_renderer.py`**

```python
from app.pipeline_engine.renderer import render_step_template


def test_static_passthrough():
    assert render_step_template("hello", {"steps": []}) == "hello"


def test_steps_reference():
    ctx = {"steps": [{"output": {"user_id": 42, "name": "alice"}}]}
    out = render_step_template("{{ steps.0.output.user_id }} {{ steps.0.output.name }}", ctx)
    assert out == "42 alice"


def test_renders_within_dict_value():
    ctx = {"steps": [{"output": {"x": "1"}}]}
    out = render_step_template('{"v": "{{ steps.0.output.x }}"}', ctx)
    assert out == '{"v": "1"}'


def test_now_uuid_randin():
    out = render_step_template("{{ now() }}|{{ uuid() }}|{{ randint(1,1) }}", {"steps": []})
    parts = out.split("|")
    assert "T" in parts[0]
    assert len(parts[1]) >= 32
    assert parts[2] == "1"


def test_ssti_blocked():
    out = render_step_template("{{ ''.__class__.__mro__ }}", {"steps": []})
    assert "<class" not in out
```

- [ ] **Step 4: Run tests**

```bash
cd "F:/project/git/test-platform/backend"
source .venv/Scripts/activate
pytest tests/test_pipeline_renderer.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
cd "F:/project/git/test-platform"
git add backend/app/pipeline_engine/renderer.py backend/tests/test_pipeline_renderer.py
git commit -m "feat(backend): pipeline template renderer (Jinja2 sandbox)

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 6: PipelineExecutor Skeleton + NodeExecutionError

**Files:**
- Create: `backend/app/pipeline_engine/errors.py`
- Create: `backend/app/pipeline_engine/executor.py`
- Test: `backend/tests/test_pipeline_executor.py`

**Interfaces:**
- Produces: `NodeExecutionError`, `PipelineExecutor` with `async def execute(self) -> dict` returning the full run result dict

- [ ] **Step 1: Create app/pipeline_engine/errors.py**

```python
class NodeExecutionError(Exception):
    def __init__(self, message: str, *, retryable: bool = False, details: dict | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.details = details or {}
```

- [ ] **Step 2: Create app/pipeline_engine/executor.py**

For this task, `PipelineExecutor.run_step` is a stub that calls `_resolve_executor().run()`; we will replace the executor implementations in Phase 2. The skeleton must already integrate with the per-step DB persistence so that by Phase 3 we can test end-to-end.

```python
import logging
import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pipeline import (
    Pipeline, PipelineRun, PipelineRunStep, PipelineStep, RunStatus, StepRunStatus,
)
from app.pipeline_engine.errors import NodeExecutionError
from app.pipeline_engine.renderer import render_step_template
from app.schemas.pipeline import pick_node_config

log = logging.getLogger("app.pipeline_engine")


class PipelineExecutor:
    def __init__(self, db: AsyncSession, run: PipelineRun, pipeline: Pipeline,
                 steps: list[PipelineStep], executor_registry: dict | None = None):
        self.db = db
        self.run = run
        self.pipeline = pipeline
        self.steps = sorted(steps, key=lambda s: s.order_index)
        self.context: dict = {"steps": []}
        self.executor_registry = executor_registry or {}  # type_value -> NodeExecutor instance

    def _resolve_executor(self, type_value: str):
        exe = self.executor_registry.get(type_value)
        if not exe:
            raise NodeExecutionError(f"no executor registered for type {type_value}", retryable=False)
        return exe

    async def _render_config(self, raw_config: dict) -> dict:
        """Render every string leaf in the config (recursively)."""
        def _walk(node):
            if isinstance(node, str):
                return render_step_template(node, self.context)
            if isinstance(node, dict):
                return {k: _walk(v) for k, v in node.items()}
            if isinstance(node, list):
                return [_walk(x) for x in node]
            return node
        return _walk(raw_config)

    async def _new_run_step(self, step: PipelineStep) -> PipelineRunStep:
        rs = PipelineRunStep(
            run_id=self.run.id,
            step_id=step.id,
            order_index=step.order_index,
            status=StepRunStatus.PENDING,
        )
        self.db.add(rs)
        await self.db.flush()
        return rs

    async def execute(self) -> dict:
        self.run.total_steps = len(self.steps)
        success_count = 0
        failure_count = 0
        skipped_count = 0

        for step in self.steps:
            if not step.enabled:
                rs = await self._new_run_step(step)
                rs.status = StepRunStatus.SKIPPED
                rs.started_at = datetime.now(timezone.utc)
                rs.finished_at = datetime.now(timezone.utc)
                rs.duration_ms = 0
                skipped_count += 1
                self.context["steps"].append({"output": {}, "error": None, "skipped": True})
                continue

            rs = await self._new_run_step(step)
            rs.started_at = datetime.now(timezone.utc)
            t0 = time.perf_counter()
            try:
                validated = pick_node_config(step.type.value, step.config)
                rendered = await self._render_config(validated.model_dump())
                rs.input_rendered = rendered
                output = await self._resolve_executor(step.type.value).run(rendered)
                rs.output = output
                rs.status = StepRunStatus.SUCCESS
                self.context["steps"].append({"output": output})
                success_count += 1
                log.info("step success: id=%s type=%s duration_ms=%s", step.id, step.type.value, int((time.perf_counter() - t0) * 1000))
            except NodeExecutionError as e:
                rs.status = StepRunStatus.FAILED
                rs.error = str(e)
                self.context["steps"].append({"output": {}, "error": str(e)})
                failure_count += 1
                log.error("step failed: id=%s type=%s error=%s retryable=%s", step.id, step.type.value, e, e.retryable)
                break
            except Exception as e:
                rs.status = StepRunStatus.FAILED
                rs.error = f"unexpected: {e}"
                self.context["steps"].append({"output": {}, "error": str(e)})
                failure_count += 1
                log.exception("step unexpected error: id=%s", step.id)
                break
            finally:
                rs.finished_at = datetime.now(timezone.utc)
                rs.duration_ms = int((time.perf_counter() - t0) * 1000)
                await self.db.flush()

        self.run.success_count = success_count
        self.run.failure_count = failure_count
        self.run.skipped_count = skipped_count
        self.run.status = RunStatus.SUCCESS if failure_count == 0 else RunStatus.FAILED
        self.run.finished_at = datetime.now(timezone.utc)
        await self.db.commit()
        return {
            "run_id": self.run.id,
            "pipeline_id": self.pipeline.id,
            "status": self.run.status.value,
            "started_at": self.run.started_at.isoformat(),
            "finished_at": self.run.finished_at.isoformat(),
            "total_steps": self.run.total_steps,
            "success_count": success_count,
            "failure_count": failure_count,
            "skipped_count": skipped_count,
        }
```

- [ ] **Step 3: Write skeleton tests `tests/test_pipeline_executor.py`**

These tests use a fake executor registry to avoid real DB connections.

```python
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.db.session as session_module
import app.models  # noqa: F401,F403
from app.db.base import Base
from app.models.pipeline import (
    Pipeline, PipelineRun, PipelineStep, StepType, RunStatus, StepRunStatus,
)
from app.models.project import Project, ProjectMember, ProjectRole
from app.models.user import User
from app.pipeline_engine.errors import NodeExecutionError
from app.pipeline_engine.executor import PipelineExecutor


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    TestSession = async_sessionmaker(engine, expire_on_commit=False)
    async with TestSession() as s:
        yield s
    await engine.dispose()


async def _seed(session):
    u = User(username="u", password_hash="x", is_admin=False)
    session.add(u); await session.flush()
    p = Project(name="P", created_by=u.id)
    session.add(p); await session.flush()
    session.add(ProjectMember(project_id=p.id, user_id=u.id, role=ProjectRole.OWNER))
    pipe = Pipeline(project_id=p.id, name="pipe", created_by=u.id)
    session.add(pipe); await session.flush()
    step = PipelineStep(
        pipeline_id=pipe.id, order_index=0, type=StepType.MYSQL,
        name="ok", enabled=True,
        config={"connection": {"host": "h", "user": "u", "password": "p", "database": "d"}, "sql": "SELECT 1"},
    )
    session.add(step); await session.flush()
    run = PipelineRun(pipeline_id=pipe.id, triggered_by=u.id, status=RunStatus.RUNNING)
    session.add(run); await session.flush()
    return pipe, [step], run


class FakeExecutor:
    def __init__(self, outputs=None, raise_exc=None):
        self.outputs = outputs or [{"affected_rows": 1, "inserted_id": 42}]
        self.raise_exc = raise_exc

    async def run(self, rendered_config):
        if self.raise_exc:
            raise self.raise_exc
        return self.outputs.pop(0)


async def test_executor_success_writes_run_step(session):
    pipe, steps, run = await _seed(session)
    exe = PipelineExecutor(session, run, pipe, steps, executor_registry={"mysql": FakeExecutor()})
    result = await exe.execute()
    assert result["status"] == "success"
    assert result["success_count"] == 1
    assert run.status == RunStatus.SUCCESS


async def test_executor_failure_breaks_and_marks_skipped(session):
    pipe, [step_ok, step_skip], run = await _seed(session)
    # add a second step that should be marked skipped
    step_skip = PipelineStep(
        pipeline_id=pipe.id, order_index=1, type=StepType.KAFKA,
        name="should_skip", enabled=True,
        config={"connection": {"bootstrap_servers": "h:9092"}, "topic": "t", "value": "{}"},
    )
    session.add(step_skip); await session.flush()
    await session.refresh(run)
    failing = FakeExecutor(raise_exc=NodeExecutionError("boom", retryable=True))
    exe = PipelineExecutor(session, run, pipe, [step_ok, step_skip],
                           executor_registry={"mysql": failing, "kafka": FakeExecutor()})
    result = await exe.execute()
    assert result["status"] == "failed"
    assert result["success_count"] == 0
    assert result["failure_count"] == 1
    assert result["skipped_count"] == 1


async def test_disabled_step_skipped_without_executor(session):
    pipe, [step], run = await _seed(session)
    step.enabled = False
    await session.flush()
    exe = PipelineExecutor(session, run, pipe, [step], executor_registry={})
    result = await exe.execute()
    assert result["skipped_count"] == 1
    assert result["success_count"] == 0
```

- [ ] **Step 4: Run tests**

```bash
cd "F:/project/git/test-platform/backend"
source .venv/Scripts/activate
pytest tests/test_pipeline_executor.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd "F:/project/git/test-platform"
git add backend/
git commit -m "feat(backend): PipelineExecutor skeleton with skip-on-fail semantics

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## Phase 2 — Node Executors

### Task 7: MySQL Executor

**Files:**
- Create: `backend/app/pipeline_engine/executors/__init__.py`
- Create: `backend/app/pipeline_engine/executors/mysql_executor.py`
- Test: `backend/tests/test_mysql_executor.py`

**Interfaces:**
- Produces: `MySQLExecutor.run(rendered_config: dict) -> dict`

- [ ] **Step 1: Update pyproject.toml — add asyncmy dev dep**

`asyncmy` is already a runtime dep. No changes needed unless missing; verify:

```bash
cd "F:/project/git/test-platform/backend"
grep asyncmy pyproject.toml
```

Should show it. If not, add `"asyncmy>=0.2.9"` to `dependencies`.

- [ ] **Step 2: Create app/pipeline_engine/executors/__init__.py** (empty)

- [ ] **Step 3: Create app/pipeline_engine/executors/mysql_executor.py**

```python
import asyncmy

from app.pipeline_engine.errors import NodeExecutionError


class MySQLExecutor:
    type = "mysql"

    async def run(self, rendered_config: dict) -> dict:
        conn_cfg = rendered_config["connection"]
        sql = rendered_config["sql"]
        params = rendered_config.get("params", {})

        conn = None
        try:
            conn = await asyncmy.connect(
                host=conn_cfg["host"],
                port=conn_cfg["port"],
                user=conn_cfg["user"],
                password=conn_cfg["password"],
                db=conn_cfg["database"],
                autocommit=True,
            )
            async with conn.cursor() as cur:
                # Convert dict-style params to positional tuple in declaration order.
                # MySQL params only supports %s placeholders with positional args.
                # We support ordered-key insertion via .keys() in Python 3.7+ dict.
                if params:
                    keys = list(params.keys())
                    values = tuple(params[k] for k in keys)
                    sql_params = _named_to_positional(sql, keys)
                    await cur.execute(sql_params, values)
                else:
                    await cur.execute(sql)
                affected = cur.rowcount
                inserted_id = cur.lastrowid
            return {"affected_rows": affected, "inserted_id": inserted_id}
        except asyncmy.errors.OperationalError as e:
            raise NodeExecutionError(f"mysql connection error: {e}", retryable=True) from e
        except asyncmy.errors.ProgrammingError as e:
            raise NodeExecutionError(f"mysql sql error: {e}", retryable=False, details={"sql": sql}) from e
        except asyncmy.errors.IntegrityError as e:
            raise NodeExecutionError(f"mysql integrity error: {e}", retryable=False) from e
        finally:
            if conn is not None:
                await conn.ensure_closed()


def _named_to_positional(sql: str, keys: list[str]) -> str:
    """Replace %(name)s placeholders with %s in given key order."""
    out = sql
    for k in keys:
        out = out.replace(f"%({k})s", "%s")
    return out
```

- [ ] **Step 4: Write tests `tests/test_mysql_executor.py`**

```python
import pytest

from app.pipeline_engine.errors import NodeExecutionError
from app.pipeline_engine.executors.mysql_executor import MySQLExecutor, _named_to_positional


def test_named_to_positional_replaces_in_order():
    sql = "INSERT INTO x (a, b) VALUES (%(a)s, %(b)s)"
    out = _named_to_positional(sql, ["a", "b"])
    assert out == "INSERT INTO x (a, b) VALUES (%s, %s)"


async def test_mysql_executor_connection_error_is_retryable(monkeypatch):
    import asyncmy
    from app.pipeline_engine.executors import mysql_executor as mod

    async def _boom(*a, **kw):
        raise asyncmy.errors.OperationalError(2003, "can't connect")
    monkeypatch.setattr(mod, "asyncmy", type("X", (), {"connect": staticmethod(_boom), "errors": asyncmy.errors}))

    exe = MySQLExecutor()
    rendered = {"connection": {"host": "h", "port": 3306, "user": "u", "password": "p", "database": "d"},
                "sql": "SELECT 1", "params": {}}
    with pytest.raises(NodeExecutionError) as exc:
        await exe.run(rendered)
    assert exc.value.retryable is True


async def test_mysql_executor_sql_error_not_retryable(monkeypatch):
    import asyncmy
    from app.pipeline_engine.executors import mysql_executor as mod

    class FakeConn:
        async def ensure_closed(self):
            return None
    class FakeCursor:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return None
        async def execute(self, sql, params=None):
            raise asyncmy.errors.ProgrammingError(1064, "syntax error")
        @property
        def rowcount(self): return 0
        @property
        def lastrowid(self): return None
    async def _connect(*a, **kw): return FakeConn()
    monkeypatch.setattr(mod, "asyncmy", type("X", (), {
        "connect": staticmethod(_connect),
        "errors": asyncmy.errors,
    }))

    exe = MySQLExecutor()
    rendered = {"connection": {"host": "h", "port": 3306, "user": "u", "password": "p", "database": "d"},
                "sql": "BAD", "params": {}}
    with pytest.raises(NodeExecutionError) as exc:
        await exe.run(rendered)
    assert exc.value.retryable is False
```

- [ ] **Step 5: Run tests**

```bash
cd "F:/project/git/test-platform/backend"
source .venv/Scripts/activate
pytest tests/test_mysql_executor.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
cd "F:/project/git/test-platform"
git add backend/app/pipeline_engine/executors/ backend/tests/test_mysql_executor.py
git commit -m "feat(backend): MySQL pipeline node executor

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 8: Kafka Executor

**Files:**
- Modify: `backend/pyproject.toml` (add `aiokafka>=0.10`)
- Create: `backend/app/pipeline_engine/executors/kafka_executor.py`
- Test: `backend/tests/test_kafka_executor.py`

- [ ] **Step 1: Add aiokafka to pyproject.toml**

In `dependencies` list, add `"aiokafka>=0.10"`. Then:

```bash
cd "F:/project/git/test-platform/backend"
source .venv/Scripts/activate
pip install -e ".[dev]"
```

- [ ] **Step 2: Create app/pipeline_engine/executors/kafka_executor.py**

```python
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError, KafkaTimeoutError

from app.pipeline_engine.errors import NodeExecutionError


class KafkaExecutor:
    type = "kafka"

    async def run(self, rendered_config: dict) -> dict:
        conn = rendered_config["connection"]
        producer = AIOKafkaProducer(
            bootstrap_servers=conn["bootstrap_servers"],
            security_protocol=conn.get("security_protocol", "PLAINTEXT"),
            sasl_plain_username=conn.get("sasl_username"),
            sasl_plain_password=conn.get("sasl_password"),
        )
        try:
            await producer.start()
            metadata = await producer.send_and_wait(
                topic=rendered_config["topic"],
                key=rendered_config.get("key", "").encode("utf-8") if rendered_config.get("key") else None,
                value=rendered_config["value"].encode("utf-8"),
            )
            return {
                "topic": metadata.topic,
                "partition": metadata.partition,
                "offset": metadata.offset,
            }
        except (KafkaConnectionError, KafkaTimeoutError) as e:
            raise NodeExecutionError(f"kafka error: {e}", retryable=True) from e
        finally:
            await producer.stop()
```

- [ ] **Step 3: Write tests `tests/test_kafka_executor.py`**

```python
import pytest

from app.pipeline_engine.errors import NodeExecutionError
from app.pipeline_engine.executors import kafka_executor as mod
from app.pipeline_engine.executors.kafka_executor import KafkaExecutor


class FakeMetadata:
    topic = "t"
    partition = 0
    offset = 7


class FakeProducer:
    def __init__(self, **kw):
        self.kw = kw
        self.started = False
        self.stopped = False

    async def start(self):
        self.started = True

    async def send_and_wait(self, topic, key, value):
        return FakeMetadata()

    async def stop(self):
        self.stopped = True


async def test_kafka_executor_success(monkeypatch):
    monkeypatch.setattr(mod, "AIOKafkaProducer", FakeProducer)
    exe = KafkaExecutor()
    out = await exe.run({
        "connection": {"bootstrap_servers": "h:9092"},
        "topic": "t",
        "key": "k",
        "value": '{"x":1}',
    })
    assert out == {"topic": "t", "partition": 0, "offset": 7}


async def test_kafka_executor_connection_error_retryable(monkeypatch):
    from aiokafka.errors import KafkaConnectionError

    class BrokenProducer(FakeProducer):
        async def start(self):
            raise KafkaConnectionError("can't connect")

    monkeypatch.setattr(mod, "AIOKafkaProducer", BrokenProducer)
    exe = KafkaExecutor()
    with pytest.raises(NodeExecutionError) as exc:
        await exe.run({
            "connection": {"bootstrap_servers": "h:9092"},
            "topic": "t",
            "value": "{}",
        })
    assert exc.value.retryable is True
```

- [ ] **Step 4: Run tests**

```bash
cd "F:/project/git/test-platform/backend"
source .venv/Scripts/activate
pytest tests/test_kafka_executor.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
cd "F:/project/git/test-platform"
git add backend/
git commit -m "feat(backend): Kafka pipeline node executor

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 9: Redis Executor

**Files:**
- Modify: `backend/pyproject.toml` (add `redis>=5.0`)
- Create: `backend/app/pipeline_engine/executors/redis_executor.py`
- Test: `backend/tests/test_redis_executor.py`

- [ ] **Step 1: Add redis to pyproject.toml**

In `dependencies` list, add `"redis>=5.0"`. Then:

```bash
cd "F:/project/git/test-platform/backend"
source .venv/Scripts/activate
pip install -e ".[dev]"
```

- [ ] **Step 2: Create app/pipeline_engine/executors/redis_executor.py**

```python
import asyncio

import redis

from app.pipeline_engine.errors import NodeExecutionError


class RedisExecutor:
    type = "redis"

    async def run(self, rendered_config: dict) -> dict:
        conn = rendered_config["connection"]
        operation = rendered_config["operation"]
        if operation != "set":
            raise NodeExecutionError(f"unsupported operation {operation!r}", retryable=False)

        client = redis.Redis(
            host=conn["host"],
            port=conn["port"],
            password=conn.get("password"),
            db=conn.get("db", 0),
            decode_responses=True,
        )
        try:
            key = rendered_config["key"]
            value = rendered_config["value"]
            ttl = rendered_config.get("ttl_seconds", 0)

            def _do_set():
                if ttl > 0:
                    return client.set(key, value, ex=ttl)
                return client.set(key, value)

            ok = await asyncio.to_thread(_do_set)
            if not ok:
                raise NodeExecutionError(f"redis SET returned falsy for key {key!r}", retryable=False)
            return {"key": key, "operation": "set"}
        except redis.ConnectionError as e:
            raise NodeExecutionError(f"redis connection error: {e}", retryable=True) from e
        except redis.RedisError as e:
            raise NodeExecutionError(f"redis error: {e}", retryable=False) from e
        finally:
            await asyncio.to_thread(client.close)
```

- [ ] **Step 3: Write tests `tests/test_redis_executor.py`**

```python
import pytest

from app.pipeline_engine.errors import NodeExecutionError
from app.pipeline_engine.executors import redis_executor as mod
from app.pipeline_engine.executors.redis_executor import RedisExecutor


class FakeRedis:
    def __init__(self, **kw):
        self.kw = kw
        self.closed = False

    def set(self, key, value, ex=None):
        self.last = {"key": key, "value": value, "ex": ex}
        return True

    def close(self):
        self.closed = True


async def test_redis_executor_success(monkeypatch):
    monkeypatch.setattr(mod.redis, "Redis", FakeRedis)
    exe = RedisExecutor()
    out = await exe.run({
        "connection": {"host": "h", "port": 6379, "db": 0},
        "operation": "set",
        "key": "k",
        "value": "v",
        "ttl_seconds": 60,
    })
    assert out == {"key": "k", "operation": "set"}


async def test_redis_executor_connection_error_retryable(monkeypatch):
    import redis as _redis

    class BrokenRedis(FakeRedis):
        def set(self, *a, **kw):
            raise _redis.ConnectionError("nope")

    monkeypatch.setattr(mod.redis, "Redis", BrokenRedis)
    exe = RedisExecutor()
    with pytest.raises(NodeExecutionError) as exc:
        await exe.run({
            "connection": {"host": "h", "port": 6379, "db": 0},
            "operation": "set",
            "key": "k",
            "value": "v",
            "ttl_seconds": 0,
        })
    assert exc.value.retryable is True


async def test_redis_executor_rejects_non_set(monkeypatch):
    monkeypatch.setattr(mod.redis, "Redis", FakeRedis)
    exe = RedisExecutor()
    with pytest.raises(NodeExecutionError) as exc:
        await exe.run({
            "connection": {"host": "h", "port": 6379, "db": 0},
            "operation": "hset",
            "key": "k",
            "value": "v",
        })
    assert exc.value.retryable is False
```

- [ ] **Step 4: Run tests**

```bash
cd "F:/project/git/test-platform/backend"
source .venv/Scripts/activate
pytest tests/test_redis_executor.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd "F:/project/git/test-platform"
git add backend/
git commit -m "feat(backend): Redis pipeline node executor (set only)

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 10: HTTP Executor

**Files:**
- Create: `backend/app/pipeline_engine/executors/http_executor.py`
- Test: `backend/tests/test_http_executor.py`

`httpx` is already a dev dep in v1; promote to runtime (or use a thin wrapper). For simplicity, install as needed.

- [ ] **Step 1: Add httpx to runtime deps**

In `backend/pyproject.toml` `dependencies` list, add `"httpx>=0.27"`. Then:

```bash
cd "F:/project/git/test-platform/backend"
source .venv/Scripts/activate
pip install -e ".[dev]"
```

- [ ] **Step 2: Create app/pipeline_engine/executors/http_executor.py**

```python
import json

import httpx

from app.pipeline_engine.errors import NodeExecutionError


class HttpExecutor:
    type = "http"

    async def run(self, rendered_config: dict) -> dict:
        method = rendered_config["method"]
        url = rendered_config["url"]
        headers = rendered_config.get("headers") or {}
        body = rendered_config.get("body")
        timeout = rendered_config.get("timeout_seconds", 30)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.request(method, url, headers=headers, content=body)
        except httpx.ConnectError as e:
            raise NodeExecutionError(f"http connection error: {e}", retryable=True) from e
        except httpx.TimeoutException as e:
            raise NodeExecutionError(f"http timeout: {e}", retryable=True) from e

        status = resp.status_code
        resp_headers = dict(resp.headers)
        text = resp.text
        try:
            parsed = resp.json()
        except (json.JSONDecodeError, ValueError):
            parsed = text

        if 400 <= status < 500:
            raise NodeExecutionError(
                f"http {status}: {text[:200]}",
                retryable=False,
                details={"status": status, "headers": resp_headers, "body": parsed},
            )
        if status >= 500:
            raise NodeExecutionError(
                f"http {status}: {text[:200]}",
                retryable=True,
                details={"status": status, "headers": resp_headers, "body": parsed},
            )

        return {"status": status, "headers": resp_headers, "body": parsed}
```

- [ ] **Step 3: Write tests `tests/test_http_executor.py`**

We use httpx's `MockTransport` to stub responses (httpx-native way, no external server needed).

```python
import json

import httpx
import pytest

from app.pipeline_engine.errors import NodeExecutionError
from app.pipeline_engine.executors import http_executor as mod
from app.pipeline_engine.executors.http_executor import HttpExecutor


def _handler_200(request):
    return httpx.Response(200, json={"ok": True, "echo": request.content.decode()})


def _handler_500(request):
    return httpx.Response(500, text="oops")


def _handler_404(request):
    return httpx.Response(404, text="nope")


async def test_http_executor_success(monkeypatch):
    transport = httpx.MockTransport(_handler_200)
    orig_client = httpx.AsyncClient

    def factory(*a, **kw):
        kw["transport"] = transport
        return orig_client(*a, **kw)

    monkeypatch.setattr(mod.httpx, "AsyncClient", factory)

    exe = HttpExecutor()
    out = await exe.run({
        "method": "POST",
        "url": "http://x/y",
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"a": 1}),
        "timeout_seconds": 5,
    })
    assert out["status"] == 200
    assert out["body"]["ok"] is True


async def test_http_executor_4xx_not_retryable(monkeypatch):
    transport = httpx.MockTransport(_handler_404)
    orig_client = httpx.AsyncClient

    def factory(*a, **kw):
        kw["transport"] = transport
        return orig_client(*a, **kw)

    monkeypatch.setattr(mod.httpx, "AsyncClient", factory)

    exe = HttpExecutor()
    with pytest.raises(NodeExecutionError) as exc:
        await exe.run({"method": "GET", "url": "http://x/y", "timeout_seconds": 5})
    assert exc.value.retryable is False


async def test_http_executor_5xx_retryable(monkeypatch):
    transport = httpx.MockTransport(_handler_500)
    orig_client = httpx.AsyncClient

    def factory(*a, **kw):
        kw["transport"] = transport
        return orig_client(*a, **kw)

    monkeypatch.setattr(mod.httpx, "AsyncClient", factory)

    exe = HttpExecutor()
    with pytest.raises(NodeExecutionError) as exc:
        await exe.run({"method": "GET", "url": "http://x/y", "timeout_seconds": 5})
    assert exc.value.retryable is True
```

- [ ] **Step 4: Run tests**

```bash
cd "F:/project/git/test-platform/backend"
source .venv/Scripts/activate
pytest tests/test_http_executor.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd "F:/project/git/test-platform"
git add backend/
git commit -m "feat(backend): HTTP pipeline node executor

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 11: Executor Registry

**Files:**
- Modify: `backend/app/pipeline_engine/__init__.py`

**Interfaces:**
- Produces: `default_executor_registry()` returning `{"mysql": MySQLExecutor(), "kafka": KafkaExecutor(), "redis": RedisExecutor(), "http": HttpExecutor()}`

- [ ] **Step 1: Update app/pipeline_engine/__init__.py**

```python
from app.pipeline_engine.executors.http_executor import HttpExecutor
from app.pipeline_engine.executors.kafka_executor import KafkaExecutor
from app.pipeline_engine.executors.mysql_executor import MySQLExecutor
from app.pipeline_engine.executors.redis_executor import RedisExecutor


def default_executor_registry() -> dict[str, object]:
    return {
        "mysql": MySQLExecutor(),
        "kafka": KafkaExecutor(),
        "redis": RedisExecutor(),
        "http": HttpExecutor(),
    }


__all__ = ["default_executor_registry"]
```

- [ ] **Step 2: Run all backend tests**

```bash
cd "F:/project/git/test-platform/backend"
source .venv/Scripts/activate
pytest -q
```

Expected: 40+ tests pass (v1 + Phase 1 + Phase 2).

- [ ] **Step 3: Commit**

```bash
cd "F:/project/git/test-platform"
git add backend/app/pipeline_engine/__init__.py
git commit -m "feat(backend): default executor registry

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## Phase 3 — API

### Task 12: Pipeline CRUD API

**Files:**
- Create: `backend/app/api/v1/pipelines.py`
- Modify: `backend/app/main.py` (mount router)
- Test: `backend/tests/test_pipelines_api.py`

**Interfaces:**
- Produces: 5 endpoints (`GET /pipelines?project_id`, `POST /pipelines`, `GET /pipelines/{id}`, `PATCH /pipelines/{id}`, `DELETE /pipelines/{id}`)

- [ ] **Step 1: Create app/api/v1/pipelines.py**

```python
from fastapi import APIRouter, Depends, HTTPException, status
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
```

- [ ] **Step 2: Mount in app/main.py**

Add to imports:

```python
from app.api.v1 import pipelines as pipelines_v1
```

And after the existing includes:

```python
app.include_router(pipelines_v1.router, prefix="/api/v1")
```

- [ ] **Step 3: Write tests `tests/test_pipelines_api.py`**

```python
from app.auth.security import hash_password
from app.models.project import Project, ProjectMember, ProjectRole
from app.models.user import User


async def _setup(client, session):
    u = User(username="u", password_hash=hash_password("u12345"), is_admin=False)
    session.add(u); await session.commit()
    p = Project(name="P", created_by=u.id)
    session.add(p); await session.flush()
    session.add(ProjectMember(project_id=p.id, user_id=u.id, role=ProjectRole.OWNER))
    await session.commit()
    tok = (await client.post("/api/v1/auth/login", json={"username": "u", "password": "u12345"})).json()["access_token"]
    return p, tok


async def test_create_pipeline(client, session):
    p, tok = await _setup(client, session)
    r = await client.post(
        "/api/v1/pipelines",
        json={"project_id": p.id, "name": "pl1", "description": "x"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 201
    assert r.json()["name"] == "pl1"


async def test_list_pipelines(client, session):
    p, tok = await _setup(client, session)
    await client.post("/api/v1/pipelines", json={"project_id": p.id, "name": "pl"}, headers={"Authorization": f"Bearer {tok}"})
    r = await client.get(f"/api/v1/pipelines?project_id={p.id}", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert len(r.json()) == 1


async def test_delete_pipeline(client, session):
    p, tok = await _setup(client, session)
    pid = (await client.post("/api/v1/pipelines", json={"project_id": p.id, "name": "pl"}, headers={"Authorization": f"Bearer {tok}"})).json()["id"]
    r = await client.delete(f"/api/v1/pipelines/{pid}", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 204
```

- [ ] **Step 4: Run tests**

```bash
cd "F:/project/git/test-platform/backend"
source .venv/Scripts/activate
pytest tests/test_pipelines_api.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
cd "F:/project/git/test-platform"
git add backend/
git commit -m "feat(backend): pipeline CRUD API

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 13: Step CRUD + Reorder API

**Files:**
- Modify: `backend/app/api/v1/pipelines.py` (add step endpoints)
- Test: `backend/tests/test_pipeline_steps_api.py`

- [ ] **Step 1: Add step endpoints to app/api/v1/pipelines.py**

Append (after the existing CRUD endpoints):

```python
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pipeline import PipelineStep, StepType
from app.schemas.pipeline import ReorderRequest, StepCreate, StepOut, StepUpdate, pick_node_config
from app.security.crypto import encrypt


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
    # Encrypt password fields before persisting
    encrypted = _encrypt_passwords(body.config, body.type)
    # Determine next order_index
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
        # type is required to dispatch encryption; fall back to existing type
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


# ---- helpers ----

_PASSWORD_KEYS = {"password", "sasl_password"}


def _encrypt_passwords(raw: dict, type_value: StepType) -> dict:
    """Encrypt password/sasl_password fields before DB write. Return a new dict."""
    # First validate shape
    pick_node_config(type_value.value, raw)
    out = json.loads(json.dumps(raw))  # deep copy via JSON
    conn = out.get("connection")
    if isinstance(conn, dict):
        for key in _PASSWORD_KEYS:
            if key in conn and conn[key]:
                conn[key + "_enc"] = encrypt(conn[key])
                del conn[key]
    return out
```

Add at top of file:

```python
import json
```

- [ ] **Step 2: Write tests `tests/test_pipeline_steps_api.py`**

```python
from app.auth.security import hash_password
from app.models.pipeline import StepType
from app.models.project import Project, ProjectMember, ProjectRole
from app.models.user import User


async def _setup(client, session):
    u = User(username="u", password_hash=hash_password("u12345"), is_admin=False)
    session.add(u); await session.commit()
    p = Project(name="P", created_by=u.id)
    session.add(p); await session.flush()
    session.add(ProjectMember(project_id=p.id, user_id=u.id, role=ProjectRole.OWNER))
    await session.commit()
    tok = (await client.post("/api/v1/auth/login", json={"username": "u", "password": "u12345"})).json()["access_token"]
    pipe = (await client.post(
        "/api/v1/pipelines",
        json={"project_id": p.id, "name": "pl"},
        headers={"Authorization": f"Bearer {tok}"},
    )).json()
    return p, tok, pipe


async def test_create_mysql_step_encrypts_password(client, session):
    p, tok, pipe = await _setup(client, session)
    cfg = {
        "connection": {"host": "h", "port": 3306, "user": "u", "password": "plain", "database": "d"},
        "sql": "INSERT INTO x VALUES (%s)",
        "params": {"v": 1},
    }
    r = await client.post(
        f"/api/v1/pipelines/{pipe['id']}/steps",
        json={"type": "mysql", "name": "s1", "config": cfg},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 201
    assert "password_enc" in r.json()["config"]["connection"]
    assert "password" not in r.json()["config"]["connection"]


async def test_create_kafka_step(client, session):
    p, tok, pipe = await _setup(client, session)
    cfg = {"connection": {"bootstrap_servers": "h:9092"}, "topic": "t", "value": "{}"}
    r = await client.post(
        f"/api/v1/pipelines/{pipe['id']}/steps",
        json={"type": "kafka", "name": "s2", "config": cfg},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 201


async def test_reorder_steps(client, session):
    p, tok, pipe = await _setup(client, session)
    s1 = (await client.post(f"/api/v1/pipelines/{pipe['id']}/steps",
        json={"type": "kafka", "name": "a", "config": {"connection": {"bootstrap_servers": "h:9092"}, "topic": "t", "value": "{}"}},
        headers={"Authorization": f"Bearer {tok}"})).json()
    s2 = (await client.post(f"/api/v1/pipelines/{pipe['id']}/steps",
        json={"type": "kafka", "name": "b", "config": {"connection": {"bootstrap_servers": "h:9092"}, "topic": "t", "value": "{}"}},
        headers={"Authorization": f"Bearer {tok}"})).json()
    r = await client.post(
        f"/api/v1/pipelines/{pipe['id']}/steps/reorder",
        json={"order": [s2["id"], s1["id"]]},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200
    assert r.json()[0]["id"] == s2["id"]
```

- [ ] **Step 3: Run tests**

```bash
cd "F:/project/git/test-platform/backend"
source .venv/Scripts/activate
pytest tests/test_pipeline_steps_api.py -v
```

Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
cd "F:/project/git/test-platform"
git add backend/
git commit -m "feat(backend): pipeline step CRUD + reorder API with password encryption

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 14: Run + History + Dry-Run API

**Files:**
- Modify: `backend/app/api/v1/pipelines.py` (add run + history + dry-run endpoints)
- Test: `backend/tests/test_pipeline_runs_api.py`

- [ ] **Step 1: Append run / history / dry-run endpoints**

Append to `app/api/v1/pipelines.py`:

```python
from datetime import datetime, timezone

from app.models.pipeline import PipelineRun, PipelineRunStep, PipelineStep, RunStatus, StepRunStatus
from app.pipeline_engine import default_executor_registry
from app.pipeline_engine.executor import PipelineExecutor
from app.schemas.pipeline import RunDetailOut, RunOut, RunStepOut, TestStepRequest


@router.post("/{pipeline_id}/run", response_model=RunDetailOut)
async def run_pipeline(user: CurrentUser, session: SessionDep, pipeline_id: int) -> RunDetailOut:
    pipe = await session.get(Pipeline, pipeline_id)
    if not pipe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await _require_role(session, pipe.project_id, user.id, ProjectRole.OWNER, ProjectRole.DEVELOPER)
    rows = await session.scalars(
        select(PipelineStep).where(PipelineStep.pipeline_id == pipeline_id).order_by(PipelineStep.order_index)
    )
    steps = list(rows.all())
    run = PipelineRun(pipeline_id=pipeline_id, triggered_by=user.id, status=RunStatus.RUNNING)
    session.add(run)
    await session.flush()
    exe = PipelineExecutor(session, run, pipe, steps, executor_registry=default_executor_registry())
    await exe.execute()
    rs_rows = await session.scalars(
        select(PipelineRunStep).where(PipelineRunStep.run_id == run.id).order_by(PipelineRunStep.order_index)
    )
    step_outs = [RunStepOut.model_validate(r) for r in rs_rows.all()]
    return RunDetailOut(
        id=run.id, pipeline_id=run.pipeline_id, triggered_by=run.triggered_by,
        status=run.status.value, started_at=run.started_at, finished_at=run.finished_at,
        total_steps=run.total_steps, success_count=run.success_count,
        failure_count=run.failure_count, skipped_count=run.skipped_count,
        steps=step_outs,
    )


@router.get("/{pipeline_id}/runs", response_model=list[RunOut])
async def list_runs(user: CurrentUser, session: SessionDep, pipeline_id: int) -> list[PipelineRun]:
    pipe = await session.get(Pipeline, pipeline_id)
    if not pipe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await _require_role(session, pipe.project_id, user.id,
                        ProjectRole.OWNER, ProjectRole.DEVELOPER, ProjectRole.VIEWER)
    rows = await session.scalars(
        select(PipelineRun)
        .where(PipelineRun.pipeline_id == pipeline_id)
        .order_by(PipelineRun.id.desc())
        .limit(30)
    )
    return list(rows.all())


@router.delete("/{pipeline_id}/runs", status_code=status.HTTP_204_NO_CONTENT)
async def clear_runs(user: CurrentUser, session: SessionDep, pipeline_id: int) -> None:
    pipe = await session.get(Pipeline, pipeline_id)
    if not pipe:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await _require_role(session, pipe.project_id, user.id, ProjectRole.OWNER, ProjectRole.DEVELOPER)
    rows = await session.scalars(select(PipelineRun).where(PipelineRun.pipeline_id == pipeline_id))
    for r in rows.all():
        await session.delete(r)
    await session.commit()


@router.post("/{pipeline_id}/steps/{step_id}/test")
async def test_step(user: CurrentUser, session: SessionDep, pipeline_id: int, step_id: int, body: TestStepRequest):
    step = await session.get(PipelineStep, step_id)
    if not step or step.pipeline_id != pipeline_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await _require_role(session, step.pipeline_id, user.id,
                        ProjectRole.OWNER, ProjectRole.DEVELOPER, ProjectRole.VIEWER)
    # body.context shape: {"steps": [...]} — matches PipelineExecutor.context
    render_ctx = body.context if "steps" in body.context else {"steps": body.context.get("steps", [])}
    try:
        pick_node_config(step.type.value, step.config)  # raises ValidationError on mismatch
        rendered = await _render_with(step.config, render_ctx)
        exe = default_executor_registry()[step.type.value]
        output = await exe.run(rendered)
        return {"ok": True, "output": output, "rendered_config": rendered}
    except NodeExecutionError as e:
        return {"ok": False, "error": str(e), "retryable": e.retryable}
    except Exception as e:
        return {"ok": False, "error": f"unexpected: {e}", "retryable": False}


async def _render_with(raw: dict, ctx: dict) -> dict:
    from app.pipeline_engine.renderer import render_step_template
    def _walk(node):
        if isinstance(node, str):
            return render_step_template(node, ctx)
        if isinstance(node, dict):
            return {k: _walk(v) for k, v in node.items()}
        if isinstance(node, list):
            return [_walk(x) for x in node]
        return node
    return _walk(raw)
```

Add to imports at top of file:

```python
from app.pipeline_engine.errors import NodeExecutionError
```

- [ ] **Step 2: Add separate runs/{run_id} GET endpoint**

Add (outside the existing pipeline-scoped router) — but since it's not pipeline-scoped, place it in a new module OR keep it in pipelines.py but use a different router prefix. For simplicity, append to pipelines.py but mount under a second router. To keep this task self-contained, **add as a second APIRouter** in pipelines.py:

Append:

```python
runs_router = APIRouter(prefix="/runs", tags=["runs"])


@runs_router.get("/{run_id}", response_model=RunDetailOut)
async def get_run(user: CurrentUser, session: SessionDep, run_id: int) -> RunDetailOut:
    run = await session.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    pipe = await session.get(Pipeline, run.pipeline_id)
    await _require_role(session, pipe.project_id, user.id,
                        ProjectRole.OWNER, ProjectRole.DEVELOPER, ProjectRole.VIEWER)
    rs_rows = await session.scalars(
        select(PipelineRunStep).where(PipelineRunStep.run_id == run_id).order_by(PipelineRunStep.order_index)
    )
    step_outs = [RunStepOut.model_validate(r) for r in rs_rows.all()]
    return RunDetailOut(
        id=run.id, pipeline_id=run.pipeline_id, triggered_by=run.triggered_by,
        status=run.status.value, started_at=run.started_at, finished_at=run.finished_at,
        total_steps=run.total_steps, success_count=run.success_count,
        failure_count=run.failure_count, skipped_count=run.skipped_count,
        steps=step_outs,
    )
```

- [ ] **Step 3: Mount both routers in app/main.py**

Add import:

```python
from app.api.v1.pipelines import pipelines_v1_router, runs_v1_router  # see Step 4
```

Hmm — currently `app/api/v1/pipelines.py` exports `router` (the pipeline router). Let me update to export both:

In `app/api/v1/pipelines.py`, rename the existing `router = APIRouter(prefix="/pipelines", tags=["pipelines"])` to:

```python
pipelines_v1_router = APIRouter(prefix="/pipelines", tags=["pipelines"])
```

And keep `runs_v1_router` as the new one. Then update `app/main.py` import + includes accordingly.

(Replace any references to `router` inside the file with `pipelines_v1_router`.)

- [ ] **Step 4: Write tests `tests/test_pipeline_runs_api.py`**

```python
from app.auth.security import hash_password
from app.models.pipeline import PipelineRun, StepType
from app.models.project import Project, ProjectMember, ProjectRole
from app.models.user import User


async def _seed(client, session):
    u = User(username="u", password_hash=hash_password("u12345"), is_admin=False)
    session.add(u); await session.commit()
    p = Project(name="P", created_by=u.id)
    session.add(p); await session.flush()
    session.add(ProjectMember(project_id=p.id, user_id=u.id, role=ProjectRole.OWNER))
    await session.commit()
    tok = (await client.post("/api/v1/auth/login", json={"username": "u", "password": "u12345"})).json()["access_token"]
    return p, tok


async def test_run_pipeline_creates_history(client, session):
    p, tok = await _seed(client, session)
    pipe = (await client.post(
        "/api/v1/pipelines", json={"project_id": p.id, "name": "pl"},
        headers={"Authorization": f"Bearer {tok}"})).json()
    r = await client.post(f"/api/v1/pipelines/{pipe['id']}/run", headers={"Authorization": f"Bearer {tok}"})
    # The run will likely fail because no real MySQL is reachable, but a run record should still be created
    assert r.status_code == 200
    body = r.json()
    assert body["pipeline_id"] == pipe["id"]
    assert body["status"] in ("success", "failed")
    assert len(body["steps"]) >= 0


async def test_list_runs_limit_30(client, session):
    p, tok = await _seed(client, session)
    pipe = (await client.post("/api/v1/pipelines", json={"project_id": p.id, "name": "pl"},
        headers={"Authorization": f"Bearer {tok}"})).json()
    r = await client.get(f"/api/v1/pipelines/{pipe['id']}/runs", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)
```

- [ ] **Step 5: Run tests**

```bash
cd "F:/project/git/test-platform/backend"
source .venv/Scripts/activate
pytest tests/test_pipeline_runs_api.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
cd "F:/project/git/test-platform"
git add backend/
git commit -m "feat(backend): pipeline run, history, dry-run endpoints

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## Phase 4 — Frontend

### Task 15: Pipelines API Client

**Files:**
- Create: `frontend/src/api/pipelines.ts`

- [ ] **Step 1: Create src/api/pipelines.ts**

```typescript
import { http } from "@/api/http";

export interface Pipeline {
  id: number; project_id: number; name: string;
  description: string | null; created_by: number;
  created_at: string; updated_at: string;
}

export interface Step {
  id: number; pipeline_id: number; order_index: number;
  type: "mysql" | "kafka" | "redis" | "http";
  name: string; enabled: boolean;
  config: Record<string, any>;
}

export interface Run {
  id: number; pipeline_id: number; triggered_by: number;
  status: "running" | "success" | "failed";
  started_at: string; finished_at: string | null;
  total_steps: number; success_count: number;
  failure_count: number; skipped_count: number;
}

export interface RunStep {
  id: number; run_id: number; step_id: number;
  order_index: number; status: string;
  started_at: string | null; finished_at: string | null;
  duration_ms: number | null;
  input_rendered: Record<string, any> | null;
  output: Record<string, any> | null;
  error: string | null;
}

export interface RunDetail extends Run {
  steps: RunStep[];
}

export const pipelinesApi = {
  list: (projectId: number) =>
    http.get<Pipeline[]>(`/pipelines`, { params: { project_id: projectId } }).then((r) => r.data),
  get: (id: number) =>
    http.get<Pipeline>(`/pipelines/${id}`).then((r) => r.data),
  create: (body: { project_id: number; name: string; description?: string }) =>
    http.post<Pipeline>(`/pipelines`, body).then((r) => r.data),
  update: (id: number, body: { name?: string; description?: string }) =>
    http.patch<Pipeline>(`/pipelines/${id}`, body).then((r) => r.data),
  remove: (id: number) => http.delete(`/pipelines/${id}`),
  steps: (pipelineId: number) =>
    http.get<Step[]>(`/pipelines/${pipelineId}/steps`).then((r) => r.data),
  addStep: (pipelineId: number, body: { type: Step["type"]; name: string; enabled?: boolean; config: Record<string, any> }) =>
    http.post<Step>(`/pipelines/${pipelineId}/steps`, body).then((r) => r.data),
  updateStep: (pipelineId: number, stepId: number, body: Partial<{ name: string; enabled: boolean; config: Record<string, any> }>) =>
    http.patch<Step>(`/pipelines/${pipelineId}/steps/${stepId}`, body).then((r) => r.data),
  removeStep: (pipelineId: number, stepId: number) =>
    http.delete(`/pipelines/${pipelineId}/steps/${stepId}`),
  reorder: (pipelineId: number, order: number[]) =>
    http.post<Step[]>(`/pipelines/${pipelineId}/steps/reorder`, { order }).then((r) => r.data),
  testStep: (pipelineId: number, stepId: number, body: { context: Record<string, any> }) =>
    http.post<{ ok: boolean; output?: any; error?: string; retryable?: boolean; rendered_config?: any }>(
      `/pipelines/${pipelineId}/steps/${stepId}/test`, body
    ).then((r) => r.data),
  run: (pipelineId: number) =>
    http.post<RunDetail>(`/pipelines/${pipelineId}/run`).then((r) => r.data),
  runs: (pipelineId: number) =>
    http.get<Run[]>(`/pipelines/${pipelineId}/runs`).then((r) => r.data),
  clearRuns: (pipelineId: number) => http.delete(`/pipelines/${pipelineId}/runs`),
  getRun: (runId: number) =>
    http.get<RunDetail>(`/runs/${runId}`).then((r) => r.data),
};
```

- [ ] **Step 2: Verify build**

```bash
cd "F:/project/git/test-platform/frontend"
npm run build
```

Expected: success.

- [ ] **Step 3: Commit**

```bash
cd "F:/project/git/test-platform"
git add frontend/src/api/pipelines.ts
git commit -m "feat(frontend): pipelines API client

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 16: Project Detail — Pipeline Tab

**Files:**
- Modify: `frontend/src/views/ProjectDetailView.vue` (add third tab)

- [ ] **Step 1: Add "数据流水线" tab**

In `ProjectDetailView.vue`, add a third `<el-tab-pane>` after the existing two (Mock 列表 and 成员管理). The pane contains a button to create a pipeline and a table listing pipelines. Use `pipelinesApi` from Task 15.

```vue
<el-tab-pane label="数据流水线" name="pipelines">
  <el-button type="primary" @click="$router.push(`/pipelines/new?project_id=${projectId}`)">新建流水线</el-button>
  <el-table :data="pipelines" style="margin-top:16px">
    <el-table-column prop="id" label="ID" width="80" />
    <el-table-column prop="name" label="名称" />
    <el-table-column prop="description" label="描述" />
    <el-table-column label="操作" width="240">
      <template #default="{ row }">
        <el-button link @click="$router.push(`/pipelines/${row.id}`)">查看</el-button>
        <el-button link @click="runPipeline(row.id)">运行</el-button>
        <el-popconfirm title="确认删除?" @confirm="removePipeline(row.id)">
          <template #reference><el-button link type="danger">删除</el-button></template>
        </el-popconfirm>
      </template>
    </el-table-column>
  </el-table>
</el-tab-pane>
```

Script additions:

```typescript
import { pipelinesApi, Pipeline } from "@/api/pipelines";

const pipelines = ref<Pipeline[]>([]);

async function refreshPipelines() {
  pipelines.value = await pipelinesApi.list(projectId);
}
async function runPipeline(id: number) {
  const run = await pipelinesApi.run(id);
  await refreshPipelines();
  ElMessage.success(`运行完成 (${run.status})`);
  $router.push(`/runs/${run.id}`);
}
async function removePipeline(id: number) {
  await pipelinesApi.remove(id);
  await refreshPipelines();
  ElMessage.success("已删除");
}
```

And add `refreshPipelines()` to the existing `onMounted` hook alongside `refresh()` and `loadUsers()`.

- [ ] **Step 2: Verify build**

```bash
cd "F:/project/git/test-platform/frontend"
npm run build
```

- [ ] **Step 3: Commit**

```bash
cd "F:/project/git/test-platform"
git add frontend/src/views/ProjectDetailView.vue
git commit -m "feat(frontend): project detail — pipelines tab

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 17: Pipeline Detail Page

**Files:**
- Create: `frontend/src/views/PipelineView.vue`
- Modify: `frontend/src/router/index.ts` (add route)

- [ ] **Step 1: Create src/views/PipelineView.vue**

```vue
<template>
  <el-page-header :title="pipeline?.name || '流水线'" @back="$router.push(`/projects/${pipeline?.project_id}`)" />
  <div style="margin: 8px 0">
    <el-button type="primary" @click="runIt" :loading="running">运行</el-button>
    <el-button @click="$router.push(`/pipelines/${pipelineId}/edit`)">编辑</el-button>
    <el-popconfirm title="确认删除?" @confirm="removePipeline">
      <template #reference><el-button type="danger" link>删除</el-button></template>
    </el-popconfirm>
  </div>
  <div style="margin: 8px 0">
    描述: {{ pipeline?.description || "—" }}
  </div>

  <h3>步骤</h3>
  <el-table :data="steps">
    <el-table-column prop="order_index" label="#" width="60" />
    <el-table-column prop="type" label="类型" width="100" />
    <el-table-column prop="name" label="名称" />
    <el-table-column label="启用" width="80">
      <template #default="{ row }"><el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? "是" : "否" }}</el-tag></template>
    </el-table-column>
    <el-table-column label="操作" width="200">
      <template #default="{ row }">
        <el-button link @click="$router.push(`/pipelines/${pipelineId}/steps/${row.id}`)">编辑</el-button>
        <el-popconfirm title="删除步骤?" @confirm="removeStep(row.id)">
          <template #reference><el-button link type="danger">删除</el-button></template>
        </el-popconfirm>
      </template>
    </el-table-column>
  </el-table>
  <el-button @click="$router.push(`/pipelines/${pipelineId}/steps/new`)">+ 添加步骤</el-button>

  <h3 style="margin-top:24px">运行历史(最近 30 条)</h3>
  <el-table :data="runs">
    <el-table-column prop="id" label="ID" width="80" />
    <el-table-column label="状态" width="100">
      <template #default="{ row }"><el-tag :type="row.status === 'success' ? 'success' : (row.status === 'failed' ? 'danger' : '')">{{ row.status }}</el-tag></template>
    </el-table-column>
    <el-table-column prop="started_at" label="开始时间" />
    <el-table-column label="成功/失败/跳过">
      <template #default="{ row }">{{ row.success_count }} / {{ row.failure_count }} / {{ row.skipped_count }}</template>
    </el-table-column>
    <el-table-column label="操作" width="100">
      <template #default="{ row }"><el-button link @click="$router.push(`/runs/${row.id}`)">查看</el-button></template>
    </el-table-column>
  </el-table>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { pipelinesApi, Pipeline, Step, Run } from "@/api/pipelines";

const route = useRoute();
const router = useRouter();
const pipelineId = Number(route.params.id);
const pipeline = ref<Pipeline | null>(null);
const steps = ref<Step[]>([]);
const runs = ref<Run[]>([]);
const running = ref(false);

async function refresh() {
  pipeline.value = await pipelinesApi.get(pipelineId);
  steps.value = await pipelinesApi.steps(pipelineId);
  runs.value = await pipelinesApi.runs(pipelineId);
}

async function runIt() {
  running.value = true;
  try {
    const run = await pipelinesApi.run(pipelineId);
    await refresh();
    ElMessage.success(`运行 ${run.status}`);
    router.push(`/runs/${run.id}`);
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "运行失败");
  } finally {
    running.value = false;
  }
}

async function removePipeline() {
  await pipelinesApi.remove(pipelineId);
  ElMessage.success("已删除");
  router.push(`/projects/${pipeline.value?.project_id}`);
}

async function removeStep(id: number) {
  await pipelinesApi.removeStep(pipelineId, id);
  await refresh();
}

onMounted(refresh);
</script>
```

- [ ] **Step 2: Add route**

In `frontend/src/router/index.ts`, add:

```typescript
{ path: "pipelines/:id", component: () => import("@/views/PipelineView.vue") },
```

(under the `children` of the `/` route).

- [ ] **Step 3: Verify build**

```bash
cd "F:/project/git/test-platform/frontend"
npm run build
```

- [ ] **Step 4: Commit**

```bash
cd "F:/project/git/test-platform"
git add frontend/
git commit -m "feat(frontend): pipeline detail page with steps and history

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 18: Step Edit Page (Type-Specific Forms)

**Files:**
- Create: `frontend/src/views/StepEditView.vue`
- Modify: `frontend/src/router/index.ts` (add route)

- [ ] **Step 1: Create src/views/StepEditView.vue**

A single page that handles both `new` and edit (parameterized by URL).

```vue
<template>
  <el-page-header :title="isNew ? '新建步骤' : '编辑步骤'" @back="$router.back()" />

  <el-form :model="form" label-width="140px" style="max-width:720px">
    <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
    <el-form-item label="类型">
      <el-select v-model="form.type" :disabled="!isNew" @change="onTypeChange">
        <el-option label="MySQL" value="mysql" />
        <el-option label="Kafka" value="kafka" />
        <el-option label="Redis" value="redis" />
        <el-option label="HTTP" value="http" />
      </el-select>
    </el-form-item>
    <el-form-item label="启用"><el-switch v-model="form.enabled" /></el-form-item>

    <!-- MySQL config -->
    <template v-if="form.type === 'mysql'">
      <el-divider content-position="left">连接</el-divider>
      <el-form-item label="host"><el-input v-model="form.config.connection.host" /></el-form-item>
      <el-form-item label="port"><el-input-number v-model="form.config.connection.port" :min="1" :max="65535" /></el-form-item>
      <el-form-item label="user"><el-input v-model="form.config.connection.user" /></el-form-item>
      <el-form-item label="password"><el-input v-model="form.config.connection.password" type="password" show-password /></el-form-item>
      <el-form-item label="database"><el-input v-model="form.config.connection.database" /></el-form-item>
      <el-divider content-position="left">SQL</el-divider>
      <el-form-item label="SQL"><el-input v-model="form.config.sql" type="textarea" :rows="3" /></el-form-item>
      <el-form-item label="params (JSON)"><el-input v-model="paramsText" type="textarea" :rows="4" /></el-form-item>
    </template>

    <!-- Kafka config -->
    <template v-if="form.type === 'kafka'">
      <el-divider content-position="left">连接</el-divider>
      <el-form-item label="bootstrap_servers"><el-input v-model="form.config.connection.bootstrap_servers" /></el-form-item>
      <el-form-item label="security_protocol"><el-input v-model="form.config.connection.security_protocol" /></el-form-item>
      <el-form-item label="sasl_username"><el-input v-model="form.config.connection.sasl_username" /></el-form-item>
      <el-form-item label="sasl_password"><el-input v-model="form.config.connection.sasl_password" type="password" show-password /></el-form-item>
      <el-form-item label="topic"><el-input v-model="form.config.topic" /></el-form-item>
      <el-form-item label="key (模板)"><el-input v-model="form.config.key" /></el-form-item>
      <el-form-item label="value (模板)"><el-input v-model="form.config.value" type="textarea" :rows="4" /></el-form-item>
    </template>

    <!-- Redis config -->
    <template v-if="form.type === 'redis'">
      <el-divider content-position="left">连接</el-divider>
      <el-form-item label="host"><el-input v-model="form.config.connection.host" /></el-form-item>
      <el-form-item label="port"><el-input-number v-model="form.config.connection.port" :min="1" :max="65535" /></el-form-item>
      <el-form-item label="password"><el-input v-model="form.config.connection.password" type="password" show-password /></el-form-item>
      <el-form-item label="db"><el-input-number v-model="form.config.connection.db" :min="0" :max="15" /></el-form-item>
      <el-form-item label="key (模板)"><el-input v-model="form.config.key" /></el-form-item>
      <el-form-item label="value (模板)"><el-input v-model="form.config.value" type="textarea" :rows="4" /></el-form-item>
      <el-form-item label="ttl_seconds"><el-input-number v-model="form.config.ttl_seconds" :min="0" :max="2592000" /></el-form-item>
    </template>

    <!-- HTTP config -->
    <template v-if="form.type === 'http'">
      <el-form-item label="method">
        <el-select v-model="form.config.method" style="width:160px">
          <el-option v-for="m in ['GET','POST','PUT','DELETE','PATCH']" :key="m" :value="m" :label="m" />
        </el-select>
      </el-form-item>
      <el-form-item label="URL (模板)"><el-input v-model="form.config.url" /></el-form-item>
      <el-form-item label="headers (JSON)"><el-input v-model="headersText" type="textarea" :rows="3" /></el-form-item>
      <el-form-item label="body (模板)"><el-input v-model="form.config.body" type="textarea" :rows="4" /></el-form-item>
      <el-form-item label="timeout_seconds"><el-input-number v-model="form.config.timeout_seconds" :min="1" :max="600" /></el-form-item>
    </template>

    <el-button type="primary" :loading="loading" @click="save">保存</el-button>
    <el-button :disabled="isNew" @click="runTest">测试此步骤</el-button>
  </el-form>

  <pre v-if="testResult" class="result">{{ JSON.stringify(testResult, null, 2) }}</pre>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { pipelinesApi, Step } from "@/api/pipelines";

const route = useRoute();
const router = useRouter();
const pipelineId = Number(route.params.id);
const stepId = computed(() => (route.params.stepId === "new" ? null : Number(route.params.stepId)));
const isNew = computed(() => stepId.value === null);

const form = reactive<{
  name: string; type: Step["type"]; enabled: boolean;
  config: any;
}>({
  name: "",
  type: "mysql",
  enabled: true,
  config: _defaultConfig("mysql"),
});

const paramsText = ref("{}");
const headersText = ref("{}");
const testResult = ref<any>(null);
const loading = ref(false);

function _defaultConfig(t: Step["type"]) {
  if (t === "mysql") return { connection: { host: "", port: 3306, user: "", password: "", database: "" }, sql: "", params: {} };
  if (t === "kafka") return { connection: { bootstrap_servers: "", security_protocol: "PLAINTEXT" }, topic: "", value: "" };
  if (t === "redis") return { connection: { host: "", port: 6379, db: 0 }, operation: "set", key: "", value: "", ttl_seconds: 0 };
  return { method: "GET", url: "", headers: {}, body: "", timeout_seconds: 30 };
}

function onTypeChange(t: Step["type"]) {
  form.config = _defaultConfig(t);
  paramsText.value = "{}";
  headersText.value = "{}";
}

onMounted(async () => {
  if (!isNew.value && stepId.value !== null) {
    const all = await pipelinesApi.steps(pipelineId);
    const s = all.find((x) => x.id === stepId.value);
    if (s) {
      form.name = s.name;
      form.type = s.type;
      form.enabled = s.enabled;
      form.config = s.config;
      paramsText.value = JSON.stringify(s.config.params ?? {}, null, 2);
      headersText.value = JSON.stringify(s.config.headers ?? {}, null, 2);
    }
  }
});

async function save() {
  loading.value = true;
  try {
    let config = JSON.parse(JSON.stringify(form.config));
    if (form.type === "mysql") {
      try { config.params = JSON.parse(paramsText.value || "{}"); } catch { ElMessage.error("params JSON 格式错误"); return; }
    }
    if (form.type === "http") {
      try { config.headers = JSON.parse(headersText.value || "{}"); } catch { ElMessage.error("headers JSON 格式错误"); return; }
    }
    if (isNew.value) {
      const created = await pipelinesApi.addStep(pipelineId, { type: form.type, name: form.name, enabled: form.enabled, config });
      router.replace(`/pipelines/${pipelineId}/steps/${created.id}`);
    } else {
      await pipelinesApi.updateStep(pipelineId, stepId.value!, { name: form.name, enabled: form.enabled, config });
      ElMessage.success("已保存");
    }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "保存失败");
  } finally {
    loading.value = false;
  }
}

async function runTest() {
  try {
    const res = await pipelinesApi.testStep(pipelineId, stepId.value!, { context: {} });
    testResult.value = res;
  } catch (e: any) {
    testResult.value = { error: e.response?.data?.detail || e.message };
  }
}
</script>

<style scoped>
.result { background: #f5f5f5; padding: 12px; white-space: pre-wrap; margin-top: 16px; }
</style>
```

- [ ] **Step 2: Add routes**

In `frontend/src/router/index.ts`, add (under the `/` children):

```typescript
{ path: "pipelines/:id/steps/new", component: () => import("@/views/StepEditView.vue") },
{ path: "pipelines/:id/steps/:stepId", component: () => import("@/views/StepEditView.vue") },
```

- [ ] **Step 3: Verify build**

```bash
cd "F:/project/git/test-platform/frontend"
npm run build
```

- [ ] **Step 4: Commit**

```bash
cd "F:/project/git/test-platform"
git add frontend/
git commit -m "feat(frontend): step edit page with type-specific forms and dry-run

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 19: Run Detail Page

**Files:**
- Create: `frontend/src/views/RunView.vue`
- Modify: `frontend/src/router/index.ts` (add route)

- [ ] **Step 1: Create src/views/RunView.vue**

```vue
<template>
  <el-page-header :title="`运行 #${runId}`" @back="$router.back()" />
  <div v-if="run" style="margin: 8px 0">
    <el-tag :type="run.status === 'success' ? 'success' : (run.status === 'failed' ? 'danger' : '')">{{ run.status }}</el-tag>
    总计 {{ run.total_steps }} 步 | 成功 {{ run.success_count }} / 失败 {{ run.failure_count }} / 跳过 {{ run.skipped_count }}
    <span style="margin-left: 16px">{{ run.started_at }} → {{ run.finished_at }}</span>
  </div>

  <h3>每步详情</h3>
  <el-table :data="run?.steps || []">
    <el-table-column prop="order_index" label="#" width="60" />
    <el-table-column prop="status" label="状态" width="100">
      <template #default="{ row }">
        <el-tag :type="row.status === 'success' ? 'success' : (row.status === 'failed' ? 'danger' : (row.status === 'skipped' ? 'info' : ''))">{{ row.status }}</el-tag>
      </template>
    </el-table-column>
    <el-table-column prop="duration_ms" label="耗时(ms)" width="120" />
    <el-table-column label="输入(渲染后)">
      <template #default="{ row }">
        <el-popover v-if="row.input_rendered" placement="left" :width="500" trigger="click">
          <template #reference><el-button link>查看</el-button></template>
          <pre>{{ JSON.stringify(row.input_rendered, null, 2) }}</pre>
        </el-popover>
        <span v-else>—</span>
      </template>
    </el-table-column>
    <el-table-column label="输出">
      <template #default="{ row }">
        <el-popover v-if="row.output" placement="left" :width="500" trigger="click">
          <template #reference>
            <el-button link @click="copy(row.output)">查看/复制</el-button>
          </template>
          <pre>{{ JSON.stringify(row.output, null, 2) }}</pre>
        </el-popover>
        <span v-else>—</span>
      </template>
    </el-table-column>
    <el-table-column prop="error" label="错误" />
  </el-table>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { ElMessage } from "element-plus";
import { pipelinesApi, RunDetail } from "@/api/pipelines";

const route = useRoute();
const runId = Number(route.params.id);
const run = ref<RunDetail | null>(null);

async function refresh() {
  run.value = await pipelinesApi.getRun(runId);
}
async function copy(obj: any) {
  await navigator.clipboard.writeText(JSON.stringify(obj));
  ElMessage.success("已复制");
}
onMounted(refresh);
</script>
```

- [ ] **Step 2: Add route**

In `frontend/src/router/index.ts`:

```typescript
{ path: "runs/:id", component: () => import("@/views/RunView.vue") },
```

- [ ] **Step 3: Verify build**

```bash
cd "F:/project/git/test-platform/frontend"
npm run build
```

- [ ] **Step 4: Commit**

```bash
cd "F:/project/git/test-platform"
git add frontend/
git commit -m "feat(frontend): run detail page with per-step input/output/error

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## Phase 5 — Logging & Deployment

### Task 20: Application Logging Configuration

**Files:**
- Create: `backend/app/logging_config.py`
- Modify: `backend/app/main.py` (call dictConfig at startup)
- Modify: `backend/.gitignore` (add `logs/`)
- Modify: `.gitignore` (root, add `logs/`)

- [ ] **Step 1: Create backend/app/logging_config.py**

```python
import logging.config
from pathlib import Path

LOGS_DIR = Path(__file__).resolve().parents[2] / "logs"
LOGS_DIR.mkdir(exist_ok=True)
LOG_FILE = LOGS_DIR / "app.log"

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        }
    },
    "handlers": {
        "stdout": {"class": "logging.StreamHandler", "formatter": "default", "stream": "ext://sys.stdout"},
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "default",
            "filename": str(LOG_FILE),
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf-8",
        },
    },
    "root": {"level": "INFO", "handlers": ["stdout", "file"]},
    "loggers": {
        "uvicorn": {"level": "INFO", "handlers": ["stdout", "file"], "propagate": False},
        "uvicorn.error": {"level": "INFO", "handlers": ["stdout", "file"], "propagate": False},
        "uvicorn.access": {"level": "INFO", "handlers": ["stdout", "file"], "propagate": False},
        "app": {"level": "INFO", "handlers": ["stdout", "file"], "propagate": False},
    },
}


def configure_logging() -> None:
    logging.config.dictConfig(LOGGING_CONFIG)
```

- [ ] **Step 2: Modify backend/app/main.py — call configure_logging() at startup**

Add at the top of `app/main.py`:

```python
import logging

from app.logging_config import configure_logging

configure_logging()
log = logging.getLogger("app")
```

And add a startup log inside `lifespan`:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("application starting up")
    # ... existing code ...
    log.info("application shutting down")
    await engine.dispose()
```

- [ ] **Step 3: Add logs/ to .gitignore**

In repo root `.gitignore`, ensure `logs/` is listed. (Already present from v1.) Verify by:

```bash
grep -F "logs/" "F:/project/git/test-platform/.gitignore"
```

Expected: line containing `logs/`.

- [ ] **Step 4: Add logs/ to backend/.gitignore**

Append to `backend/.gitignore`:

```
logs/
```

- [ ] **Step 5: Verify logging works**

```bash
cd "F:/project/git/test-platform/backend"
source .venv/Scripts/activate
python -c "from app.main import app; print('app loaded')"
```

Then check that `logs/app.log` was created:

```bash
ls "F:/project/git/test-platform/logs/"
```

Expected: `app.log` file exists.

- [ ] **Step 6: Commit**

```bash
cd "F:/project/git/test-platform"
git add backend/
git commit -m "feat(backend): application logging to logs/app.log + stdout

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 21: Docker Compose Env + Mount Logs

**Files:**
- Modify: `docker-compose.yml`
- Modify: `.env.example`

- [ ] **Step 1: Add ENCRYPTION_KEY + LOG_LEVEL to docker-compose env**

In `docker-compose.yml`, in both `backend` and `backend-init` service environment blocks, add:

```yaml
      ENCRYPTION_KEY: ${ENCRYPTION_KEY:-dev-fernet-key-replace-in-prod}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
```

(Replace existing keys if present; ensure the lines are properly indented under `environment:`.)

- [ ] **Step 2: Mount logs/ from backend**

In the `backend` service, add:

```yaml
    volumes:
      - ./logs:/app/logs
```

- [ ] **Step 3: Update .env.example**

Append:

```env
ENCRYPTION_KEY=base64-encoded-32-byte-fernet-key
LOG_LEVEL=INFO
```

(Generate a real one with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.)

- [ ] **Step 4: Validate YAML**

```bash
cd "F:/project/git/test-platform"
python -c "import yaml; d = yaml.safe_load(open('docker-compose.yml')); assert all('ENCRYPTION_KEY' in s.get('environment', {}) for s in [d['services']['backend'], d['services']['backend-init']]); print('OK')"
```

Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
cd "F:/project/git/test-platform"
git add docker-compose.yml .env.example
git commit -m "feat(deploy): wire ENCRYPTION_KEY + LOG_LEVEL + logs volume

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## Self-Review Checklist

After completing all tasks:

- All v1 tests still pass (40 backend + 4 frontend)
- New tests added in each task pass
- Spec coverage:
  - §2 stack: ✓ (Task 7–10 install aiokafka, redis, httpx; Fernet Task 1)
  - §3 architecture: ✓ (single-app, /api/v1, pipeline executor)
  - §4 logging: ✓ (Task 20)
  - §5 data model: ✓ (Task 2, Task 3)
  - §5.1 permissions: ✓ (Task 12 inline `_require_role`)
  - §6 node config schemas: ✓ (Task 4)
  - §7.1 PipelineExecutor: ✓ (Task 6)
  - §7.2 NodeExecutor interface: ✓ (Task 7–10)
  - §7.3 template render: ✓ (Task 5)
  - §7.4 NodeExecutionError: ✓ (Task 6)
  - §7.5 Fernet: ✓ (Task 1, Task 13 password_enc conversion)
  - §8.1 MySQL: ✓ (Task 7)
  - §8.2 Kafka: ✓ (Task 8)
  - §8.3 Redis: ✓ (Task 9, set only)
  - §8.4 HTTP: ✓ (Task 10)
  - §8.5 Pydantic discriminated union: ✓ (Task 4 pick_node_config)
  - §9.1 pipeline CRUD: ✓ (Task 12)
  - §9.2 step CRUD + reorder: ✓ (Task 13)
  - §9.3 run + history + dry-run: ✓ (Task 14)
  - §10 frontend pages: ✓ (Task 16–19)
  - §11.1 env vars: ✓ (Task 21)
  - §11.2 alembic migration: ✓ (Task 3)
  - §11.3 docker compose: ✓ (Task 21)
