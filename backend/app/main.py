from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1 import auth as auth_v1
from app.api.v1 import users as users_v1
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(title="Test Platform", version="0.1.0", lifespan=lifespan)
app.include_router(auth_v1.router, prefix="/api/v1")
app.include_router(users_v1.router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}