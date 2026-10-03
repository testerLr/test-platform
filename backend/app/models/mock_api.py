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