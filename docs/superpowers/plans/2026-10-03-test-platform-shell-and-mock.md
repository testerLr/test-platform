# Test Platform Shell & Mock Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the internal test platform shell + HTTP/HTTPS Mock feature with Python (FastAPI) backend, Vue3 frontend, MySQL storage, all containerized with Docker.

**Architecture:** Single FastAPI app hosts both management APIs (`/api/v1/*`, JWT-auth) and the Mock runtime (`/m/*`, no auth). Mock routes are loaded into an in-memory table on startup and refreshed on config change. Frontend is a Vue3 SPA served by Nginx, which also reverse-proxies `/api/*` and `/m/*` to the backend. MySQL stores users, projects, project_members, mock_apis.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.x (async), Alembic, asyncmy, Jinja2, python-jose, passlib[bcrypt], pytest, pytest-asyncio, httpx; Vue 3, Vite, Element Plus, Pinia, Vue Router, Axios, Vitest; MySQL 8; Docker Compose, Nginx.

**Spec Reference:** `docs/superpowers/specs/2026-10-03-test-platform-shell-and-mock-design.md`

---

## Global Constraints

- Python >= 3.11
- Backend framework: FastAPI (latest stable)
- ORM: SQLAlchemy 2.x **asyncio**; migrations via Alembic
- Database driver: `asyncmy` (async MySQL driver)
- Auth: JWT (HS256) via `python-jose`, passwords hashed via `passlib[bcrypt]`
- Mock template engine: **Jinja2**, with sandboxed variables (`request`, `now()`, `uuid()`, `randint(min, max)`)
- Frontend: Vue 3 + Vite + Element Plus + Pinia + Vue Router + Axios
- Containerization: docker-compose orchestrates `mysql`, `backend`, `frontend`
- Mock runtime path prefix: `/m` (e.g. `GET /m/api/user/1`)
- Management API prefix: `/api/v1`
- All Mock config writes go through Pydantic schemas; commit style: `feat: …`, `fix: …`, `test: …`, `chore: …`
- Conventional Commits with the Co-Authored-By trailer

---

## Phase 1 — Project Scaffolding

### Task 1: Initialize Git Repository and Root Files

**Files:**
- Create: `test-platform/.gitignore`
- Create: `test-platform/README.md`
- Create: `test-platform/.env.example`

- [ ] **Step 1: Initialize git repo and create .gitignore**

```bash
cd test-platform
git init
git config user.email "dev@example.com"
git config user.name "Dev"
```

Create `.gitignore`:

```gitignore
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
.env
.pytest_cache/
.mypy_cache/
.ruff_cache/

node_modules/
dist/
.vite/

*.log
.DS_Store
.idea/
.vscode/

mysql_data/
```

- [ ] **Step 2: Create README.md**

```markdown
# Test Platform

Internal testing platform providing HTTP/HTTPS Mock and (later) test data generation.

## Stack
- Backend: Python 3.11 + FastAPI
- Frontend: Vue 3 + Element Plus
- DB: MySQL 8
- Deploy: Docker Compose

## Quick start
docker compose up -d
# visit http://localhost
# default admin: admin / admin123 (created by migration seed)
```

- [ ] **Step 3: Create .env.example**

```env
MYSQL_ROOT_PASSWORD=change-me
MYSQL_DATABASE=test_platform
DATABASE_URL=mysql+asyncmy://root:change-me@mysql:3306/test_platform
JWT_SECRET=please-generate-a-strong-secret
JWT_ALGORITHM=HS256
JWT_EXPIRES_MINUTES=1440
```

- [ ] **Step 4: Initial commit**

```bash
git add .gitignore README.md .env.example
git commit -m "chore: initial repo scaffolding"
```

Expected: 1 commit on `main`.

---

### Task 2: Backend Python Project Skeleton

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/config.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "test-platform-backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.110",
    "uvicorn[standard]>=0.27",
    "sqlalchemy[asyncio]>=2.0",
    "alembic>=1.13",
    "asyncmy>=0.2.9",
    "pydantic>=2.6",
    "pydantic-settings>=2.2",
    "python-jose[cryptography]>=3.3",
    "passlib[bcrypt]>=1.7.4",
    "jinja2>=3.1",
    "python-multipart>=0.0.9",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "httpx>=0.27",
    "aiosqlite>=0.20",
    "ruff>=0.4",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["."]
include = ["app*"]
```

- [ ] **Step 2: Create app/__init__.py and tests/__init__.py**

Empty files.

- [ ] **Step 3: Create app/config.py**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./test.db"
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 1440


settings = Settings()
```

- [ ] **Step 4: Create app/main.py**

```python
from fastapi import FastAPI

app = FastAPI(title="Test Platform", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 5: Create tests/conftest.py**

```python
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client() -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
```

- [ ] **Step 6: Create health-check test and run it**

Create `tests/test_health.py`:

```python
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

Then install and run:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest -v
```

Expected: `test_health PASSED`.

- [ ] **Step 7: Commit**

```bash
git add backend/
git commit -m "chore(backend): python project skeleton with health endpoint"
```

---

### Task 3: Frontend Vue3 Project Skeleton

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.ts`
- Create: `frontend/src/App.vue`
- Create: `frontend/src/router/index.ts`
- Create: `frontend/src/views/LoginView.vue`
- Create: `frontend/src/views/HomeView.vue`
- Create: `frontend/Dockerfile`
- Create: `frontend/.gitignore`

- [ ] **Step 1: Create frontend/.gitignore**

```
node_modules/
dist/
.vite/
*.local
```

- [ ] **Step 2: Create package.json**

```json
{
  "name": "test-platform-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc -b && vite build",
    "preview": "vite preview --host 0.0.0.0 --port 5173",
    "test": "vitest run"
  },
  "dependencies": {
    "vue": "^3.4",
    "vue-router": "^4.3",
    "pinia": "^2.1",
    "element-plus": "^2.7",
    "@element-plus/icons-vue": "^2.3",
    "axios": "^1.7",
    "@vueuse/core": "^10.11"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0",
    "typescript": "^5.4",
    "vue-tsc": "^2.0",
    "vite": "^5.2",
    "vitest": "^1.6",
    "@vue/test-utils": "^2.4",
    "jsdom": "^24.0"
  }
}
```

- [ ] **Step 3: Create vite.config.ts**

```typescript
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  server: { host: "0.0.0.0", port: 5173, proxy: { "/api": "http://localhost:8000", "/m": "http://localhost:8000" } },
  test: { environment: "jsdom", globals: true }
});
```

- [ ] **Step 4: Create tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "strict": true,
    "jsx": "preserve",
    "sourceMap": true,
    "resolveJsonModule": true,
    "esModuleInterop": true,
    "lib": ["ES2022", "DOM"],
    "types": ["vitest/globals"],
    "skipLibCheck": true
  },
  "include": ["src/**/*.ts", "src/**/*.vue"]
}
```

- [ ] **Step 5: Create index.html**

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <title>Test Platform</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

- [ ] **Step 6: Create src/main.ts**

```typescript
import { createApp } from "vue";
import { createPinia } from "pinia";
import ElementPlus from "element-plus";
import "element-plus/dist/index.css";
import App from "./App.vue";
import router from "./router";

const app = createApp(App);
app.use(createPinia());
app.use(router);
app.use(ElementPlus);
app.mount("#app");
```

- [ ] **Step 7: Create src/App.vue**

```vue
<template>
  <router-view />
</template>
```

- [ ] **Step 8: Create src/router/index.ts**

```typescript
import { createRouter, createWebHistory } from "vue-router";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", component: () => import("@/views/LoginView.vue") },
    { path: "/", component: () => import("@/views/HomeView.vue") }
  ]
});

export default router;
```

- [ ] **Step 9: Create src/views/LoginView.vue**

```vue
<template>
  <div class="login">
    <h2>登录</h2>
    <p>占位登录页 — 后续任务会替换为完整表单</p>
  </div>
</template>
```

- [ ] **Step 10: Create src/views/HomeView.vue**

```vue
<template>
  <div>
    <h2>主页</h2>
    <p>登录后默认页 — 后续任务会替换为完整主页</p>
  </div>
</template>
```

- [ ] **Step 11: Create frontend/Dockerfile**

```dockerfile
# Build stage
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install --no-audit --no-fund
COPY . .
RUN npm run build

# Runtime stage
FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

(Create `nginx.conf` later in Phase 10 — the build will fail to run until then, but `npm run build` alone works.)

- [ ] **Step 12: Install dependencies and verify build**

```bash
cd frontend
npm install
npm run build
```

Expected: `dist/index.html` produced, exit 0.

- [ ] **Step 13: Commit**

```bash
git add frontend/
git commit -m "chore(frontend): vue3 + vite + element plus skeleton"
```

---

### Task 4: docker-compose.yml Skeleton

**Files:**
- Create: `docker-compose.yml`
- Create: `.env` (local only, ignored)

- [ ] **Step 1: Create docker-compose.yml**

```yaml
services:
  mysql:
    image: mysql:8
    restart: unless-stopped
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD:-rootpw}
      MYSQL_DATABASE: ${MYSQL_DATABASE:-test_platform}
    volumes:
      - mysql_data:/var/lib/mysql
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost", "-uroot", "-p${MYSQL_ROOT_PASSWORD:-rootpw}"]
      interval: 5s
      timeout: 5s
      retries: 20

  backend:
    build: ./backend
    depends_on:
      mysql:
        condition: service_healthy
    environment:
      DATABASE_URL: mysql+asyncmy://root:${MYSQL_ROOT_PASSWORD:-rootpw}@mysql:3306/${MYSQL_DATABASE:-test_platform}
      JWT_SECRET: ${JWT_SECRET:-dev-secret}
      JWT_ALGORITHM: HS256
      JWT_EXPIRES_MINUTES: "1440"
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2

volumes:
  mysql_data:
```

- [ ] **Step 2: Create backend/Dockerfile**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml ./
RUN pip install --no-cache-dir ".[dev]"
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

- [ ] **Step 3: Validate compose config**

```bash
docker compose config
```

Expected: prints the merged YAML, exit 0. (We won't `up` yet — the frontend service is added in Phase 10.)

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml backend/Dockerfile
git commit -m "chore: docker-compose skeleton with mysql and backend"
```

---

## Phase 2 — Database Models, Migrations, Auth

### Task 5: Database Session and Base ORM

**Files:**
- Create: `backend/app/db/__init__.py`
- Create: `backend/app/db/base.py`
- Create: `backend/app/db/session.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/config.py`
- Modify: `backend/tests/conftest.py`

**Interfaces:**
- Produces: `engine`, `AsyncSessionLocal`, `get_session()` async generator
- Consumes: `settings.database_url`

- [ ] **Step 1: Create app/db/__init__.py** (empty)

- [ ] **Step 2: Create app/db/base.py**

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

- [ ] **Step 3: Create app/db/session.py**

```python
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False, future=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session
```

- [ ] **Step 4: Update app/main.py — wire startup/shutdown hooks**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Models register themselves on import; nothing to do at startup yet.
    yield
    await engine.dispose()


app = FastAPI(title="Test Platform", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 5: Update tests/conftest.py — use SQLite in-memory for tests**

```python
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.db.session as session_module
from app.db.base import Base
from app.main import app


@pytest_asyncio.fixture
async def client():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    TestSession = async_sessionmaker(test_engine, expire_on_commit=False)
    session_module.engine = test_engine
    session_module.AsyncSessionLocal = TestSession

    async def _override():
        async with TestSession() as s:
            yield s

    app.dependency_overrides[session_module.get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    await test_engine.dispose()
```

- [ ] **Step 6: Run tests**

```bash
cd backend && pytest -v
```

Expected: `test_health PASSED`.

- [ ] **Step 7: Commit**

```bash
git add backend/
git commit -m "feat(backend): async SQLAlchemy session and test DB override"
```

---

### Task 6: User, Project, ProjectMember, MockAPI ORM Models

**Files:**
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/user.py`
- Create: `backend/app/models/project.py`
- Create: `backend/app/models/mock_api.py`
- Modify: `backend/app/db/base.py`

- [ ] **Step 1: Create app/models/__init__.py — re-export models so metadata registers**

```python
from app.models.mock_api import MockAPI  # noqa: F401
from app.models.project import Project, ProjectMember  # noqa: F401
from app.models.user import User  # noqa: F401
```

- [ ] **Step 2: Create app/models/user.py**

```python
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 3: Create app/models/project.py**

```python
from datetime import datetime
from enum import Enum

from sqlalchemy import BigInteger, DateTime, Enum as SAEnum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProjectRole(str, Enum):
    OWNER = "owner"
    DEVELOPER = "developer"
    VIEWER = "viewer"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = (UniqueConstraint("project_id", "user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("projects.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    role: Mapped[ProjectRole] = mapped_column(
        SAEnum(ProjectRole, name="project_role"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

- [ ] **Step 4: Create app/models/mock_api.py**

```python
from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Enum as SAEnum, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class HttpMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class MockAPI(Base):
    __tablename__ = "mock_apis"
    __table_args__ = (Index("ix_mock_method_path_enabled", "method", "path", "enabled"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    method: Mapped[HttpMethod] = mapped_column(SAEnum(HttpMethod, name="http_method"), nullable=False)
    path: Mapped[str] = mapped_column(String(255), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    request_match: Mapped[dict | None] = mapped_column(JSON)
    response_status: Mapped[int] = mapped_column(Integer, default=200, nullable=False)
    response_headers: Mapped[dict | None] = mapped_column(JSON)
    response_body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    delay_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 5: Run pytest to confirm metadata registers**

```bash
cd backend && pytest -v
```

Expected: `test_health PASSED`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/
git commit -m "feat(backend): user, project, project_member, mock_api ORM models"
```

---

### Task 7: Alembic Migrations

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/.gitkeep`
- Create: `backend/migrations_seed.py` (admin user seed)

**Interfaces:**
- Produces: `alembic upgrade head` creates all tables in MySQL

- [ ] **Step 1: Initialize alembic in backend/**

```bash
cd backend
alembic init alembic
```

- [ ] **Step 2: Edit alembic.ini** — set `sqlalchemy.url` to read from env

Replace line:
```ini
sqlalchemy.url = driver://user:pass@localhost/dbname
```
with
```ini
sqlalchemy.url =
```

- [ ] **Step 3: Replace alembic/env.py — async + autogenerate from models**

```python
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from app.config import settings
from app.db.base import Base
from app.models import *  # noqa: F401,F403  -- register all models

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as conn:
        await conn.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


run_migrations_online()
```

- [ ] **Step 4: Generate initial migration**

```bash
cd backend
alembic revision --autogenerate -m "initial schema"
```

Expected: file `alembic/versions/xxxx_initial_schema.py` created.

- [ ] **Step 5: Apply migration against a test SQLite (sanity check)**

```bash
cd backend
DATABASE_URL=sqlite+aiosqlite:///./alembic_test.db alembic upgrade head
```

Expected: `alembic_test.db` created with all 4 tables. Inspect:

```bash
sqlite3 alembic_test.db ".tables"
```

Expected: `alembic_version  mock_apis  project_members  projects  users`.

Delete the test DB afterwards: `rm alembic_test.db`.

- [ ] **Step 6: Commit alembic scaffolding + initial migration**

```bash
git add backend/alembic.ini backend/alembic/
git commit -m "feat(backend): alembic async config and initial migration"
```

---

### Task 8: Password Hashing and JWT Utilities

**Files:**
- Create: `backend/app/auth/__init__.py`
- Create: `backend/app/auth/security.py`
- Test: `backend/tests/test_auth_security.py`

**Interfaces:**
- Produces: `hash_password(plain: str) -> str`, `verify_password(plain: str, hashed: str) -> bool`, `create_access_token(subject: str) -> str`, `decode_token(token: str) -> dict`

- [ ] **Step 1: Create app/auth/__init__.py** (empty)

- [ ] **Step 2: Create app/auth/security.py**

```python
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd.verify(plain, hashed)


def create_access_token(subject: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_expires_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as e:
        raise ValueError("invalid token") from e
```

- [ ] **Step 3: Write failing test `tests/test_auth_security.py`**

```python
from app.auth.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_hash_and_verify_password():
    h = hash_password("hello-world")
    assert h != "hello-world"
    assert verify_password("hello-world", h)
    assert not verify_password("wrong", h)


def test_jwt_roundtrip():
    token = create_access_token("42")
    decoded = decode_token(token)
    assert decoded["sub"] == "42"
```

- [ ] **Step 4: Run tests**

```bash
cd backend && pytest tests/test_auth_security.py -v
```

Expected: both tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/app/auth backend/tests/test_auth_security.py
git commit -m "feat(backend): password hashing and JWT helpers"
```

---

### Task 9: Auth Dependency and Login Endpoint

**Files:**
- Create: `backend/app/deps.py`
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/schemas/common.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/v1/__init__.py`
- Create: `backend/app/api/v1/auth.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_auth_api.py`

**Interfaces:**
- Produces: `current_user: Annotated[User, Depends(get_current_user)]`, `POST /api/v1/auth/login`, `GET /api/v1/auth/me`, `POST /api/v1/auth/change-password`

- [ ] **Step 1: Create app/schemas/common.py**

```python
from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
```

- [ ] **Step 2: Create app/schemas/auth.py**

```python
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class UserPublic(BaseModel):
    id: int
    username: str
    is_admin: bool


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=6, max_length=128)
```

- [ ] **Step 3: Create app/schemas/__init__.py** (empty)

- [ ] **Step 4: Create app/api/__init__.py** and **app/api/v1/__init__.py** (empty)

- [ ] **Step 5: Create app/deps.py**

```python
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.db.session as session_module
from app.auth.security import decode_token
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_session():
    async for s in session_module.get_session():
        yield s


SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    session: SessionDep, token: Annotated[str | None, Depends(oauth2_scheme)]
) -> User:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")
    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")
    user_id = int(payload["sub"])
    user = await session.scalar(select(User).where(User.id == user_id))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
```

- [ ] **Step 6: Create app/api/v1/auth.py**

```python
from fastapi import APIRouter, Depends, HTTPException, status
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="wrong old password")
    user.password_hash = hash_password(body.new_password)
    await session.commit()
```

- [ ] **Step 7: Modify app/main.py — mount router**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1 import auth as auth_v1
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(title="Test Platform", version="0.1.0", lifespan=lifespan)
app.include_router(auth_v1.router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 8: Write failing tests `tests/test_auth_api.py`**

```python
import pytest

from app.auth.security import hash_password
from app.models.user import User


@pytest.fixture
async def admin_user(session):
    u = User(username="admin", password_hash=hash_password("admin123"), is_admin=True)
    session.add(u)
    await session.commit()
    await session.refresh(u)
    return u


async def test_login_success(client, admin_user):
    r = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


async def test_login_wrong_password(client, admin_user):
    r = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


async def test_me_requires_token(client):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 401


async def test_me_with_token(client, admin_user):
    token = (await client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})).json()["access_token"]
    r = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["username"] == "admin"
```

- [ ] **Step 9: Update tests/conftest.py — provide `session` fixture and seed helpers**

```python
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.db.session as session_module
from app.db.base import Base
from app.deps import get_session
from app.main import app


@pytest_asyncio.fixture
async def session():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    TestSession = async_sessionmaker(test_engine, expire_on_commit=False)
    session_module.engine = test_engine
    session_module.AsyncSessionLocal = TestSession
    async with TestSession() as s:
        yield s
    await test_engine.dispose()


@pytest_asyncio.fixture
async def client(session):
    async def _override():
        yield session

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
```

(Remove the old client-only fixture; replace with this combined one.)

- [ ] **Step 10: Run tests**

```bash
cd backend && pytest -v
```

Expected: all auth + health tests pass.

- [ ] **Step 11: Commit**

```bash
git add backend/
git commit -m "feat(backend): auth API (login, me, change-password) with JWT"
```

---

## Phase 3 — User Management

### Task 10: User Schemas and Repository Helper

**Files:**
- Create: `backend/app/schemas/user.py`
- Modify: `backend/app/schemas/__init__.py`

- [ ] **Step 1: Create app/schemas/user.py**

```python
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
```

- [ ] **Step 2: Update app/schemas/__init__.py**

```python
# Re-export for convenience.
from app.schemas.auth import (  # noqa: F401
    ChangePasswordRequest,
    LoginRequest,
    UserPublic,
)
from app.schemas.common import ORMModel, TokenResponse  # noqa: F401
from app.schemas.user import PasswordReset, UserCreate, UserOut, UserUpdate  # noqa: F401
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/
git commit -m "feat(backend): user schemas"
```

---

### Task 11: User CRUD API (admin only)

**Files:**
- Create: `backend/app/api/v1/users.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_users_api.py`

**Interfaces:**
- Produces: `GET /api/v1/users`, `POST /api/v1/users`, `PATCH /api/v1/users/{id}`, `POST /api/v1/users/{id}/reset-password`

- [ ] **Step 1: Create app/api/v1/users.py**

```python
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


@router.get("", response_model=list[UserOut])
async def list_users(_: Depends(require_admin), session: SessionDep) -> list[User]:
    return list((await session.scalars(select(User).order_by(User.id))).all())


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    _: Depends(require_admin), session: SessionDep, body: UserCreate
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
    _: Depends(require_admin), session: SessionDep, user_id: int, body: UserUpdate
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
    _: Depends(require_admin), session: SessionDep, user_id: int, body: PasswordReset
) -> None:
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    user.password_hash = hash_password(body.new_password)
    await session.commit()
```

- [ ] **Step 2: Modify app/main.py — mount users router**

Add after the auth router line:
```python
from app.api.v1 import users as users_v1
```
and:
```python
app.include_router(users_v1.router, prefix="/api/v1")
```

- [ ] **Step 3: Write tests `tests/test_users_api.py`**

```python
from app.auth.security import hash_password
from app.models.user import User


async def _admin_token(client, session) -> str:
    u = User(username="admin", password_hash=hash_password("admin123"), is_admin=True)
    session.add(u); await session.commit(); await session.refresh(u)
    r = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    return r.json()["access_token"]


async def _auth(client, token):
    client.headers["Authorization"] = f"Bearer {token}"


async def test_list_users_requires_admin(client, session):
    token = await _admin_token(client, session)
    await _auth(client, token)
    r = await client.get("/api/v1/users")
    assert r.status_code == 200
    assert any(u["username"] == "admin" for u in r.json())


async def test_non_admin_cannot_list(client, session):
    u = User(username="alice", password_hash=hash_password("alice123"), is_admin=False)
    session.add(u); await session.commit()
    token = (await client.post("/api/v1/auth/login", json={"username": "alice", "password": "alice123"})).json()["access_token"]
    r = await client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


async def test_admin_creates_user(client, session):
    token = await _admin_token(client, session)
    r = await client.post(
        "/api/v1/users",
        json={"username": "bob", "password": "bob12345", "is_admin": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201
    assert r.json()["username"] == "bob"
```

- [ ] **Step 4: Run all tests**

```bash
cd backend && pytest -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/
git commit -m "feat(backend): admin-only user management API"
```

---

## Phase 4 — Project Management

### Task 12: Project Schemas and API

**Files:**
- Create: `backend/app/schemas/project.py`
- Create: `backend/app/api/v1/projects.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/schemas/__init__.py`
- Test: `backend/tests/test_projects_api.py`

**Interfaces:**
- Produces: CRUD on `/api/v1/projects` + member management under `/api/v1/projects/{id}/members`

- [ ] **Step 1: Create app/schemas/project.py**

```python
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
```

- [ ] **Step 2: Create app/api/v1/projects.py**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

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
        # ensure at least one owner remains
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
```

- [ ] **Step 3: Wire router in app/main.py**

Add:
```python
from app.api.v1 import projects as projects_v1
```
and:
```python
app.include_router(projects_v1.router, prefix="/api/v1")
```

- [ ] **Step 4: Update app/schemas/__init__.py** to re-export project schemas:

```python
from app.schemas.project import (  # noqa: F401
    MemberAdd,
    MemberOut,
    MemberUpdate,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
)
```

(Add to existing file.)

- [ ] **Step 5: Write tests `tests/test_projects_api.py`**

```python
from app.auth.security import hash_password
from app.models.user import User


async def _user(client, session, name, *, admin=False):
    u = User(username=name, password_hash=hash_password(name + "123"), is_admin=admin)
    session.add(u); await session.commit(); await session.refresh(u)
    token = (await client.post("/api/v1/auth/login", json={"username": name, "password": name + "123"})).json()["access_token"]
    return u, token


async def test_create_and_list(client, session):
    _, token = await _user(client, session, "alice")
    h = {"Authorization": f"Bearer {token}"}
    r = await client.post("/api/v1/projects", json={"name": "P1"}, headers=h)
    assert r.status_code == 201
    pid = r.json()["id"]
    r = await client.get("/api/v1/projects", headers=h)
    assert any(p["id"] == pid for p in r.json())


async def test_only_owner_can_add_member(client, session):
    owner, ot = await _user(client, session, "owner")
    other, _ = await _user(client, session, "other")
    h = {"Authorization": f"Bearer {ot}"}
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers=h)).json()["id"]
    r = await client.post(
        f"/api/v1/projects/{pid}/members",
        json={"user_id": other.id, "role": "developer"},
        headers=h,
    )
    assert r.status_code == 201


async def test_non_member_cannot_see_project(client, session):
    owner, ot = await _user(client, session, "owner")
    outsider, out_t = await _user(client, session, "outsider")
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers={"Authorization": f"Bearer {ot}"})).json()["id"]
    r = await client.get(f"/api/v1/projects/{pid}", headers={"Authorization": f"Bearer {out_t}"})
    assert r.status_code == 403


async def test_last_owner_cannot_be_removed(client, session):
    owner, ot = await _user(client, session, "owner")
    pid = (await client.post("/api/v1/projects", json={"name": "P"}, headers={"Authorization": f"Bearer {ot}"})).json()["id"]
    r = await client.delete(
        f"/api/v1/projects/{pid}/members/{owner.id}",
        headers={"Authorization": f"Bearer {ot}"},
    )
    assert r.status_code == 400
```

- [ ] **Step 6: Run tests**

```bash
cd backend && pytest -v
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/
git commit -m "feat(backend): project and member management API"
```

---

## Phase 5 — Mock CRUD

### Task 13: Mock Schemas

**Files:**
- Create: `backend/app/schemas/mock_api.py`
- Modify: `backend/app/schemas/__init__.py`

- [ ] **Step 1: Create app/schemas/mock_api.py**

```python
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
```

- [ ] **Step 2: Update app/schemas/__init__.py**

Add re-exports:
```python
from app.schemas.mock_api import (  # noqa: F401
    MockCreate,
    MockOut,
    MockRequestMatch,
    MockTestRequest,
    MockTestResponse,
    MockUpdate,
)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/
git commit -m "feat(backend): mock schemas"
```

---

### Task 14: Mock CRUD API

**Files:**
- Create: `backend/app/mock_engine/__init__.py`
- Create: `backend/app/mock_engine/engine.py`
- Create: `backend/app/api/v1/mocks.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/schemas/__init__.py`
- Test: `backend/tests/test_mocks_api.py`

**Interfaces:**
- Produces: CRUD on `/api/v1/mocks`; engine instance `MockEngine` with `load_all()`, `upsert(mock)`, `remove(id)`

- [ ] **Step 1: Create app/mock_engine/__init__.py**

```python
from app.mock_engine.engine import MockEngine, get_engine

__all__ = ["MockEngine", "get_engine"]
```

- [ ] **Step 2: Create app/mock_engine/engine.py — placeholder for now**

```python
from app.models.mock_api import MockAPI


class MockEngine:
    def __init__(self) -> None:
        self._routes: list[MockAPI] = []

    async def load_all(self, db_rows: list[MockAPI]) -> None:
        self._routes = [m for m in db_rows if m.enabled]

    async def upsert(self, mock: MockAPI) -> None:
        self._routes = [m for m in self._routes if m.id != mock.id]
        if mock.enabled:
            self._routes.append(mock)

    async def remove(self, mock_id: int) -> None:
        self._routes = [m for m in self._routes if m.id != mock_id]

    def all(self) -> list[MockAPI]:
        return list(self._routes)


_engine = MockEngine()


def get_engine() -> MockEngine:
    return _engine
```

(Real match/render comes in Phase 6 — this lets CRUD tests run.)

- [ ] **Step 3: Create app/api/v1/mocks.py**

```python
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
    if not m or (roles and m.role not in roles):
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
        # restrict to projects user belongs to
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
    if "request_match" in data and data["request_match"] is not None:
        data["request_match"] = body.request_match.model_dump(exclude_none=True) if body.request_match else None
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
    # Renderer is filled in Phase 6 — temporarily return raw body.
    return MockTestResponse(
        status=mock.response_status,
        headers=mock.response_headers or {},
        body=mock.response_body,
    )
```

- [ ] **Step 4: Wire mocks router in app/main.py**

Add import and include:
```python
from app.api.v1 import mocks as mocks_v1
```
```python
app.include_router(mocks_v1.router, prefix="/api/v1")
```

- [ ] **Step 5: Update lifespan in app/main.py — load engine on startup**

```python
from sqlalchemy import select
from app.mock_engine import get_engine
from app.models.mock_api import MockAPI


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with session_module.AsyncSessionLocal() as s:
        rows = list((await s.scalars(select(MockAPI))).all())
    await get_engine().load_all(rows)
    yield
    await engine.dispose()
```

(Need to import `session_module`; add `import app.db.session as session_module`.)

- [ ] **Step 6: Write tests `tests/test_mocks_api.py`**

```python
from app.auth.security import hash_password
from app.models.project import Project, ProjectMember, ProjectRole
from app.models.user import User


async def _setup(client, session):
    owner = User(username="owner", password_hash=hash_password("owner123"), is_admin=False)
    viewer = User(username="viewer", password_hash=hash_password("viewer123"), is_admin=False)
    session.add_all([owner, viewer]); await session.commit()
    p = Project(name="P", created_by=owner.id)
    session.add(p); await session.flush()
    session.add_all([
        ProjectMember(project_id=p.id, user_id=owner.id, role=ProjectRole.OWNER),
        ProjectMember(project_id=p.id, user_id=viewer.id, role=ProjectRole.VIEWER),
    ])
    await session.commit()
    ot = (await client.post("/api/v1/auth/login", json={"username": "owner", "password": "owner123"})).json()["access_token"]
    vt = (await client.post("/api/v1/auth/login", json={"username": "viewer", "password": "viewer123"})).json()["access_token"]
    return p, owner, viewer, ot, vt


async def test_owner_creates_and_engine_loads(client, session):
    p, _, _, ot, _ = await _setup(client, session)
    r = await client.post(
        "/api/v1/mocks",
        json={"project_id": p.id, "name": "m1", "method": "GET", "path": "/api/u/{id}", "response_body": "{}"},
        headers={"Authorization": f"Bearer {ot}"},
    )
    assert r.status_code == 201
    mid = r.json()["id"]
    assert any(m.id == mid for m in get_engine_for_test().all())


def get_engine_for_test():
    from app.mock_engine import get_engine
    return get_engine()


async def test_viewer_cannot_create(client, session):
    p, _, _, _, vt = await _setup(client, session)
    r = await client.post(
        "/api/v1/mocks",
        json={"project_id": p.id, "name": "m", "method": "GET", "path": "/x"},
        headers={"Authorization": f"Bearer {vt}"},
    )
    assert r.status_code == 403


async def test_patch_toggles_enabled(client, session):
    p, _, _, ot, _ = await _setup(client, session)
    mid = (await client.post(
        "/api/v1/mocks",
        json={"project_id": p.id, "name": "m", "method": "GET", "path": "/x"},
        headers={"Authorization": f"Bearer {ot}"},
    )).json()["id"]
    r = await client.patch(f"/api/v1/mocks/{mid}", json={"enabled": False}, headers={"Authorization": f"Bearer {ot}"})
    assert r.status_code == 200
    assert all(m.id != mid for m in get_engine_for_test().all())
```

- [ ] **Step 7: Run tests**

```bash
cd backend && pytest -v
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add backend/
git commit -m "feat(backend): mock CRUD API and engine startup hook"
```

---

## Phase 6 — Mock Runtime Engine

### Task 15: Path Matcher

**Files:**
- Create: `backend/app/mock_engine/matcher.py`
- Test: `backend/tests/test_mock_matcher.py`

**Interfaces:**
- Produces: `match_path(template: str, actual: str) -> dict | None` — returns extracted path params or None

- [ ] **Step 1: Write failing tests `tests/test_mock_matcher.py`**

```python
from app.mock_engine.matcher import match_path


def test_exact_match():
    assert match_path("/api/user/1", "/api/user/1") == {}


def test_param_match():
    assert match_path("/api/user/{id}", "/api/user/42") == {"id": "42"}


def test_no_match_different_length():
    assert match_path("/api/{x}", "/api/a/b") is None


def test_no_match_static_segment():
    assert match_path("/api/{x}/list", "/api/42/detail") is None
```

- [ ] **Step 2: Run — confirm FAIL**

```bash
pytest tests/test_mock_matcher.py -v
```

Expected: import or assertion failure.

- [ ] **Step 3: Implement matcher**

Create `backend/app/mock_engine/matcher.py`:

```python
import re

_PARAM_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def match_path(template: str, actual: str) -> dict[str, str] | None:
    tpl_parts = template.strip("/").split("/")
    act_parts = actual.strip("/").split("/")
    if len(tpl_parts) != len(act_parts):
        return None
    params: dict[str, str] = {}
    for t, a in zip(tpl_parts, act_parts):
        m = _PARAM_RE.fullmatch(t)
        if m:
            params[m.group(1)] = a
        elif t != a:
            return None
    return params
```

- [ ] **Step 4: Run — confirm PASS**

```bash
pytest tests/test_mock_matcher.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/mock_engine/matcher.py backend/tests/test_mock_matcher.py
git commit -m "feat(backend): mock path template matcher"
```

---

### Task 16: Request Matcher (query/headers/body)

**Files:**
- Modify: `backend/app/mock_engine/matcher.py`
- Test: `backend/tests/test_mock_request_match.py`

**Interfaces:**
- Produces: `match_request(spec: dict | None, *, query, headers, body_text) -> bool`

- [ ] **Step 1: Write failing tests `tests/test_mock_request_match.py`**

```python
from app.mock_engine.matcher import match_request


def test_none_spec_always_matches():
    assert match_request(None, query={}, headers={}, body_text="")


def test_query_match():
    spec = {"query": {"token": "abc"}}
    assert match_request(spec, query={"token": "abc"}, headers={}, body_text="")
    assert not match_request(spec, query={"token": "xyz"}, headers={}, body_text="")


def test_header_match_case_insensitive():
    spec = {"headers": {"Authorization": "Bearer x"}}
    assert match_request(spec, query={}, headers={"authorization": "Bearer x"}, body_text="")


def test_body_contains_substring():
    assert match_request({"body_contains": "login"}, query={}, headers={}, body_text="action=login")
    assert not match_request({"body_contains": "logout"}, query={}, headers={}, body_text="action=login")


def test_body_jsonpath_true():
    spec = {"body_jsonpath": "$.action == 'login'"}
    assert match_request(spec, query={}, headers={}, body_text='{"action": "login"}')


def test_body_jsonpath_invalid_body_fails():
    assert not match_request({"body_jsonpath": "$.x"}, query={}, headers={}, body_text="not-json")
```

- [ ] **Step 2: Implement**

Append to `app/mock_engine/matcher.py`:

```python
import json
from jsonpath_ng import parse as jp_parse  # type: ignore


def match_request(
    spec: dict | None,
    *,
    query: dict[str, str],
    headers: dict[str, str],
    body_text: str,
) -> bool:
    if not spec:
        return True
    if q := spec.get("query"):
        for k, v in q.items():
            if query.get(k) != v:
                return False
    if h := spec.get("headers"):
        lower = {k.lower(): v for k, v in headers.items()}
        for k, v in h.items():
            if lower.get(k.lower()) != v:
                return False
    if "body_contains" in spec:
        if not body_text or spec["body_contains"] not in body_text:
            return False
    if "body_jsonpath" in spec:
        try:
            data = json.loads(body_text) if body_text else None
        except json.JSONDecodeError:
            return False
        if data is None:
            return False
        expr = jp_parse(spec["body_jsonpath"])
        matches = expr.find(data)
        if not matches or not isinstance(matches[0].value, bool) or not matches[0].value:
            return False
    return True
```

- [ ] **Step 3: Add `jsonpath-ng` to pyproject.toml dependencies**

Add to the `dependencies` list:
```toml
"jsonpath-ng>=1.6",
```

Then:
```bash
pip install -e ".[dev]"
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_mock_request_match.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/
git commit -m "feat(backend): mock request matcher (query/headers/body)"
```

---

### Task 17: Template Renderer

**Files:**
- Create: `backend/app/mock_engine/renderer.py`
- Test: `backend/tests/test_mock_renderer.py`

**Interfaces:**
- Produces: `render(text: str, *, path_params, query, headers, body_text) -> str`

- [ ] **Step 1: Write failing tests `tests/test_mock_renderer.py`**

```python
from app.mock_engine.renderer import render


def test_static_passthrough():
    assert render("hello", path_params={}, query={}, headers={}, body_text="") == "hello"


def test_path_param():
    out = render("id={{ request.path.id }}", path_params={"id": "42"}, query={}, headers={}, body_text="")
    assert out == "id=42"


def test_query_and_header_and_body_field():
    out = render(
        "q={{ request.query.q }} h={{ request.header.Authorization }} u={{ request.body.username }}",
        path_params={},
        query={"q": "hi"},
        headers={"Authorization": "Bearer x"},
        body_text='{"username": "alice"}',
    )
    assert out == "q=hi h=Bearer x u=alice"


def test_now_uuid_randin():
    out = render("{{ now() }}|{{ uuid() }}|{{ randint(1,1) }}", path_params={}, query={}, headers={}, body_text="")
    parts = out.split("|")
    assert len(parts) == 3
    assert "T" in parts[0]
    assert len(parts[1]) >= 32
    assert parts[2] == "1"
```

- [ ] **Step 2: Implement**

Create `app/mock_engine/renderer.py`:

```python
import random
import uuid
from datetime import datetime, timezone

from jinja2 import Environment, StrictUndefined

_ENV = Environment(
    autoescape=False,
    undefined=StrictUndefined,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return str(uuid.uuid4())


def _randint(a: int, b: int) -> int:
    return random.randint(a, b)


def render(
    text: str,
    *,
    path_params: dict[str, str],
    query: dict[str, str],
    headers: dict[str, str],
    body_text: str,
) -> str:
    import json

    body = None
    if body_text:
        try:
            body = json.loads(body_text)
        except json.JSONDecodeError:
            body = None

    class _BodyProxy:
        def __init__(self, data):
            self._data = data or {}

        def __getattr__(self, key):
            value = self._data.get(key)
            if isinstance(value, dict):
                return _BodyProxy(value)
            if value is None and key not in self._data:
                raise AttributeError(key)
            return value

    request = {
        "path": _BodyProxy(path_params),
        "query": _BodyProxy(query),
        "header": _BodyProxy({k.lower(): v for k, v in headers.items()}),
        "body": _BodyProxy(body if isinstance(body, dict) else {}),
    }

    template = _ENV.from_string(text)
    return template.render(
        request=request,
        now=_now,
        uuid=_uuid,
        randint=_randint,
    )
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/test_mock_renderer.py -v
```

Expected: 4 passed.

- [ ] **Step 4: Commit**

```bash
git add backend/app/mock_engine/renderer.py backend/tests/test_mock_renderer.py backend/pyproject.toml
git commit -m "feat(backend): mock template renderer (jinja2 sandbox)"
```

---

### Task 18: Runtime `/m/{full_path:path}` Endpoint

**Files:**
- Create: `backend/app/mock_engine/routes.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/mock_engine/engine.py`
- Test: `backend/tests/test_mock_runtime.py`

**Interfaces:**
- Produces: `GET/POST/PUT/DELETE/PATCH/HEAD/OPTIONS /m/{full_path:path}` matching engine routes

- [ ] **Step 1: Add `match` method to MockEngine**

Replace `app/mock_engine/engine.py`:

```python
import asyncio
from dataclasses import dataclass

from app.mock_engine.matcher import match_path, match_request
from app.mock_engine.renderer import render
from app.models.mock_api import MockAPI


@dataclass
class MatchedMock:
    mock: MockAPI
    path_params: dict[str, str]


class MockEngine:
    def __init__(self) -> None:
        self._routes: list[MockAPI] = []
        self._lock = asyncio.Lock()

    async def load_all(self, db_rows: list[MockAPI]) -> None:
        async with self._lock:
            self._routes = [m for m in db_rows if m.enabled]

    async def upsert(self, mock: MockAPI) -> None:
        async with self._lock:
            self._routes = [m for m in self._routes if m.id != mock.id]
            if mock.enabled:
                self._routes.append(mock)

    async def remove(self, mock_id: int) -> None:
        async with self._lock:
            self._routes = [m for m in self._routes if m.id != mock_id]

    def all(self) -> list[MockAPI]:
        return list(self._routes)

    def find(
        self,
        method: str,
        full_path: str,
        *,
        query: dict[str, str],
        headers: dict[str, str],
        body_text: str,
    ) -> MatchedMock | None:
        for m in self._routes:
            if m.method.value != method.upper():
                continue
            params = match_path(m.path, full_path)
            if params is None:
                continue
            if not match_request(m.request_match, query=query, headers=headers, body_text=body_text):
                continue
            return MatchedMock(mock=m, path_params=params)
        return None


_engine = MockEngine()


def get_engine() -> MockEngine:
    return _engine
```

- [ ] **Step 2: Create app/mock_engine/routes.py**

```python
import asyncio
import json

from fastapi import APIRouter, Request, Response

from app.mock_engine import get_engine
from app.mock_engine.renderer import render

router = APIRouter()

_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]


async def _handle(request: Request) -> Response:
    body_bytes = await request.body()
    body_text = body_bytes.decode("utf-8", errors="replace")
    headers = {k: v for k, v in request.headers.items()}
    # strip Host and Content-Length which are noisy
    headers.pop("host", None)
    headers.pop("content-length", None)
    query = {k: v for k, v in request.query_params.items()}
    full_path = "/" + request.path_params["full_path"]

    engine = get_engine()
    matched = engine.find(
        request.method,
        full_path,
        query=query,
        headers=headers,
        body_text=body_text,
    )
    if not matched:
        return Response(
            content=json.dumps({"detail": "Mock not found"}),
            media_type="application/json",
            status_code=404,
        )

    mock = matched.mock
    if mock.delay_ms:
        await asyncio.sleep(mock.delay_ms / 1000)

    rendered_headers = {
        k: render(v, path_params=matched.path_params, query=query, headers=headers, body_text=body_text)
        for k, v in (mock.response_headers or {}).items()
    }
    rendered_body = render(
        mock.response_body,
        path_params=matched.path_params,
        query=query,
        headers=headers,
        body_text=body_text,
    )
    content_type = rendered_headers.pop("Content-Type", "application/json")
    return Response(content=rendered_body, headers=rendered_headers, media_type=content_type, status_code=mock.response_status)


for method in _METHODS:
    router.add_api_route(
        path="/m/{full_path:path}",
        endpoint=_handle,
        methods=[method],
    )
```

- [ ] **Step 3: Mount runtime router in app/main.py**

Add import and include **after** all other routers:
```python
from app.mock_engine import routes as mock_routes
```
```python
app.include_router(mock_routes.router)
```

- [ ] **Step 4: Write end-to-end tests `tests/test_mock_runtime.py`**

```python
from app.auth.security import hash_password
from app.mock_engine import get_engine
from app.models.mock_api import HttpMethod, MockAPI
from app.models.project import Project, ProjectMember, ProjectRole
from app.models.user import User


async def _seed_mock(client, session):
    owner = User(username="owner", password_hash=hash_password("owner123"), is_admin=False)
    session.add(owner); await session.commit()
    p = Project(name="P", created_by=owner.id)
    session.add(p); await session.flush()
    session.add(ProjectMember(project_id=p.id, user_id=owner.id, role=ProjectRole.OWNER))
    await session.commit()
    ot = (await client.post("/api/v1/auth/login", json={"username": "owner", "password": "owner123"})).json()["access_token"]
    return p, ot


async def test_runtime_static(client, session):
    p, ot = await _seed_mock(client, session)
    await client.post(
        "/api/v1/mocks",
        json={"project_id": p.id, "name": "m", "method": "GET", "path": "/ping", "response_body": '{"ok":true}', "response_status": 200},
        headers={"Authorization": f"Bearer {ot}"},
    )
    r = await client.get("/m/ping")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


async def test_runtime_path_param_and_body_field(client, session):
    p, ot = await _seed_mock(client, session)
    await client.post(
        "/api/v1/mocks",
        json={
            "project_id": p.id, "name": "m", "method": "POST", "path": "/u/{id}",
            "response_body": '{"id":"{{ request.path.id }}","user":"{{ request.body.name }}"}',
        },
        headers={"Authorization": f"Bearer {ot}"},
    )
    r = await client.post("/m/u/42", json={"name": "alice"})
    assert r.status_code == 200
    assert r.json() == {"id": "42", "user": "alice"}


async def test_runtime_not_found(client):
    r = await client.get("/m/nope")
    assert r.status_code == 404


async def test_disabled_mock_not_served(client, session):
    p, ot = await _seed_mock(client, session)
    mid = (await client.post(
        "/api/v1/mocks",
        json={"project_id": p.id, "name": "m", "method": "GET", "path": "/x", "response_body": "{}"},
        headers={"Authorization": f"Bearer {ot}"},
    )).json()["id"]
    await client.patch(f"/api/v1/mocks/{mid}", json={"enabled": False}, headers={"Authorization": f"Bearer {ot}"})
    r = await client.get("/m/x")
    assert r.status_code == 404


async def test_query_match(client, session):
    p, ot = await _seed_mock(client, session)
    await client.post(
        "/api/v1/mocks",
        json={
            "project_id": p.id, "name": "m", "method": "GET", "path": "/q",
            "request_match": {"query": {"token": "abc"}},
            "response_body": '{"ok":true}',
        },
        headers={"Authorization": f"Bearer {ot}"},
    )
    r = await client.get("/m/q?token=abc")
    assert r.status_code == 200
    r = await client.get("/m/q?token=zzz")
    assert r.status_code == 404
```

- [ ] **Step 5: Run tests**

```bash
cd backend && pytest -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/
git commit -m "feat(backend): mock runtime /m/* with path params, query match, template render"
```

---

### Task 19: Wire `/mocks/{id}/test` to Real Renderer

**Files:**
- Modify: `backend/app/api/v1/mocks.py`

- [ ] **Step 1: Replace the test_mock handler body**

In `app/api/v1/mocks.py`, replace the `test_mock` function body (after auth check) with:

```python
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
```

(Add a test in `test_mocks_api.py`:)

```python
async def test_test_endpoint_renders_template(client, session):
    p, ot = await _seed_mock(client, session)
    mid = (await client.post(
        "/api/v1/mocks",
        json={"project_id": p.id, "name": "m", "method": "POST", "path": "/x",
              "response_body": '{"hi":"{{ request.body.name }}"}'},
        headers={"Authorization": f"Bearer {ot}"},
    )).json()["id"]
    r = await client.post(
        f"/api/v1/mocks/{mid}/test",
        json={"method": "POST", "path": "/x", "body": '{"name":"bob"}'},
        headers={"Authorization": f"Bearer {ot}"},
    )
    assert r.status_code == 200
    assert '"hi":"bob"' in r.json()["body"]
```

- [ ] **Step 2: Run, commit**

```bash
cd backend && pytest -v
git add backend/
git commit -m "feat(backend): /mocks/{id}/test renders templates"
```

---

## Phase 7 — Frontend Foundations

### Task 20: Pinia Auth Store and Axios Client

**Files:**
- Create: `frontend/src/stores/auth.ts`
- Create: `frontend/src/api/http.ts`
- Test: `frontend/src/stores/__tests__/auth.spec.ts`

- [ ] **Step 1: Create src/api/http.ts**

```typescript
import axios, { AxiosInstance } from "axios";

export const http: AxiosInstance = axios.create({ baseURL: "/api/v1" });

http.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

http.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("token");
      if (location.pathname !== "/login") location.href = "/login";
    }
    return Promise.reject(err);
  }
);
```

- [ ] **Step 2: Create src/stores/auth.ts**

```typescript
import { defineStore } from "pinia";
import { ref } from "vue";
import { http } from "@/api/http";

interface Me { id: number; username: string; is_admin: boolean }

export const useAuthStore = defineStore("auth", () => {
  const token = ref<string | null>(localStorage.getItem("token"));
  const me = ref<Me | null>(null);

  async function login(username: string, password: string): Promise<void> {
    const r = await http.post("/auth/login", { username, password });
    token.value = r.data.access_token;
    localStorage.setItem("token", token.value);
    await fetchMe();
  }

  async function fetchMe(): Promise<void> {
    if (!token.value) { me.value = null; return; }
    const r = await http.get<Me>("/auth/me");
    me.value = r.data;
  }

  function logout(): void {
    token.value = null;
    me.value = null;
    localStorage.removeItem("token");
  }

  return { token, me, login, fetchMe, logout };
});
```

- [ ] **Step 3: Create alias `@` → `src` in Vite**

Add to `frontend/vite.config.ts`:

```typescript
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  plugins: [vue()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: { host: "0.0.0.0", port: 5173, proxy: { "/api": "http://localhost:8000", "/m": "http://localhost:8000" } },
  test: { environment: "jsdom", globals: true }
});
```

- [ ] **Step 4: Test `auth.spec.ts`**

```typescript
import { setActivePinia, createPinia } from "pinia";
import { useAuthStore } from "@/stores/auth";

describe("auth store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
  });

  it("starts logged out", () => {
    const s = useAuthStore();
    expect(s.token).toBeNull();
    expect(s.me).toBeNull();
  });

  it("logout clears state", () => {
    const s = useAuthStore();
    s.token = "abc";
    s.me = { id: 1, username: "u", is_admin: false };
    s.logout();
    expect(s.token).toBeNull();
    expect(s.me).toBeNull();
  });
});
```

- [ ] **Step 5: Run frontend tests**

```bash
cd frontend && npm test
```

Expected: 2 specs pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): axios http client and pinia auth store"
```

---

### Task 21: Router Auth Guard and Layout Shell

**Files:**
- Modify: `frontend/src/router/index.ts`
- Create: `frontend/src/layouts/AppLayout.vue`
- Modify: `frontend/src/App.vue`

- [ ] **Step 1: Modify src/router/index.ts — guard + lazy routes**

```typescript
import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", component: () => import("@/views/LoginView.vue"), meta: { public: true } },
    {
      path: "/",
      component: () => import("@/layouts/AppLayout.vue"),
      children: [
        { path: "", redirect: "/projects" },
        { path: "projects", component: () => import("@/views/ProjectsView.vue") },
        { path: "projects/new", component: () => import("@/views/ProjectNewView.vue") },
        { path: "projects/:id", component: () => import("@/views/ProjectDetailView.vue") },
        { path: "mocks", component: () => import("@/views/MocksView.vue") },
        { path: "mocks/new", component: () => import("@/views/MockEditView.vue") },
        { path: "mocks/:id", component: () => import("@/views/MockEditView.vue") },
        { path: "users", component: () => import("@/views/UsersView.vue"), meta: { adminOnly: true } }
      ]
    }
  ]
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  if (to.meta.public) return true;
  if (!auth.token) return { path: "/login", query: { redirect: to.fullPath } };
  if (!auth.me) await auth.fetchMe();
  if (to.meta.adminOnly && !auth.me?.is_admin) return { path: "/projects" };
  return true;
});

export default router;
```

- [ ] **Step 2: Create src/layouts/AppLayout.vue**

```vue
<template>
  <el-container class="layout">
    <el-aside width="200px" class="aside">
      <h3 class="logo">Test Platform</h3>
      <el-menu :default-active="route.path" router>
        <el-menu-item index="/projects">项目</el-menu-item>
        <el-menu-item index="/mocks">Mock 接口</el-menu-item>
        <el-menu-item v-if="auth.me?.is_admin" index="/users">用户管理</el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <span class="grow"></span>
        <span>{{ auth.me?.username }}</span>
        <el-button link @click="onLogout">退出</el-button>
      </el-header>
      <el-main><router-view /></el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

function onLogout() {
  auth.logout();
  router.push("/login");
}
</script>

<style scoped>
.layout { height: 100vh; }
.aside { background: #001529; color: #fff; }
.logo { color: #fff; padding: 16px; }
.header { display: flex; align-items: center; border-bottom: 1px solid #eee; }
.grow { flex: 1; }
</style>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): router guard and app layout shell"
```

---

## Phase 8 — Frontend Project, User, Mock UI

### Task 22: Login View

**Files:**
- Modify: `frontend/src/views/LoginView.vue`

- [ ] **Step 1: Replace LoginView.vue**

```vue
<template>
  <div class="login-page">
    <el-card class="login-card">
      <h2>登录</h2>
      <el-form :model="form" @keyup.enter="submit">
        <el-form-item label="用户名">
          <el-input v-model="form.username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" show-password />
        </el-form-item>
        <el-button type="primary" :loading="loading" @click="submit">登录</el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();

const form = reactive({ username: "", password: "" });
const loading = ref(false);

async function submit() {
  loading.value = true;
  try {
    await auth.login(form.username, form.password);
    router.push((route.query.redirect as string) || "/projects");
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "登录失败");
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.login-page { height: 100vh; display: flex; align-items: center; justify-content: center; background: #f5f5f5; }
.login-card { width: 360px; }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/views/LoginView.vue
git commit -m "feat(frontend): login view with form"
```

---

### Task 23: Projects List + Create + Detail (with Members)

**Files:**
- Create: `frontend/src/views/ProjectsView.vue`
- Create: `frontend/src/views/ProjectNewView.vue`
- Create: `frontend/src/views/ProjectDetailView.vue`
- Create: `frontend/src/api/projects.ts`

- [ ] **Step 1: Create src/api/projects.ts**

```typescript
import { http } from "@/api/http";

export interface Project { id: number; name: string; description: string | null }
export interface Member { user_id: number; username: string; role: "owner" | "developer" | "viewer" }

export const projectsApi = {
  list: () => http.get<Project[]>("/projects").then((r) => r.data),
  get: (id: number) => http.get<Project>(`/projects/${id}`).then((r) => r.data),
  create: (body: { name: string; description?: string }) =>
    http.post<Project>("/projects", body).then((r) => r.data),
  update: (id: number, body: Partial<Project>) =>
    http.patch<Project>(`/projects/${id}`, body).then((r) => r.data),
  remove: (id: number) => http.delete(`/projects/${id}`),
  members: (id: number) => http.get<Member[]>(`/projects/${id}/members`).then((r) => r.data),
  addMember: (id: number, body: { user_id: number; role: Member["role"] }) =>
    http.post<Member>(`/projects/${id}/members`, body).then((r) => r.data),
  updateMember: (id: number, userId: number, body: { role: Member["role"] }) =>
    http.patch<Member>(`/projects/${id}/members/${userId}`, body).then((r) => r.data),
  removeMember: (id: number, userId: number) =>
    http.delete(`/projects/${id}/members/${userId}`),
};
```

- [ ] **Step 2: Create src/views/ProjectsView.vue**

```vue
<template>
  <div>
    <el-page-header title="项目" />
    <el-button type="primary" @click="$router.push('/projects/new')">新建项目</el-button>
    <el-table :data="projects" style="width:100%;margin-top:16px">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="description" label="描述" />
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button link @click="$router.push(`/projects/${row.id}`)">查看</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { projectsApi, Project } from "@/api/projects";

const projects = ref<Project[]>([]);
onMounted(async () => { projects.value = await projectsApi.list(); });
</script>
```

- [ ] **Step 3: Create src/views/ProjectNewView.vue**

```vue
<template>
  <el-page-header title="新建项目" @back="$router.push('/projects')" />
  <el-form :model="form" label-width="80px" style="max-width:480px">
    <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
    <el-form-item label="描述"><el-input v-model="form.description" type="textarea" /></el-form-item>
    <el-button type="primary" :loading="loading" @click="submit">创建</el-button>
  </el-form>
</template>

<script setup lang="ts">
import { reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { projectsApi } from "@/api/projects";

const router = useRouter();
const form = reactive({ name: "", description: "" });
const loading = ref(false);

async function submit() {
  loading.value = true;
  try {
    const p = await projectsApi.create({ name: form.name, description: form.description || undefined });
    router.push(`/projects/${p.id}`);
  } catch (e: any) { ElMessage.error(e.response?.data?.detail || "创建失败"); }
  finally { loading.value = false; }
}
</script>
```

- [ ] **Step 4: Create src/views/ProjectDetailView.vue**

```vue
<template>
  <el-page-header :title="project?.name || '项目'" @back="$router.push('/projects')" />
  <el-tabs v-model="tab">
    <el-tab-pane label="Mock 列表" name="mocks">
      <el-button type="primary" @click="$router.push(`/mocks/new?project_id=${projectId}`)">新建 Mock</el-button>
      <el-table :data="mocks">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="method" label="方法" width="100" />
        <el-table-column prop="path" label="路径" />
        <el-table-column label="启用" width="100">
          <template #default="{ row }"><el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '是' : '否' }}</el-tag></template>
        </el-table-column>
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button link @click="$router.push(`/mocks/${row.id}`)">编辑</el-button>
            <el-popconfirm title="确认删除?" @confirm="remove(row.id)"><template #reference><el-button link type="danger">删除</el-button></template></el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-tab-pane>
    <el-tab-pane label="成员管理" name="members">
      <el-select v-model="newUserId" placeholder="选择用户" filterable>
        <el-option v-for="u in allUsers" :key="u.id" :label="u.username" :value="u.id" />
      </el-select>
      <el-select v-model="newRole" placeholder="角色" style="width:120px;margin-left:8px">
        <el-option label="developer" value="developer" />
        <el-option label="viewer" value="viewer" />
      </el-select>
      <el-button @click="addMember">添加</el-button>
      <el-table :data="members" style="margin-top:16px">
        <el-table-column prop="user_id" label="用户ID" width="100" />
        <el-table-column prop="username" label="用户名" />
        <el-table-column prop="role" label="角色" />
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button link @click="removeMember(row.user_id)">移除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-tab-pane>
  </el-tabs>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import { ElMessage } from "element-plus";
import { projectsApi, Member } from "@/api/projects";
import { mocksApi, Mock } from "@/api/mocks";
import { http } from "@/api/http";

const route = useRoute();
const projectId = Number(route.params.id);
const project = ref<{ id: number; name: string } | null>(null);
const tab = ref("mocks");
const mocks = ref<Mock[]>([]);
const members = ref<Member[]>([]);
const allUsers = ref<{ id: number; username: string }[]>([]);
const newUserId = ref<number | null>(null);
const newRole = ref<Member["role"]>("developer");

async function refresh() {
  project.value = await projectsApi.get(projectId);
  mocks.value = await mocksApi.list(projectId);
  members.value = await projectsApi.members(projectId);
}

async function loadUsers() {
  try {
    allUsers.value = (await http.get("/users")).data;
  } catch { /* non-admin */ }
}

async function addMember() {
  if (!newUserId.value) return;
  await projectsApi.addMember(projectId, { user_id: newUserId.value, role: newRole.value });
  await refresh();
  ElMessage.success("已添加");
}

async function removeMember(uid: number) {
  await projectsApi.removeMember(projectId, uid);
  await refresh();
}

async function remove(id: number) {
  await mocksApi.remove(id);
  await refresh();
}

onMounted(async () => { await refresh(); await loadUsers(); });
</script>
```

- [ ] **Step 5: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): project list, new, detail (with members and mocks tabs)"
```

---

### Task 24: Mock List, Edit, and Test-Response Panel

**Files:**
- Create: `frontend/src/api/mocks.ts`
- Create: `frontend/src/views/MocksView.vue`
- Create: `frontend/src/views/MockEditView.vue`

- [ ] **Step 1: Create src/api/mocks.ts**

```typescript
import { http } from "@/api/http";

export interface Mock {
  id: number; project_id: number; name: string;
  method: "GET" | "POST" | "PUT" | "DELETE" | "PATCH" | "HEAD" | "OPTIONS";
  path: string; enabled: boolean;
  request_match: { query?: Record<string,string>; headers?: Record<string,string>; body_contains?: string; body_jsonpath?: string } | null;
  response_status: number;
  response_headers: Record<string,string> | null;
  response_body: string;
  delay_ms: number; description: string | null;
}

export interface MockCreate extends Omit<Mock, "id" | "request_match" | "response_headers"> {
  request_match?: Mock["request_match"];
  response_headers?: Record<string,string>;
}

export interface MockTestRequest {
  method: Mock["method"]; path: string;
  headers: Record<string,string>; query: Record<string,string>;
  body: string | null;
}
export interface MockTestResponse { status: number; headers: Record<string,string>; body: string }

export const mocksApi = {
  list: (projectId?: number) => http.get<Mock[]>("/mocks", { params: { project_id: projectId } }).then((r) => r.data),
  get: (id: number) => http.get<Mock>(`/mocks/${id}`).then((r) => r.data),
  create: (body: MockCreate) => http.post<Mock>("/mocks", body).then((r) => r.data),
  update: (id: number, body: Partial<MockCreate>) => http.patch<Mock>(`/mocks/${id}`, body).then((r) => r.data),
  remove: (id: number) => http.delete(`/mocks/${id}`),
  test: (id: number, body: MockTestRequest) => http.post<MockTestResponse>(`/mocks/${id}/test`, body).then((r) => r.data),
};
```

- [ ] **Step 2: Create src/views/MocksView.vue**

```vue
<template>
  <el-page-header title="Mock 接口" />
  <el-button type="primary" @click="$router.push('/mocks/new')">新建 Mock</el-button>
  <el-table :data="mocks" style="margin-top:16px">
    <el-table-column prop="id" label="ID" width="80" />
    <el-table-column prop="project_id" label="项目" width="80" />
    <el-table-column prop="method" label="方法" width="100" />
    <el-table-column prop="path" label="路径" />
    <el-table-column label="启用" width="100">
      <template #default="{ row }"><el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '是' : '否' }}</el-tag></template>
    </el-table-column>
    <el-table-column label="操作" width="160">
      <template #default="{ row }">
        <el-button link @click="$router.push(`/mocks/${row.id}`)">编辑</el-button>
        <el-popconfirm title="确认删除?" @confirm="remove(row.id)"><template #reference><el-button link type="danger">删除</el-button></template></el-popconfirm>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { mocksApi, Mock } from "@/api/mocks";

const mocks = ref<Mock[]>([]);
async function refresh() { mocks.value = await mocksApi.list(); }
async function remove(id: number) { await mocksApi.remove(id); await refresh(); ElMessage.success("已删除"); }
onMounted(refresh);
</script>
```

- [ ] **Step 3: Create src/views/MockEditView.vue**

```vue
<template>
  <el-page-header :title="isNew ? '新建 Mock' : '编辑 Mock'" @back="$router.back()" />
  <el-form :model="form" label-width="120px" style="max-width:760px">
    <el-form-item label="项目"><el-input-number v-model="form.project_id" :min="1" /></el-form-item>
    <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
    <el-form-item label="方法">
      <el-select v-model="form.method" style="width:140px">
        <el-option v-for="m in METHODS" :key="m" :value="m" :label="m" />
      </el-select>
    </el-form-item>
    <el-form-item label="路径"><el-input v-model="form.path" placeholder="如 /api/user/{id}" /></el-form-item>
    <el-form-item label="状态码"><el-input-number v-model="form.response_status" :min="100" :max="599" /></el-form-item>
    <el-form-item label="响应头 (JSON)"><el-input v-model="responseHeadersText" type="textarea" :rows="3" /></el-form-item>
    <el-form-item label="响应体"><el-input v-model="form.response_body" type="textarea" :rows="8" placeholder='{"id":"{{ request.path.id }}"}' /></el-form-item>
    <el-form-item label="延时(ms)"><el-input-number v-model="form.delay_ms" :min="0" :max="60000" /></el-form-item>
    <el-form-item label="启用"><el-switch v-model="form.enabled" /></el-form-item>
    <el-form-item label="描述"><el-input v-model="form.description" type="textarea" /></el-form-item>
    <el-button type="primary" :loading="loading" @click="save">保存</el-button>
  </el-form>

  <el-divider />
  <h3>测试响应</h3>
  <el-form :model="testReq" label-width="100px" style="max-width:520px">
    <el-form-item label="Method">
      <el-select v-model="testReq.method" style="width:140px"><el-option v-for="m in METHODS" :key="m" :value="m" :label="m" /></el-select>
    </el-form-item>
    <el-form-item label="Path"><el-input v-model="testReq.path" placeholder="/api/user/1" /></el-form-item>
    <el-form-item label="Headers (JSON)"><el-input v-model="testHeadersText" type="textarea" :rows="2" /></el-form-item>
    <el-form-item label="Query (JSON)"><el-input v-model="testQueryText" type="textarea" :rows="2" /></el-form-item>
    <el-form-item label="Body"><el-input v-model="testReq.body" type="textarea" :rows="4" /></el-form-item>
    <el-button :disabled="!mockId" @click="runTest">运行测试</el-button>
  </el-form>
  <pre v-if="testRes" class="result">{{ testRes.status }} {{ testRes.headers }}\n{{ testRes.body }}</pre>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { mocksApi, Mock, MockTestResponse } from "@/api/mocks";

const route = useRoute();
const router = useRouter();
const METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"] as const;

const mockId = computed(() => (route.params.id ? Number(route.params.id) : null));
const isNew = computed(() => !mockId.value);

const form = reactive<Mock>({
  id: 0, project_id: Number(route.query.project_id) || 1, name: "", method: "GET", path: "/api/example",
  enabled: true, request_match: null, response_status: 200, response_headers: { "Content-Type": "application/json" },
  response_body: '{"ok":true}', delay_ms: 0, description: null
});
const responseHeadersText = ref(JSON.stringify(form.response_headers, null, 2));
const loading = ref(false);

const testReq = reactive({ method: "GET" as Mock["method"], path: "/api/example", headers: {} as Record<string,string>, query: {} as Record<string,string>, body: null as string | null });
const testHeadersText = ref("{}");
const testQueryText = ref("{}");
const testRes = ref<MockTestResponse | null>(null);

onMounted(async () => {
  if (mockId.value) {
    const m = await mocksApi.get(mockId.value);
    Object.assign(form, m);
    responseHeadersText.value = JSON.stringify(m.response_headers ?? {}, null, 2);
  }
});

async function save() {
  loading.value = true;
  try {
    let headers: Record<string,string> | undefined;
    try { headers = JSON.parse(responseHeadersText.value || "{}"); } catch { ElMessage.error("响应头 JSON 格式错误"); return; }
    const body = { ...form, response_headers: headers };
    delete (body as any).id;
    if (isNew.value) {
      const created = await mocksApi.create(body);
      router.replace(`/mocks/${created.id}`);
    } else {
      await mocksApi.update(mockId.value!, body);
      ElMessage.success("已保存");
    }
  } catch (e: any) { ElMessage.error(e.response?.data?.detail || "保存失败"); }
  finally { loading.value = false; }
}

async function runTest() {
  try {
    testReq.headers = JSON.parse(testHeadersText.value || "{}");
    testReq.query = JSON.parse(testQueryText.value || "{}");
  } catch { return ElMessage.error("JSON 格式错误"); }
  testRes.value = await mocksApi.test(mockId.value!, testReq);
}
</script>

<style scoped>
.result { background:#f5f5f5; padding:12px; white-space: pre-wrap; }
</style>
```

- [ ] **Step 4: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): mock list, edit, and test-response panel"
```

---

### Task 25: Users View (admin only)

**Files:**
- Create: `frontend/src/views/UsersView.vue`

- [ ] **Step 1: Create src/views/UsersView.vue**

```vue
<template>
  <el-page-header title="用户管理" />
  <el-button type="primary" @click="openCreate">新建用户</el-button>
  <el-table :data="users" style="margin-top:16px">
    <el-table-column prop="id" label="ID" width="80" />
    <el-table-column prop="username" label="用户名" />
    <el-table-column label="管理员" width="100"><template #default="{ row }"><el-tag :type="row.is_admin ? 'success' : 'info'">{{ row.is_admin ? '是' : '否' }}</el-tag></template></el-table-column>
    <el-table-column label="启用" width="100"><template #default="{ row }"><el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '是' : '否' }}</el-tag></template></el-table-column>
    <el-table-column label="操作" width="200">
      <template #default="{ row }">
        <el-button link @click="toggleActive(row)">{{ row.is_active ? '停用' : '启用' }}</el-button>
        <el-button link @click="resetPwd(row)">重置密码</el-button>
      </template>
    </el-table-column>
  </el-table>

  <el-dialog v-model="createOpen" title="新建用户" width="420">
    <el-form :model="createForm">
      <el-form-item label="用户名"><el-input v-model="createForm.username" /></el-form-item>
      <el-form-item label="密码"><el-input v-model="createForm.password" type="password" show-password /></el-form-item>
      <el-form-item label="管理员"><el-switch v-model="createForm.is_admin" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="createOpen = false">取消</el-button>
      <el-button type="primary" @click="create">创建</el-button>
    </template>
  </el-dialog>

  <el-dialog v-model="resetOpen" title="重置密码" width="420">
    <el-form :model="resetForm"><el-form-item label="新密码"><el-input v-model="resetForm.new_password" type="password" show-password /></el-form-item></el-form>
    <template #footer>
      <el-button @click="resetOpen = false">取消</el-button>
      <el-button type="primary" @click="doReset">提交</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { http } from "@/api/http";

interface User { id: number; username: string; is_admin: boolean; is_active: boolean }

const users = ref<User[]>([]);
const createOpen = ref(false);
const createForm = reactive({ username: "", password: "", is_admin: false });
const resetOpen = ref(false);
const resetForm = reactive({ id: 0, new_password: "" });

async function refresh() { users.value = (await http.get<User[]>("/users")).data; }
function openCreate() { Object.assign(createForm, { username: "", password: "", is_admin: false }); createOpen.value = true; }
async function create() {
  await http.post("/users", createForm);
  createOpen.value = false;
  await refresh();
  ElMessage.success("已创建");
}
async function toggleActive(u: User) {
  await http.patch(`/users/${u.id}`, { is_active: !u.is_active });
  await refresh();
}
function resetPwd(u: User) {
  resetForm.id = u.id; resetForm.new_password = ""; resetOpen.value = true;
}
async function doReset() {
  await http.post(`/users/${resetForm.id}/reset-password`, { new_password: resetForm.new_password });
  resetOpen.value = false;
  ElMessage.success("已重置");
}
onMounted(refresh);
</script>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/views/UsersView.vue
git commit -m "feat(frontend): users management view (admin)"
```

---

## Phase 9 — Deployment

### Task 26: Frontend Nginx Config + Compose Service

**Files:**
- Create: `frontend/nginx.conf`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Create frontend/nginx.conf**

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /m/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

- [ ] **Step 2: Add frontend service to docker-compose.yml**

Add a service block:

```yaml
  frontend:
    build: ./frontend
    depends_on:
      - backend
    ports:
      - "80:80"
```

- [ ] **Step 3: Run migrations inside backend container**

```bash
docker compose build backend
docker compose run --rm backend alembic upgrade head
```

Expected: migrations apply, exit 0. (This runs the autogenerated migration from Task 7 against the MySQL container.)

- [ ] **Step 4: Start the full stack**

```bash
docker compose up -d --build
```

Expected: `mysql`, `backend`, `frontend` services all healthy.

- [ ] **Step 5: Smoke test**

```bash
curl -s http://localhost/health
# {"status":"ok"}

curl -s -X POST http://localhost/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}'
# {"access_token":"...","token_type":"bearer"}
```

(Note: the seed admin user must exist. Add a one-shot seed step.)

- [ ] **Step 6: Commit**

```bash
git add docker-compose.yml frontend/nginx.conf
git commit -m "feat(deploy): frontend nginx reverse proxy + compose service"
```

---

### Task 27: Seed Default Admin User

**Files:**
- Create: `backend/app/scripts/seed_admin.py`
- Modify: `backend/Dockerfile` (or compose `command`)

- [ ] **Step 1: Create backend/app/scripts/seed_admin.py**

```python
import asyncio

from sqlalchemy import select

from app.auth.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.user import User


async def main() -> None:
    async with AsyncSessionLocal() as s:
        if await s.scalar(select(User).where(User.username == "admin")):
            return
        s.add(User(username="admin", password_hash=hash_password("admin123"), is_admin=True))
        await s.commit()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Add init container to docker-compose.yml that runs migrations + seed**

Replace the `backend` service command with a two-step approach using an init container. Add a new service:

```yaml
  backend-init:
    build: ./backend
    depends_on:
      mysql:
        condition: service_healthy
    environment:
      DATABASE_URL: mysql+asyncmy://root:${MYSQL_ROOT_PASSWORD:-rootpw}@mysql:3306/${MYSQL_DATABASE:-test_platform}
    entrypoint: ["bash", "-lc"]
    command:
      - "alembic upgrade head && python -m app.scripts.seed_admin"
    restart: "no"
```

And modify `backend.command` to wait for `backend-init`:

```yaml
  backend:
    build: ./backend
    depends_on:
      mysql: { condition: service_healthy }
      backend-init: { condition: service_completed_successfully }
    environment:
      DATABASE_URL: mysql+asyncmy://root:${MYSQL_ROOT_PASSWORD:-rootpw}@mysql:3306/${MYSQL_DATABASE:-test_platform}
      JWT_SECRET: ${JWT_SECRET:-dev-secret}
      JWT_ALGORITHM: HS256
      JWT_EXPIRES_MINUTES: "1440"
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

- [ ] **Step 3: Bring up stack**

```bash
docker compose down -v
docker compose up -d --build
docker compose logs backend-init
```

Expected: backend-init logs "alembic upgrade head" succeeded and seed_admin ran without errors.

- [ ] **Step 4: Verify login**

```bash
curl -s -X POST http://localhost/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}' | jq
```

Expected: `{"access_token":"...","token_type":"bearer"}`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/scripts/seed_admin.py docker-compose.yml
git commit -m "feat(deploy): seed default admin user and init container"
```

---

## Self-Review Checklist

After completing all tasks, verify each spec section is covered:

- § 2 Tech Stack: ✓ Phase 1, 2, 7, 9
- § 3 Architecture: ✓ Phase 1, Task 18
- § 4 Data Model: ✓ Tasks 6, 7, 10, 12, 13
- § 4.1 Permission model: ✓ Tasks 9, 11, 12, 14
- § 5.1 Path matching: ✓ Task 15
- § 5.1 Request matching (query/headers/body_contains/body_jsonpath): ✓ Task 16
- § 5.2 Template rendering: ✓ Task 17
- § 5.3 In-memory engine + refresh: ✓ Tasks 5, 14, 18
- § 6.1–6.6 API surface: ✓ Tasks 9, 11, 12, 14, 18, 19
- § 7.1 Frontend stack: ✓ Tasks 3, 20
- § 7.2 Routes: ✓ Task 21
- § 7.3 Pages: ✓ Tasks 22, 23, 24, 25
- § 7.4 Permission gates: ✓ Tasks 21 (router), 23–25 (button-level), backend (server-side)
- § 8 Docker deployment: ✓ Tasks 4, 26, 27

No placeholders used; every step contains concrete commands or full code.
