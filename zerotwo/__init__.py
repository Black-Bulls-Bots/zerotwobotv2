"""
A python based telegram bot to manage group with anime theme
"""

__author__ = "Joker Hacker"
__version__ = "1.1-alpha"


import logging
import os
import time
import platform
from telegram import __bot_api_version__
from telegram import __version__ as ptb_version
from telegram.ext import Application
import telegram.ext as tg

from dotenv import load_dotenv


StartTime = time.time()

#load .env file
load_dotenv()

##ENV VARIABLES
BOT_VERSION = __version__
"zerotwo bot version"
PTB_VERSION = ptb_version
"`python-telegram-bot` library version"
BOT_API_VERSION = __bot_api_version__
"telegram bot API version"
PYTHON_VERSION = platform.python_version()
"installed python version"
LOGGER_LEVEL = os.environ.get("LOGGER_LEVEL", "INFO") 
"logger level, `debug(10)`, `info(20)`, `warn(30)` and `error(40)`. default is `info`"


TOKEN = os.environ.get("TOKEN", None)
"bot token obtained from bot father"
API_ID = os.environ.get("API_ID", "")
"API ID obtained from api.telegram.org"
API_HASH = os.environ.get("API_HASH", "") 
"API HASH obtained from api.telegram.org"
OWNER_ID = int(os.environ.get("OWNER_ID", None)) #type: ignore
"Telegram ID of the bot owner"
OWNER_USERNAME = os.environ.get("OWNER_USERNAME", None)
"Telegram username of the bot owner, as `@username`"
JOIN_LOGGER = os.environ.get("JOIN_LOGGER", None)
"channel ID with `-` for keeping track of new chats where the bot gets added"
EVENT_LOGS = os.environ.get("EVENT_LOGS", None)
"channel ID with `-` for keeping track of gban, sudo and other"
SUPPORT_CHAT = os.environ.get("SUPPORT_CHAT", "")
"Support chat ID, where bot would say hi and hello."

DB_URI = os.environ.get("DB_URI", None)
"Database URL of postgresql"

LOAD = os.environ.get("LOAD", "").split()
"Modules to load, separated by space"
NO_LOAD = os.environ.get("NO_LOAD", "").split()
"Modules to not load, sepaated by space"
ALLOW_EXCL = os.environ.get("ALLOW_EXCL", False)
WEBHOOK = bool(os.environ.get("WEBHOOK", False))
URL = os.environ.get("URL", "")  # Does not contain token
PORT = int(os.environ.get("PORT", 5000))
CERT_PATH = os.environ.get("CERT_PATH")


ALIVE_TEXT = [
    "I'm not alone. I'm with you, Darling.",
    "I've got you, Darling. I won't let you go anymore.",
    "I've killed countless people. But I want to live with you.",
    "If I have to be a monster to be with you, so be it.",
    "I never knew a world without you in it, and I don't want to.",
    "I won't let them keep us apart. Not now, not ever.",
    "I'd forgotten so much. But I could never forget you.",
    "I want to be with you, even if it's just for a little while longer.",
    "Every moment with you is a treasure.",
    "Don't leave me alone, Darling.",
    "I want to be human, so I can be with you.",
    "The pain of being alone is something I never want to experience again.",
    "This is where I want to be, with you.",
    "When I'm with you, I feel so alive.",
    "You are my Darling. No one else's.",
    "I want to be the only one you need.",
    "You make me feel human.",
    "I never thought I'd find someone who understands me like you do.",
    "Even in the darkest times, you bring light into my life.",
    "I don't want to be alone anymore.",
    "Every day with you is a day worth living.",
    "I love you more than anything in this world.",
    "You are the most precious person to me.",
    "There's nothing I want more than to be with you.",
    "Life is better with you in it.",
    "I don't need anything else as long as I have you.",
    "I want to be where you are, always.",
    "I'll follow you to the ends of the earth, Darling.",
    "I don't care about the past. I just want a future with you.",
    "No matter what happens, I'll always come back to you.",
    "I want to create a world where we can be together.",
    "You're my reason for living.",
    "With you, every day feels like a new adventure.",
    "There's no place like home, and you are my home.",
    "When you're by my side, I can do anything.",
    "I will never let anyone hurt you.",
    "You're the one who gave me a reason to keep going.",
    "I've never felt more complete than when I'm with you.",
    "I can't imagine my life without you in it.",
    "I want to be by your side, always.",
    "You're my partner in crime, and I wouldn't have it any other way.",
    "You make the world a better place, just by being in it.",
    "You're the person I want to wake up to every morning.",
    "Our love is the most beautiful story ever told.",
    "I want to cherish every moment with you.",
    "With you, life is an endless journey of joy.",
    "I'm not perfect, but I'm perfect for you.",
    "I don't need a million things. I just need you.",
    "In your arms, I've found my paradise.",
    "I love you more than words can express."
]
"Some of the great words said by zero two, bot will be sending this once n hour in support chat"

#enable logging
logging.basicConfig(
    format= "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("log.txt"), logging.StreamHandler()],
    level=LOGGER_LEVEL
)

LOGGER = logging.getLogger(__name__)


application = Application.builder().token(TOKEN).concurrent_updates(True).build()


# Load at end to ensure all prev variables have been set
from zerotwo.helpers.handlers import (
    CustomCommandHandler,
    CustomMessageHandler,
)

# make sure the regex handler can take extra kwargs
tg.CommandHandler = CustomCommandHandler
tg.MessageHandler = CustomMessageHandler