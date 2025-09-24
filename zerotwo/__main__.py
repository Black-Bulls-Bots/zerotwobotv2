import asyncio
import contextlib
import importlib
import random
import re
import time
import traceback
import html
import json
from typing import Optional

from telegram import Chat, InlineKeyboardButton, InlineKeyboardMarkup, Update, User
from telegram.constants import ParseMode

from telegram.ext import (
    ApplicationHandlerStop,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    Application
)
from telegram.helpers import escape_markdown
from telegram.error import BadRequest, Forbidden, TelegramError, TimedOut, ChatMigrated, NetworkError


from zerotwo import (
    ALLOW_EXCL,
    ALIVE_TEXT,
    BOT_API_VERSION,
    BOT_VERSION,
    LOGGER,
    OWNER_ID,
    TOKEN,
    PORT,
    PTB_VERSION,
    PYTHON_VERSION,
    URL,
    WEBHOOK,
    StartTime,
    application,
)
from zerotwo.helpers.chat_status import is_user_admin
from zerotwo.helpers.misc import paginate_modules
from zerotwo.modules import ALL_MODULES
from zerotwo.modules.connection import connected
from zerotwo.sql import init_db

# -------------------------------
# Constants & Shared Strings
# -------------------------------
ZEROTWO_IMG = "https://telegra.ph/file/5b9bc54b0ae753bb1ec18.jpg"
DONATE_STRING = (
    "Heya, glad to hear you want to donate!\n"
    "You can support the project by contacting @kishoreee.\n"
    "Supporting isn't always financial!\n"
    "Those who cannot provide monetary support are welcome to help us develop the bot at @blackbulls_support."
)

HELP_STRINGS = """
Hey there!
My Name is {}, from Darling in The FranXX. Take me as your group's darling to have fun with me.

*Main commands available:*
• /help — PM's you this message.
• /help <module name> — PM's you info about that module.
• /settings:
  • in PM — will send you your settings for all supported modules.
  • in group — will redirect you to PM, with all that chat's settings.

{}
""".format(
    "{}", "" if not ALLOW_EXCL else "\nAll commands can either be used with / or !.\n"
)

# -------------------------------
# Module loading
# -------------------------------
IMPORTED = {}
MIGRATEABLE = []
HELPABLE = {}
STATS = []
USER_INFO = []
DATA_IMPORT = []
DATA_EXPORT = []
CHAT_SETTINGS = {}
USER_SETTINGS = {}

for module_name in ALL_MODULES:
    imported_module = importlib.import_module(f"zerotwo.modules.{module_name}")
    mod_name = getattr(imported_module, "__mod_name__", imported_module.__name__)
    if mod_name.lower() in IMPORTED:
        raise Exception(f"Duplicate module name: {mod_name}")
    IMPORTED[mod_name.lower()] = imported_module

    if getattr(imported_module, "__help__", None):
        HELPABLE[mod_name.lower()] = imported_module
    if hasattr(imported_module, "__migrate__"):
        MIGRATEABLE.append(imported_module)
    if hasattr(imported_module, "__stats__"):
        STATS.append(imported_module)
    if hasattr(imported_module, "__user_info__"):
        USER_INFO.append(imported_module)
    if hasattr(imported_module, "__import_data__"):
        DATA_IMPORT.append(imported_module)
    if hasattr(imported_module, "__export_data__"):
        DATA_EXPORT.append(imported_module)
    if hasattr(imported_module, "__chat_settings__"):
        CHAT_SETTINGS[mod_name.lower()] = imported_module
    if hasattr(imported_module, "__user_settings__"):
        USER_SETTINGS[mod_name.lower()] = imported_module


# -------------------------------
# Utilities
# -------------------------------
def get_readable_time(seconds: int) -> str:
    time_suffix_list = ["s", "m", "h", "days"]
    time_list = []
    count = 0
    while count < 4:
        count += 1
        remainder, result = divmod(seconds, 60) if count < 3 else divmod(seconds, 24)
        if seconds == 0 and remainder == 0:
            break
        time_list.append(f"{int(result)}{time_suffix_list[count-1]}")
        seconds = int(remainder)
    if len(time_list) == 4:
        return f"{time_list.pop()}, {':'.join(reversed(time_list))}"
    return ":".join(reversed(time_list))


async def send_help(chat_id, text, keyboard=None):
    if not keyboard:
        keyboard = InlineKeyboardMarkup(paginate_modules(0, HELPABLE, "help"))
    await application.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
        reply_markup=keyboard,
    )


# -------------------------------
# Handlers
# -------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    uptime = get_readable_time(int(time.time() - StartTime))

    if update.effective_chat.type == "private":
        if args and args[0].lower() == "help":
            await send_help(
                update.effective_chat.id, HELP_STRINGS.format(context.bot.first_name)
            )
        else:
            await update.effective_message.reply_photo(
                ZEROTWO_IMG,
                caption=escape_markdown(
                    f"Hey {update.effective_user.first_name}!\n"
                    f"I'm {context.bot.first_name}, made to manage your group and have fun!\n"
                    f"Type /help to see commands.\n\n"
                    f"Version: v{BOT_VERSION}\nPython: {PYTHON_VERSION}\n"
                    f"PTB: {PTB_VERSION}\nBOT_API: {BOT_API_VERSION}"
                ),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "Add to Group",
                                url=f"https://t.me/{context.bot.username}?startgroup=True",
                            )
                        ]
                    ]
                ),
            )
    else:
        await update.effective_message.reply_text(
            f"I'm running on v{BOT_VERSION}\n<b>Uptime:</b> <code>{uptime}</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Support", url="https://t.me/blackbulls_support"
                        ),
                        InlineKeyboardButton(
                            "Announcements", url="https://t.me/blackbull_bots"
                        ),
                    ]
                ]
            ),
        )


async def help_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if m := re.match(r"help_module\((.+?)\)", data):
        module = m.group(1)
        text = f"Here is the help for the *{HELPABLE[module].__mod_name__}* module:\n{HELPABLE[module].__help__}"
        markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Back", callback_data="help_back")]]
        )
    elif m := re.match(r"help_prev\((\d+)\)", data):
        page = int(m.group(1)) - 1
        text = HELP_STRINGS.format(context.bot.first_name)
        markup = InlineKeyboardMarkup(paginate_modules(page, HELPABLE, "help"))
    elif m := re.match(r"help_next\((\d+)\)", data):
        page = int(m.group(1)) + 1
        text = HELP_STRINGS.format(context.bot.first_name)
        markup = InlineKeyboardMarkup(paginate_modules(page, HELPABLE, "help"))
    elif re.match(r"help_back", data):
        text = HELP_STRINGS.format(context.bot.first_name)
        markup = InlineKeyboardMarkup(paginate_modules(0, HELPABLE, "help"))
    else:
        return

    await query.message.edit_text(
        text=text,
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
        reply_markup=markup,
    )
    await context.bot.answer_callback_query(query.id)


async def get_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    args = update.effective_message.text.split(None, 1)

    if chat.type != Chat.PRIVATE:
        await update.effective_message.reply_text(
            "Contact me in PM to get the list of possible commands.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Help", url=f"t.me/{context.bot.username}?start=help"
                        )
                    ]
                ]
            ),
        )
    elif len(args) >= 2 and args[1].lower() in HELPABLE:
        module = args[1].lower()
        await send_help(chat.id, HELPABLE[module].__help__)
    else:
        await send_help(chat.id, HELP_STRINGS.format(context.bot.first_name))


async def send_settings(
    chat: Chat | int | str,
    user: User,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    is_user=False,
):
    if is_user:
        if USER_SETTINGS:
            settings = "\n\n".join(
                f"*{mod.__mod_name__}*:\n{mod.__user_settings__(user.id)}"
                for mod in USER_SETTINGS.values()
            )
            await application.bot.send_message(
                user.id,
                f"These are your current settings:\n\n{settings}",
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            await application.bot.send_message(
                user.id,
                "No user-specific settings available.",
                parse_mode=ParseMode.MARKDOWN,
            )
    else:
        if CHAT_SETTINGS:
            if not isinstance(chat, Chat):
                chat = await context.bot.get_chat(chat)
            conn = await connected(context.bot, update, chat, user.id, need_admin=True)
            chat_obj = await application.bot.getChat(conn)
            await application.bot.send_message(
                user.id,
                f"Which module would you like to check {chat_obj.title}'s settings for?",
                reply_markup=InlineKeyboardMarkup(
                    paginate_modules(0, CHAT_SETTINGS, "stngs", chat=chat.id)
                ),
            )
        else:
            await application.bot.send_message(
                user.id, "No chat settings available.", parse_mode=ParseMode.MARKDOWN
            )


async def settings_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if m := re.match(r"stngs_module\((.+?),(.+?)\)", data):
        chat_id, module = m.groups()
        chat = await context.bot.get_chat(chat_id)
        text = f"*{escape_markdown(chat.title)}* has the following settings for the *{CHAT_SETTINGS[module].__mod_name__}* module:\n\n{CHAT_SETTINGS[module].__chat_settings__(chat_id, update.effective_user.id)}"
        markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Back", callback_data=f"stngs_back({chat_id})")]]
        )
    elif m := re.match(r"stngs_prev\((.+?),(\d+)\)", data):
        chat_id, page = m.groups()
        chat = await context.bot.get_chat(chat_id)
        text = f"Settings for {chat.title}:"
        markup = InlineKeyboardMarkup(
            paginate_modules(int(page) - 1, CHAT_SETTINGS, "stngs", chat=chat_id)
        )
    elif m := re.match(r"stngs_next\((.+?),(\d+)\)", data):
        chat_id, page = m.groups()
        chat = await context.bot.get_chat(chat_id)
        text = f"Settings for {chat.title}:"
        markup = InlineKeyboardMarkup(
            paginate_modules(int(page) + 1, CHAT_SETTINGS, "stngs", chat=chat_id)
        )
    elif m := re.match(r"stngs_back\((.+?)\)", data):
        chat_id = m.group(1)
        chat = await context.bot.get_chat(chat_id)
        text = f"Settings for {escape_markdown(chat.title)}:"
        markup = InlineKeyboardMarkup(
            paginate_modules(0, CHAT_SETTINGS, "stngs", chat=chat_id)
        )
    else:
        return

    await query.message.reply_text(
        text=text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup
    )
    await context.bot.answer_callback_query(query.id)
    await query.message.delete()


async def get_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message

    if chat.type != Chat.PRIVATE:
        if await is_user_admin(chat, user.id):
            await msg.reply_text(
                "Click here to get this chat's settings, as well as yours.",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "Settings",
                                url=f"t.me/{context.bot.username}?start=stngs_{chat.id}",
                            )
                        ]
                    ]
                ),
            )
        else:
            await msg.reply_text("Click here to check your settings.")
    else:
        await send_settings(chat, user, update, context, True)


async def migrate_chats(update: Update, _: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if msg.migrate_to_chat_id:
        old_chat, new_chat = update.effective_chat.id, msg.migrate_to_chat_id
    elif msg.migrate_from_chat_id:
        old_chat, new_chat = msg.migrate_from_chat_id, update.effective_chat.id
    else:
        return

    LOGGER.info("Migrating from %s to %s", old_chat, new_chat)
    for mod in MIGRATEABLE:
        with contextlib.suppress(KeyError, AttributeError):
            mod.__migrate__(old_chat, new_chat)
    LOGGER.info("Successfully migrated!")
    raise ApplicationHandlerStop


async def error_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    error = context.error
    try:
        raise error
    except Forbidden:
        LOGGER.error("\nForbidden Erro\n")
        LOGGER.error(error)
        raise error
        # remove update.message.chat_id from conversation list
    except BadRequest:
        LOGGER.error("\nBadRequest Error\n")
        LOGGER.error("BadRequest caught")
        LOGGER.error(error)
        raise error

        # handle malformed requests - read more below!
    except TimedOut:
        LOGGER.error("\nTimedOut Error\n")
        raise error
        # handle slow connection problems
    except NetworkError:
        LOGGER.error("\n NetWork Error\n")
        raise error
        # handle other connection problems
    except ChatMigrated as err:
        LOGGER.error("\n ChatMigrated error\n")
        raise error
        LOGGER.error(err)
        # the chat_id of a group has changed, use e.new_chat_id instead
    except TelegramError:
        LOGGER.error(error)
        raise # then only it sends the message to the owner
        # handle all other telegram related errors

async def post_init(application: Application):

    try:
        await application.bot.sendMessage(-1002720800208, random.choice(ALIVE_TEXT))

    except Forbidden:
        raise(
            "Bot isn't able to send message to support_chat, go and check!",
        )


    except BadRequest as e:
        raise(e.message)
        

# -------------------------------
# Main
# -------------------------------
async def main():
    await init_db()
    application.add_handler(CommandHandler("start", start, block=False))
    application.add_handler(CommandHandler("help", get_help, block=False))
    application.add_handler(
        CallbackQueryHandler(help_button, pattern=r"help_.*", block=False)
    )
    application.add_handler(CommandHandler("settings", get_settings, block=False))
    application.add_handler(
        CallbackQueryHandler(settings_button, pattern=r"stngs_", block=False)
    )
    application.add_handler(
        MessageHandler(filters.StatusUpdate.MIGRATE, migrate_chats, block=False)
    )

    application.add_error_handler(error_callback)

    if WEBHOOK:
        LOGGER.info("Using webhooks.")
        await application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TOKEN,
            key="bot.key",
            cert="cert.pem",
            webhook_url=URL,
            drop_pending_updates=False,
        )
    else:
        LOGGER.info("Using long polling.")
        # await application.run_polling(drop_pending_updates=False, close_loop=False)
        await application.initialize()
        await post_init(application=application)
        await application.start()
        await application.updater.start_polling(drop_pending_updates=False)

        try:
            await asyncio.Event().wait()
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            await application.stop()
            await application.shutdown()        

if __name__ == "__main__":
    LOGGER.info("Successfully loaded modules: %s", ALL_MODULES)
    asyncio.run(main())