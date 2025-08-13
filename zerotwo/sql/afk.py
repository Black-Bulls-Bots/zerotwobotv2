
from datetime import datetime
import asyncio
from zerotwo.sql import Base, async_session, CustomLockManager
from sqlalchemy import Boolean, Column, UnicodeText, DateTime, BigInteger, select


class AFK(Base):
    __tablename__ = "afk_users"

    user_id = Column(BigInteger, primary_key=True)
    is_afk = Column(Boolean)
    reason = Column(UnicodeText)
    time = Column(DateTime)

    def __init__(self, user_id: int, reason: str = "", is_afk: bool = True, time: datetime = None):
        self.user_id = user_id
        self.reason = reason
        self.is_afk = is_afk
        self.time = time or datetime.now()

    def __repr__(self):
        return "afk_status for {}".format(self.user_id)


INSERTION_LOCK = CustomLockManager()

AFK_USERS = {}


async def is_afk(user_id: int) -> bool:
    """Checks whether given user is afk or not in local dict"""
    return user_id in AFK_USERS


async def check_afk_status(user_id: int) -> AFK | None:
    """Checks whether given user is afk or not in DB"""

    async with INSERTION_LOCK.key(user_id):
        async with async_session() as session:
            return await session.get(AFK, user_id)

async def toggle_afk(user_id: int, reason: str = None, state: bool = False) -> bool:
    "toggle between on and off of afk in DB and local cache"
    async with INSERTION_LOCK.key(user_id):
        async with async_session() as session:
            curr = await session.get(AFK, user_id)
            reason = "" if reason is None else reason
            now = datetime.now()
            if not curr:
                # New AFK entry
                curr = AFK(user_id, reason, state, now)
                AFK_USERS[user_id] = {"reason": reason, "time": now}
            else:
                # Toggle existing AFK
                curr.is_afk = not curr.is_afk
                curr.time = now  # Update timestamp whenever toggled

                if curr.is_afk:
                    curr.reason = reason
                    AFK_USERS[user_id] = {"reason": reason, "time": now}
                else:
                    AFK_USERS.pop(user_id, None)
                AFK_USERS.pop(user_id, None)             
            
            session.add(curr)
            await session.commit()
            return True
        return False
            

async def __load_afk_users():
    global AFK_USERS
    async with async_session() as session:
        all_afk = await session.execute(select(AFK))
        AFK_USERS.clear()
        AFK_USERS = {
            user.user_id: {"reason": user.reason, "time": user.time} for user in all_afk.scalars() if user.is_afk
        }
    


# ---------------------------
# Startup
# ---------------------------
async def startup():
    await __load_afk_users()