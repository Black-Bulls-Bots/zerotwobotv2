# afk_sql.py
from datetime import datetime
import asyncio
from zerotwo.sql import Base, async_session, CustomLockManager
from sqlalchemy import Boolean, Column, UnicodeText, DateTime, BigInteger, select

INSERTION_LOCK = CustomLockManager()
AFK_USERS = {}  # cache: {user_id: {"reason": str, "time": datetime}}

class AFK(Base):
    __tablename__ = "afk_users"

    user_id = Column(BigInteger, primary_key=True)
    reason = Column(UnicodeText, default="")
    time = Column(DateTime, default=datetime.now)

    def __init__(self, user_id: int, reason: str = "", time: datetime = None):
        self.user_id = user_id
        self.reason = reason
        self.time = time or datetime.now()

    def __repr__(self):
        return f"<AFK {self.user_id} reason='{self.reason}'>"


# ---------------------------
# AFK DB / Cache Operations
# ---------------------------

async def check_afk_status(user_id: int) -> AFK | None:
    """Return AFK object from DB (async)."""
    async with INSERTION_LOCK.key(user_id):
        async with async_session() as session:
            return await session.get(AFK, user_id)


async def is_afk(user_id: int) -> bool:
    """Check local cache if user is AFK."""
    return user_id in AFK_USERS


async def set_afk(user_id: int, reason: str = "") -> None:
    """Mark user as AFK (writes to DB and cache)."""
    async with INSERTION_LOCK.key(user_id):
        now = datetime.now()
        async with async_session() as session:
            afk = await session.get(AFK, user_id)
            if not afk:
                afk = AFK(user_id, reason, now)
            else:
                afk.reason = reason
                afk.time = now

            session.add(afk)
            await session.commit()
            AFK_USERS[user_id] = {"reason": reason, "time": afk.time}


async def rm_afk(user_id: int) -> None:
    """Remove AFK completely (DB + cache)."""
    async with INSERTION_LOCK.key(user_id):
        async with async_session() as session:
            afk = await session.get(AFK, user_id)
            if afk:
                await session.delete(afk)
                await session.commit()
            AFK_USERS.pop(user_id, None)


async def load_afk_cache() -> None:
    """Load all AFK users from DB into local cache on startup."""
    global AFK_USERS
    async with async_session() as session:
        result = await session.scalars(select(AFK))
        AFK_USERS = {x.user_id: {"reason": x.reason, "time": x.time} for x in result}


# ---------------------------
# Startup
# ---------------------------
async def startup():
    await load_afk_cache()
