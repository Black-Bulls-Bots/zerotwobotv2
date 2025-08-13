from zerotwo import application
from zerotwo.sql import Base, CustomLockManager, async_session
from sqlalchemy import Column, ForeignKey, Integer, BigInteger, String, UnicodeText, UniqueConstraint, func, select, update, delete
from sqlalchemy.exc import NoResultFound


class Users(Base):
    __tablename__ = "users"
    user_id = Column(BigInteger, primary_key=True)
    username = Column(UnicodeText)

    def __init__(self, user_id, username=None):
        self.user_id = user_id
        self.username = username

    def __repr__(self):
        return f"<User {self.username} ({self.user_id})>"


class Chats(Base):
    __tablename__ = "chats"
    chat_id = Column(String(14), primary_key=True)
    chat_name = Column(UnicodeText, nullable=False)

    def __init__(self, chat_id, chat_name):
        self.chat_id = str(chat_id)
        self.chat_name = chat_name

    def __repr__(self):
        return f"<Chat {self.chat_name} ({self.chat_id})>"


class ChatMembers(Base):
    __tablename__ = "chat_members"
    priv_chat_id = Column(Integer, primary_key=True)
    chat = Column(
        String(14),
        ForeignKey("chats.chat_id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    )
    user = Column(
        BigInteger,
        ForeignKey("users.user_id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    )
    __table_args__ = (UniqueConstraint("chat", "user", name="_chat_members_uc"),)

    def __init__(self, chat, user):
        self.chat = chat
        self.user = user

    def __repr__(self):
        return f"<Chat user {self.user} in chat {self.chat}>"


INSERTION_LOCK = CustomLockManager()


async def ensure_bot_in_db():
    async with INSERTION_LOCK.key(application.bot.id):
        async with async_session() as session:
            bot = Users(application.bot.id, application.bot.username)
            session.merge(bot)
            await session.commit()


async def update_user(user_id, username, chat_id=None, chat_name=None):
    async with INSERTION_LOCK.key(user_id):
        async with async_session() as session:
            user = await session.get(Users, user_id)
            if not user:
                user = Users(user_id, username)
                session.add(user)
                await session.flush()
            else:
                user.username = username

            if chat_id and chat_name:
                chat = await session.get(Chats, str(chat_id))
                if not chat:
                    chat = Chats(str(chat_id), chat_name)
                    session.add(chat)
                    await session.flush()
                else:
                    chat.chat_name = chat_name

                exists = await session.execute(
                    select(ChatMembers)
                    .filter(ChatMembers.chat == str(chat_id), ChatMembers.user == user_id)
                )
                if not exists.scalars().first():
                    session.add(ChatMembers(str(chat_id), user_id))

            await session.commit()


async def get_userid_by_name(username):
    async with async_session() as session:
        result = await session.execute(
            select(Users).filter(func.lower(Users.username) == username.lower())
        )
        return result.scalars().all()


async def get_name_by_userid(user_id):
    async with async_session() as session:
        return await session.get(Users, int(user_id))


async def get_chat_members(chat_id):
    async with async_session() as session:
        result = await session.execute(
            select(ChatMembers).filter(ChatMembers.chat == str(chat_id))
        )
        return result.scalars().all()


async def get_all_chats():
    async with async_session() as session:
        result = await session.execute(select(Chats))
        return result.scalars().all()


async def get_all_users():
    async with async_session() as session:
        result = await session.execute(select(Users))
        return result.scalars().all()


async def get_user_num_chats(user_id):
    async with async_session() as session:
        result = await session.execute(
            select(func.count()).filter(ChatMembers.user == int(user_id))
        )
        return result.scalar()


async def get_user_com_chats(user_id):
    async with async_session() as session:
        result = await session.execute(
            select(ChatMembers.chat).filter(ChatMembers.user == int(user_id))
        )
        return [row for row in result.scalars().all()]


async def num_chats():
    async with async_session() as session:
        result = await session.execute(select(func.count()).select_from(Chats))
        return result.scalar()


async def num_users():
    async with async_session() as session:
        result = await session.execute(select(func.count()).select_from(Users))
        return result.scalar()


async def migrate_chat(old_chat_id, new_chat_id):
    async with INSERTION_LOCK.key(str(old_chat_id)):
        async with async_session() as session:
            chat = await session.get(Chats, str(old_chat_id))
            if chat:
                chat.chat_id = str(new_chat_id)
            await session.execute(
                update(ChatMembers)
                .where(ChatMembers.chat == str(old_chat_id))
                .values(chat=str(new_chat_id))
            )
            await session.commit()


async def del_user(user_id):
    async with INSERTION_LOCK.key(user_id):
        async with async_session() as session:
            user = await session.get(Users, user_id)
            if user:
                await session.delete(user)
                await session.commit()
                return True
            await session.execute(
                delete(ChatMembers).where(ChatMembers.user == user_id)
            )
            await session.commit()
    return False


async def rem_chat(chat_id):
    async with INSERTION_LOCK.key(str(chat_id)):
        async with async_session() as session:
            chat = await session.get(Chats, str(chat_id))
            if chat:
                await session.delete(chat)
                await session.commit()
