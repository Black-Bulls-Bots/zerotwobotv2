import asyncio
import time
from typing import Union, Optional

from sqlalchemy import Column, String, Boolean, UnicodeText, BigInteger, select
from zerotwo.sql import Base, async_session, CustomLockManager


class ChatAccessConnectionSettings(Base):
    __tablename__ = "access_connection"
    chat_id = Column(String(14), primary_key=True)
    allow_connect_to_chat = Column(Boolean, default=True)

    def __init__(self, chat_id: Union[str, int], allow_connect_to_chat: bool = True):
        self.chat_id = str(chat_id)
        self.allow_connect_to_chat = bool(allow_connect_to_chat)

    def __repr__(self):
        return f"<Chat access settings ({self.chat_id}) is {self.allow_connect_to_chat}>"


class Connection(Base):
    __tablename__ = "connection"
    user_id = Column(BigInteger, primary_key=True)
    chat_id = Column(String(14))

    def __init__(self, user_id: int, chat_id: Union[str, int]):
        self.user_id = int(user_id)
        self.chat_id = str(chat_id)


class ConnectionHistory(Base):
    __tablename__ = "connection_history"
    user_id = Column(BigInteger, primary_key=True)
    chat_id = Column(String(14), primary_key=True)
    chat_name = Column(UnicodeText)
    conn_time = Column(BigInteger)

    def __init__(self, user_id: int, chat_id: Union[str, int], chat_name: str, conn_time: int):
        self.user_id = int(user_id)
        self.chat_id = str(chat_id)
        self.chat_name = chat_name
        self.conn_time = int(conn_time)

    def __repr__(self):
        return f"<ConnectionHistory user {self.user_id} chat {self.chat_id}>"


# ---------------------------
# Locks & Cache
# ---------------------------
CHAT_ACCESS_LOCK = CustomLockManager()
CONNECTION_LOCK = CustomLockManager()
CONNECTION_HISTORY_LOCK = CustomLockManager()

HISTORY_CONNECT: dict[int, dict[int, dict[str, str]]] = {}


# ---------------------------
# Chat Access
# ---------------------------
async def allow_connect_to_chat(chat_id: Union[str, int]) -> bool:
    chat_id = str(chat_id)
    async with CHAT_ACCESS_LOCK.key(chat_id):
        async with async_session() as session:
            setting = await session.get(ChatAccessConnectionSettings, chat_id)
            return bool(setting and setting.allow_connect_to_chat)


async def set_allow_connect_to_chat(chat_id: Union[str, int], setting: bool):
    chat_id = str(chat_id)
    async with CHAT_ACCESS_LOCK.key(chat_id):
        async with async_session() as session:
            obj = await session.get(ChatAccessConnectionSettings, chat_id)
            if not obj:
                obj = ChatAccessConnectionSettings(chat_id, setting)
            else:
                obj.allow_connect_to_chat = setting
            session.add(obj)
            await session.commit()


# ---------------------------
# Connections
# ---------------------------
async def connect(user_id: int, chat_id: Union[int, str]) -> bool:
    user_id = int(user_id)
    chat_id = str(chat_id)
    async with CONNECTION_LOCK.key(user_id):
        async with async_session() as session:
            prev = await session.get(Connection, user_id)
            if prev:
                await session.delete(prev)
            session.add(Connection(user_id, chat_id))
            await session.commit()
            return True


async def get_connected_chat(user_id: int) -> Optional[Connection]:
    user_id = int(user_id)
    async with async_session() as session:
        return await session.get(Connection, user_id)


async def disconnect(user_id: int) -> bool:
    user_id = int(user_id)
    async with CONNECTION_LOCK.key(user_id):
        async with async_session() as session:
            existing = await session.get(Connection, user_id)
            if existing:
                await session.delete(existing)
                await session.commit()
                return True
            return False


# ---------------------------
# Connection History
# ---------------------------
async def add_history_conn(user_id: int, chat_id: Union[int, str], chat_name: str):
    user_id = int(user_id)
    chat_id = str(chat_id)
    conn_time = int(time.time())

    async with CONNECTION_HISTORY_LOCK.key(user_id):
        async with async_session() as session:
            HISTORY_CONNECT.setdefault(user_id, {})

            # Remove existing entry for same chat
            to_delete = None
            for ts, data in HISTORY_CONNECT[user_id].items():
                if data["chat_id"] == chat_id:
                    to_delete = ts
                    break
            if to_delete:
                old = await session.get(ConnectionHistory, (user_id, chat_id))
                if old:
                    await session.delete(old)
                HISTORY_CONNECT[user_id].pop(to_delete, None)

            # Maintain max 5 entries
            if len(HISTORY_CONNECT[user_id]) >= 5:
                oldest = sorted(HISTORY_CONNECT[user_id])[:-4]
                for ts in oldest:
                    old_chat_id = HISTORY_CONNECT[user_id][ts]["chat_id"]
                    old = await session.get(ConnectionHistory, (user_id, old_chat_id))
                    if old:
                        await session.delete(old)
                    HISTORY_CONNECT[user_id].pop(ts, None)

            # Add new entry
            history = ConnectionHistory(user_id, chat_id, chat_name, conn_time)
            session.add(history)
            await session.commit()
            HISTORY_CONNECT[user_id][conn_time] = {"chat_name": chat_name, "chat_id": chat_id}


async def get_history_conn(user_id: int) -> dict[int, dict[str, str]]:
    user_id = int(user_id)
    return HISTORY_CONNECT.setdefault(user_id, {})


async def clear_history_conn(user_id: int) -> bool:
    user_id = int(user_id)
    async with CONNECTION_HISTORY_LOCK.key(user_id):
        async with async_session() as session:
            for ts in list(HISTORY_CONNECT.get(user_id, {})):
                chat_id = HISTORY_CONNECT[user_id][ts]["chat_id"]
                old = await session.get(ConnectionHistory, (user_id, chat_id))
                if old:
                    await session.delete(old)
                HISTORY_CONNECT[user_id].pop(ts, None)
            await session.commit()
            return True


async def __load_user_history():
    global HISTORY_CONNECT
    async with async_session() as session:
        result = await session.scalars(select(ConnectionHistory))
        HISTORY_CONNECT.clear()
        for x in result:
            HISTORY_CONNECT.setdefault(x.user_id, {})[x.conn_time] = {
                "chat_name": x.chat_name,
                "chat_id": x.chat_id
            }


# ---------------------------
# Startup
# ---------------------------
async def startup():
    await __load_user_history()
