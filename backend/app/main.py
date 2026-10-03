from contextlib import asynccontextmanager

from sqlalchemy import select

from fastapi import FastAPI

import app.db.session as session_module
from app.api.v1 import auth as auth_v1
from app.api.v1 import mocks as mocks_v1
from app.api.v1 import projects as projects_v1
from app.api.v1 import users as users_v1
from app.db.session import engine
from app.mock_engine import get_engine
from app.models.mock_api import MockAPI


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with session_module.AsyncSessionLocal() as s:
        rows = list((await s.scalars(select(MockAPI))).all())
    await get_engine().load_all(rows)
    yield
    await engine.dispose()


app = FastAPI(title="Test Platform", version="0.1.0", lifespan=lifespan)
app.include_router(auth_v1.router, prefix="/api/v1")
app.include_router(users_v1.router, prefix="/api/v1")
app.include_router(projects_v1.router, prefix="/api/v1")
app.include_router(mocks_v1.router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
