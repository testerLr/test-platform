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
