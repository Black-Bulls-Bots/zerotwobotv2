from zerotwo.sql import Base, async_session, CustomLockManager
from sqlalchemy import Column, String, UnicodeText, distinct, func, select, delete

class Disable(Base):
    __tablename__ = "disabled_commands"

    chat_id = Column(String(14), primary_key=True)
    command = Column(UnicodeText, primary_key=True)

    def __init__(self, chat_id, command):
        self.chat_id = chat_id
        self.command = command

    def __repr__(self):
        return "Disabled cmd {} in {}".format(self.command, self.chat_id)


DISABLED = {}

CUSTOM_LOCK = CustomLockManager()

async def disable_command(chat_id: str, command: str) -> bool:
    """Disable a command in a specific chat."""
    async with CUSTOM_LOCK.key(chat_id):
        async with async_session() as session:
            res = await session.get(Disable, (str(chat_id), command))
            if not res:
                DISABLED.setdefault(str(chat_id), set()).add(command.lower())
                session.add(Disable(chat_id=str(chat_id), command=command.lower()))
                await session.commit()
                return True
    return False


async def enable_command(chat_id: str, command: str) -> bool:
    """Enable a command in a specific chat."""
    async with CUSTOM_LOCK.key(chat_id):
        async with async_session() as session:
            res = await session.get(Disable, (str(chat_id), command))
            if res:
                DISABLED.get(str(chat_id), set()).discard(command.lower())
                await session.delete(res)
                await session.commit()
                return True
    return False


def is_command_disabled(chat_id: str, command: str) -> bool:
    """Check if a command is disabled in this chat."""
    return command.lower() in DISABLED.get(str(chat_id), set())


def get_all_disabled(chat_id: str) -> set:
    """Get all disabled commands for a chat."""
    return DISABLED.get(str(chat_id), set())


async def num_chats() -> int:
    async with async_session() as session:
        res = await session.execute(select(func.count(distinct(Disable.chat_id))))
        return res.scalar() or 0


async def num_disabled() -> int:
    async with async_session() as session:
        res = await session.execute(select(func.count(Disable)))
        return res.scalar() or 0


async def migrate_chat(old_chat_id: str, new_chat_id: str):
    async with CustomLockManager.key(old_chat_id), CustomLockManager.key(new_chat_id):
        async with async_session() as session:
            # Update database entries
            await session.execute(
                f"UPDATE {Disable.__tablename__} SET chat_id = :new_id WHERE chat_id = :old_id",
                {"new_id": str(new_chat_id), "old_id": str(old_chat_id)},
            )
            await session.commit()

        # Update in-memory cache
        if old_chat_id in DISABLED:
            DISABLED[new_chat_id] = DISABLED.pop(old_chat_id)


async def __load_disabled_commands():
    """Preload all disabled commands into memory."""
    global DISABLED
    async with async_session() as session:
        res = await session.execute(select(Disable))
        rows = res.scalars().all()
        for row in rows:
            DISABLED.setdefault(row.chat_id, set()).add(row.command.lower())

# ---------------------------
# Startup
# ---------------------------
async def startup():
    await __load_disabled_commands()