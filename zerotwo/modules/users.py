import asyncio
from io import BytesIO
from typing import Union

from telegram import Update, ChatMemberAdministrator
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden, TelegramError
from telegram.ext import (
    ContextTypes,
    CommandHandler,
    filters,
    MessageHandler,
)
from telegram.helpers import escape_markdown
# from zerotwobot.modules.sql.topics_sql import get_action_topic

import zerotwo.sql.users as sql
from zerotwo import LOGGER, application
from zerotwo.helpers.chat_status import check_admin
from zerotwo.sql.users import get_all_users

USERS_GROUP = 4
CHAT_GROUP = 5


async def get_user_id(username: str) -> Union[int, None]:
    # ensure valid userid
    if len(username) <= 5:
        return None

    if username.startswith("@"):
        username = username[1:]

    users = await sql.get_userid_by_name(username)

    if not users:
        return None

    elif len(users) == 1:
        return users[0].user_id

    else:
        for user_obj in users:
            try:
                userdat = await application.bot.get_chat(user_obj.user_id)
                if userdat.username == username:
                    return userdat.id

            except BadRequest as excp:
                if excp.message == "Chat not found":
                    pass
                else:
                    LOGGER.exception("Error extracting user ID")

    return None



@check_admin(only_owner=True)
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    to_send = update.effective_message.text.split(None, 1)

    if len(to_send) >= 2:
        to_group = False
        to_user = False
        if to_send[0] == "/broadcastgroups":
            to_group = True
        if to_send[0] == "/broadcastusers":
            to_user = True
        else:
            to_group = to_user = True
        chats = await sql.get_all_chats() or []
        users = get_all_users()
        failed = 0
        failed_user = 0
        if to_group:
            for chat in chats:
                try:
                    # topic_chat = get_action_topic(chat.chat_id)
                    await context.bot.sendMessage(
                        int(chat.chat_id),
                        escape_markdown(to_send[1], 2),
                        parse_mode=ParseMode.MARKDOWN_V2,
                        disable_web_page_preview=True,
                    )
                    await asyncio.sleep(1)
                except TelegramError as e:
                    failed += 1
        if to_user:
            for user in users:
                try:
                    await context.bot.sendMessage(
                        int(user.user_id),
                        escape_markdown(to_send[1], 2),
                        parse_mode=ParseMode.MARKDOWN_V2,
                        disable_web_page_preview=True,
                    )
                    await asyncio.sleep(1)
                except TelegramError as e:
                    failed_user += 1
        await update.effective_message.reply_text(
            f"Broadcast complete.\nGroups failed: {failed}.\nUsers failed: {failed_user}.",
        )



async def log_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    msg = update.effective_message

    await sql.update_user(msg.from_user.id, msg.from_user.username, chat.id, chat.title)

    if msg.reply_to_message:
        await sql.update_user(
            msg.reply_to_message.from_user.id,
            msg.reply_to_message.from_user.username,
            chat.id,
            chat.title,
        )

    if msg.from_user:
        await sql.update_user(msg.from_user.id, msg.from_user.username)



@check_admin(only_owner=True)
async def chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    all_chats = await sql.get_all_chats() or []
    chatfile = "List of chats.\n Chat name | Chat ID | Members count | Bot Admin?\n"
    P = 1
    for chat in all_chats:
        try:
            curr_chat = await context.bot.getChat(chat.chat_id)
            bot_member = await curr_chat.get_member(context.bot.id)
            chat_members = await curr_chat.get_member_count()
            chatfile += "{}. {} | {} | {} | {}\n".format(
                P, chat.chat_name, chat.chat_id, chat_members, bot_member.ADMINISTRATOR
            )
            P = P + 1
        except Exception as e:
            LOGGER.warning(f"[Groups]: {e}")
            continue

    with BytesIO(str.encode(chatfile)) as output:
        output.name = "groups_list.txt"
        await update.effective_message.reply_document(
            document=output,
            filename="groups_list.txt",
            caption="Here be the list of groups in my database.",
        )



async def chat_checker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    try:
        bot_admin = await update.effective_message.chat.get_member(bot.id)
        if isinstance(bot_admin, ChatMemberAdministrator):
            if bot_admin.can_post_messages is False:
                await bot.leaveChat(update.effective_message.chat.id)
    except Forbidden:
        pass


def __user_info__(user_id):
    if user_id in [777000, 1087968824]:
        return """╘══「 Groups count: <code>???</code> 」"""
    if user_id == application.bot.id:
        return """╘══「 Groups count: <code>???</code> 」"""
    num_chats = sql.get_user_num_chats(user_id)
    return f"""╘══「 Groups count: <code>{num_chats}</code> 」"""


def __stats__():
    return f"• {sql.num_users()} users, across {sql.num_chats()} chats"


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


__help__ = ""  # no help string

BROADCAST_HANDLER = CommandHandler(
    ["broadcastall", "broadcastusers", "broadcastgroups"], broadcast, block=False
)
USER_HANDLER = MessageHandler(filters.ALL & filters.ChatType.GROUPS, log_user, allow_edit=True, block=False)
CHAT_CHECKER_HANDLER = MessageHandler(filters.ALL & filters.ChatType.GROUPS, chat_checker, allow_edit=True, block=False)
CHATLIST_HANDLER = CommandHandler("groups", chats, block=False)

application.add_handler(USER_HANDLER, USERS_GROUP)
application.add_handler(BROADCAST_HANDLER)
application.add_handler(CHATLIST_HANDLER)
application.add_handler(CHAT_CHECKER_HANDLER, CHAT_GROUP)

__mod_name__ = "Users"
__handlers__ = [(USER_HANDLER, USERS_GROUP), BROADCAST_HANDLER, CHATLIST_HANDLER]