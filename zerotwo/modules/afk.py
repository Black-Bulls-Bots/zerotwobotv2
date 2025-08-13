import random
import html
from datetime import datetime
import humanize

from zerotwo import LOGGER, application
from zerotwo.modules.disable import (
    DisableAbleCommandHandler,
    DisableAbleMessageHandler,
)
from zerotwo.sql import afk as sql
from zerotwo.modules.users import get_user_id
from telegram import MessageEntity, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes, filters, MessageHandler

AFK_GROUP = 7
AFK_REPLY_GROUP = 8


async def afk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not update.effective_message.text:
        return

    args = update.effective_message.text.split(None, 1)
    reason = args[1] if len(args) > 1 else ""
    notice = ""

    if len(reason) > 100:
        reason = reason[:100]
        notice = "\nYour AFK reason was shortened to 100 characters."

    await sql.set_afk(user.id, reason)

    fname = user.first_name or "there"
    msg_text = f"{fname} is now away! \nReason: <code>{reason}</code> \n{notice}" if reason else f"{fname} is now away!{notice}"

    try:
        await update.effective_message.reply_text(msg_text, parse_mode="html")
    except BadRequest:
        return


async def no_longer_afk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.effective_message

    if not user:
        return

    afk_user = await sql.check_afk_status(user.id)
    if not afk_user:
        return

    afk_duration = humanize.naturaldelta(datetime.now() - afk_user.time)

    await sql.rm_afk(user.id)

    if message.new_chat_members:
        return

    firstname = user.first_name or "there"
    messages = [
        "Look who's back — {}!",
        "{} has risen from the shadows!",
        "{} decided to grace us again!",
        "{} has returned from the void!",
        "{} is back from their secret mission!",
        "{} is alive and kicking!",
        "{} just dropped back in!",
        "{} couldn’t stay away for long!",
        "{} is back in action!",
        "{} has rejoined the chaos!",
        "{} is back, better than ever!",
        "{} sneaked back into the chat!",
        "{} has returned… did you miss them?",
        "{} wandered off but found their way back!",
        "{} is back to steal the spotlight!",
        "{} has come back to save the day!",
        "{} is here — cue the applause!",
        "{} is finally back from their nap!",
        "{} reappeared like magic!"
    ]
    
    chosen_message = random.choice(messages).format(firstname)
    await message.reply_text(
        f"{chosen_message}\nYou were AFK for: <code>{afk_duration}</code>",
        parse_mode="html"
    )


async def reply_afk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot
    message = update.effective_message
    userc = update.effective_user
    userc_id = userc.id
    if message.entities and message.parse_entities(
        [MessageEntity.TEXT_MENTION, MessageEntity.MENTION],
    ):
        entities = message.parse_entities(
            [MessageEntity.TEXT_MENTION, MessageEntity.MENTION],
        )

        chk_users = []
        for ent in entities:
            if ent.type == MessageEntity.TEXT_MENTION:
                user_id = ent.user.id
                fst_name = ent.user.first_name

                if user_id in chk_users:
                    return
                chk_users.append(user_id)

            if ent.type != MessageEntity.MENTION:
                return

            user_id = await get_user_id(
                message.text[ent.offset: ent.offset + ent.length],
            )
            if not user_id:
                # Should never happen, since for a user to become AFK they must have spoken. Maybe changed username?
                return

            if user_id in chk_users:
                return
            chk_users.append(user_id)

            try:
                chat = await bot.get_chat(user_id)
            except BadRequest:
                LOGGER.error("Error: Could not fetch userid {} for AFK module".format(user_id))
                return
            fst_name = chat.first_name

            await check_afk(update, context, user_id, fst_name, userc_id)

    elif message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        fst_name = message.reply_to_message.from_user.first_name
        await check_afk(update, context, user_id, fst_name, userc_id)

async def check_afk(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, fst_name: str, userc_id: int):
    if sql.is_afk(user_id):
        user = await sql.check_afk_status(user_id)

        if int(userc_id) == int(user_id):
            return

        time = humanize.naturaldelta(datetime.now() - user.time)

        if not user.reason:
            res = "{} is afk.\n\nLast seen {} ago.".format(
                fst_name,
                time,
            )
            await update.effective_message.reply_text(res)
        else:
            res = "{} is afk.\nReason: <code>{}</code>\n\nLast seen {} ago.".format(
                html.escape(fst_name),
                html.escape(user.reason),
                time,
            )
            await update.effective_message.reply_text(res, parse_mode="html")

# ---------------------------
# Handlers
# ---------------------------
AFK_HANDLER = DisableAbleCommandHandler("afk", afk, block=False)
AFK_REGEX_HANDLER = DisableAbleMessageHandler(filters.Regex(r"(?i)^brb(.*)$"), afk, friendly="afk", block=False)
NO_AFK_HANDLER = MessageHandler(filters.ALL & filters.ChatType.GROUPS, no_longer_afk, block=False)
AFK_REPLY_HANDLER = MessageHandler(filters.ALL & filters.ChatType.GROUPS, reply_afk, block=False)

application.add_handler(AFK_HANDLER, AFK_GROUP)
application.add_handler(AFK_REGEX_HANDLER, AFK_GROUP)
application.add_handler(NO_AFK_HANDLER, AFK_GROUP)
application.add_handler(AFK_REPLY_HANDLER, AFK_REPLY_GROUP)

__mod_name__ = "AFK"
__command_list__ = ["afk"]
__handlers__ = [
    (AFK_HANDLER, AFK_GROUP),
    (AFK_REGEX_HANDLER, AFK_GROUP),
    (NO_AFK_HANDLER, AFK_GROUP),
    (AFK_REPLY_HANDLER, AFK_REPLY_GROUP),
]
