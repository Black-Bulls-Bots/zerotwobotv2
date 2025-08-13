from sqlalchemy import func, distinct, Column, String, UnicodeText, Integer, select
from zerotwo.sql import Base, async_session, CustomLockManager

class BlackListFilters(Base):
    __tablename__ = "blacklist"
    chat_id = Column(String(14), primary_key=True)
    trigger = Column(UnicodeText, primary_key=True, nullable=False)

    def __init__(self, chat_id, trigger):
        self.chat_id = str(chat_id)
        self.trigger = trigger

    def __repr__(self):
        return f"<Blacklist filter '{self.trigger}' for {self.chat_id}>"

    def __eq__(self, other):
        return (
            isinstance(other, BlackListFilters)
            and self.chat_id == other.chat_id
            and self.trigger == other.trigger
        )


class BlacklistSettings(Base):
    __tablename__ = "blacklist_settings"
    chat_id = Column(String(14), primary_key=True)
    blacklist_type = Column(Integer, default=1)
    value = Column(UnicodeText, default="0")

    def __init__(self, chat_id, blacklist_type=1, value="0"):
        self.chat_id = str(chat_id)
        self.blacklist_type = blacklist_type
        self.value = value

    def __repr__(self):
        return f"<{self.chat_id} will execute {self.blacklist_type} for blacklist trigger.>"


BLACKLIST_FILTER_INSERTION_LOCK = CustomLockManager()
BLACKLIST_SETTINGS_INSERTION_LOCK = CustomLockManager()

CHAT_BLACKLISTS: dict[str, set[str]] = {}
CHAT_SETTINGS_BLACKLISTS: dict[str, dict[str, str | int]] = {}


async def add_to_blacklist(chat_id: str, trigger: str):
    async with BLACKLIST_FILTER_INSERTION_LOCK.key(chat_id):
        async with async_session() as session:
            filt = BlackListFilters(chat_id, trigger)
            session.merge(filt)
            await session.commit()

        CHAT_BLACKLISTS.setdefault(chat_id, set()).add(trigger)


async def rm_from_blacklist(chat_id: str, trigger: str) -> bool:
    async with BLACKLIST_FILTER_INSERTION_LOCK.key(chat_id):
        async with async_session() as session:
            obj = await session.get(BlackListFilters, (chat_id, trigger))
            if not obj:
                return False

            CHAT_BLACKLISTS.get(chat_id, set()).discard(trigger)
            await session.delete(obj)
            await session.commit()
            return True


def get_chat_blacklist(chat_id: str) -> set[str]:
    return CHAT_BLACKLISTS.get(chat_id, set())


async def num_blacklist_filters() -> int:
    async with async_session() as session:
        return await session.scalar(select(func.count()).select_from(BlackListFilters))


async def num_blacklist_chat_filters(chat_id: str) -> int:
    async with async_session() as session:
        stmt = select(func.count()).select_from(BlackListFilters).filter_by(chat_id=chat_id)
        return await session.scalar(stmt)


async def num_blacklist_filter_chats() -> int:
    async with async_session() as session:
        return await session.scalar(select(func.count(distinct(BlackListFilters.chat_id))))


async def set_blacklist_strength(chat_id: str, blacklist_type: int, value: str):
    async with BLACKLIST_SETTINGS_INSERTION_LOCK.key(chat_id):
        async with async_session() as session:
            setting = await session.get(BlacklistSettings, chat_id)
            if not setting:
                setting = BlacklistSettings(chat_id, blacklist_type, value)

            setting.blacklist_type = int(blacklist_type)
            setting.value = str(value)

            session.add(setting)
            await session.commit()

        CHAT_SETTINGS_BLACKLISTS[chat_id] = {
            "blacklist_type": int(blacklist_type),
            "value": value,
        }


def get_blacklist_setting(chat_id: str) -> tuple[int, str]:
    setting = CHAT_SETTINGS_BLACKLISTS.get(chat_id)
    return (setting["blacklist_type"], setting["value"]) if setting else (1, "0")


async def __load_chat_blacklists():
    CHAT_BLACKLISTS.clear()
    async with async_session() as session:
        chats = await session.scalars(select(BlackListFilters.chat_id).distinct())
        for chat_id in chats:
            CHAT_BLACKLISTS[chat_id] = set()

        all_filters = await session.scalars(select(BlackListFilters))
        for filt in all_filters:
            CHAT_BLACKLISTS[filt.chat_id].add(filt.trigger)


async def __load_chat_settings_blacklists():
    CHAT_SETTINGS_BLACKLISTS.clear()
    async with async_session() as session:
        settings = await session.scalars(select(BlacklistSettings))
        for s in settings:
            CHAT_SETTINGS_BLACKLISTS[s.chat_id] = {
                "blacklist_type": s.blacklist_type,
                "value": s.value,
            }


async def migrate_chat(old_chat_id: str, new_chat_id: str):
    async with BLACKLIST_FILTER_INSERTION_LOCK.key(old_chat_id):
        async with async_session() as session:
            results = await session.scalars(
                select(BlackListFilters).filter_by(chat_id=old_chat_id)
            )
            for filt in results:
                filt.chat_id = str(new_chat_id)
            await session.commit()

# ---------------------------
# Startup
# ---------------------------
async def startup():
    await __load_chat_blacklists()
    await __load_chat_settings_blacklists()