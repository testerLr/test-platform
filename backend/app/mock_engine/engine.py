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
