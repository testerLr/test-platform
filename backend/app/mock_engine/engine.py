import asyncio

from app.models.mock_api import MockAPI


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


_engine = MockEngine()


def get_engine() -> MockEngine:
    return _engine
