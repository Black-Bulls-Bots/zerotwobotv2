import asyncio
import time
from typing import Union, Optional

from sqlalchemy import Column, String, Boolean, UnicodeText, Integer, BigInteger, select
from zerotwo.sql import Base, async_session


class ChatAccessConnectionSettings(Base):
    __tablename__ = "access_connection"

    chat_id = Column(String(14), primary_key=True)
    allow_connect_to_chat = Column(Boolean, default=True)

    def __init__(self, chat_id: Union[str, int], allow_connect_to_chat: bool):
        self.chat_id = str(chat_id)
        self.allow_connect_to_chat = bool(allow_connect_to_chat)

    def __repr__(self):
        return f"<Chat access settings ({self.chat_id}) is {self.allow_connect_to_chat}>"


class Connection(Base):
    __tablename__ = "connection"

    user_id = Column(BigInteger, primary_key=True)
    chat_id = Column(String(14))

    def __init__(self, user_id: int, chat_id: Union[str]):
        self.user_id = int(user_id)
        self.chat_id = str(chat_id)


class ConnectionHistory(Base):
    __tablename__ = "connection_history"

    user_id = Column(BigInteger, primary_key=True)
    chat_id = Column(String(14), primary_key=True)
    chat_name = Column(UnicodeText)
    conn_time = Column(Integer)

    def __init__(self, user_id: int, chat_id: Union[str, int], chat_name: str, conn_time: int):
        self.user_id = int(user_id)
        self.chat_id = str(chat_id)
        self.chat_name = str(chat_name)
        self.conn_time = int(conn_time)

    def __repr__(self):
        return f"<connection user {self.user_id} history {self.chat_id}>"


# ---------------------------
# Locks & Cache
# ---------------------------
CHAT_ACCESS_LOCK = asyncio.Lock()
CONNECTION_INSERTION_LOCK = asyncio.Lock()
CONNECTION_HISTORY_LOCK = asyncio.Lock()

HISTORY_CONNECT: dict[int, dict[int, dict[str, str]]] = {}


# ---------------------------
# CRUD Functions
# ---------------------------
async def allow_connect_to_chat(chat_id: Union[str, int]) -> bool:
    """Allow whether connection to this chat can be turned on or off"""
    async with async_session() as session:
        setting = await session.get(ChatAccessConnectionSettings, str(chat_id))
        return bool(setting and setting.allow_connect_to_chat)


async def set_allow_connect_to_chat(chat_id: Union[int, str], setting: bool):
    
    async with CHAT_ACCESS_LOCK:
        async with async_session() as session:
            chat_setting = await session.get(ChatAccessConnectionSettings, str(chat_id))
            if not chat_setting:
                chat_setting = ChatAccessConnectionSettings(chat_id, setting)
            else:
                chat_setting.allow_connect_to_chat = setting
            session.add(chat_setting)
            await session.commit()


async def connect(user_id: int, chat_id: Union[int, str]) -> bool:
    async with CONNECTION_INSERTION_LOCK:
        async with async_session() as session:
            prev = await session.get(Connection, int(user_id))
            if prev:
                await session.delete(prev)
            session.add(Connection(user_id, chat_id))
            await session.commit()
            return True


async def get_connected_chat(user_id: int) -> Optional[Connection]:
    async with async_session() as session:
        return await session.get(Connection, int(user_id))


async def disconnect(user_id: int) -> bool:
    async with CONNECTION_INSERTION_LOCK:
        async with async_session() as session:
            existing = await session.get(Connection, int(user_id))
            if existing:
                await session.delete(existing)
                await session.commit()
                return True
            return False


async def add_history_conn(user_id: int, chat_id: Union[int, str], chat_name: str):
    global HISTORY_CONNECT
    async with CONNECTION_HISTORY_LOCK:
        conn_time = int(time.time())
        async with async_session() as session:
            if HISTORY_CONNECT.get(user_id):
                getchat_id = {v["chat_id"]: k for k, v in HISTORY_CONNECT[user_id].items()}
                if str(chat_id) in getchat_id:
                    todeltime = getchat_id[str(chat_id)]
                    old = await session.get(ConnectionHistory, (user_id, str(chat_id)))
                    if old:
                        await session.delete(old)
                    HISTORY_CONNECT[user_id].pop(todeltime, None)
                elif len(HISTORY_CONNECT[user_id]) >= 5:
                    to_remove = sorted(HISTORY_CONNECT[user_id])[:-4]
                    for ts in to_remove:
                        old_chat_id = HISTORY_CONNECT[user_id][ts]["chat_id"]
                        old = await session.get(ConnectionHistory, (user_id, str(old_chat_id)))
                        if old:
                            await session.delete(old)
                        HISTORY_CONNECT[user_id].pop(ts, None)
            else:
                HISTORY_CONNECT[user_id] = {}

            old = await session.get(ConnectionHistory, (user_id, str(chat_id)))
            if old:
                await session.delete(old)

            history = ConnectionHistory(user_id, chat_id, chat_name, conn_time)
            session.add(history)
            await session.commit()

            HISTORY_CONNECT[user_id][conn_time] = {"chat_name": chat_name, "chat_id": str(chat_id)}


async def get_history_conn(user_id: int) -> dict[int, dict[str, str]]:
    return HISTORY_CONNECT.setdefault(user_id, {})


async def clear_history_conn(user_id: int) -> bool:
    async with CONNECTION_HISTORY_LOCK:
        async with async_session() as session:
            for ts in list(HISTORY_CONNECT.get(user_id, {})):
                chat_old = HISTORY_CONNECT[user_id][ts]["chat_id"]
                old = await session.get(ConnectionHistory, (user_id, str(chat_old)))
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
        for x in result.all():
            HISTORY_CONNECT.setdefault(x.user_id, {})[x.conn_time] = {
                "chat_name": x.chat_name,
                "chat_id": x.chat_id
            }


# ---------------------------
# Startup
# ---------------------------
async def startup():
    await __load_user_history()
