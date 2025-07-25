import logging
import os

from telegram.ext import ApplicationBuilder

from dotenv import load_dotenv


#env variables
load_dotenv()

LOGGER_LEVEL = os.environ.get("LOGGER_LEVEL", "INFO") 

BOT_TOKEN = os.environ.get("BOT_TOKEN", None)
DB_URI = os.environ.get("DATABASE_URL", None)
LOAD = ""
NO_LOAD = ""

#enable logging

logging.basicConfig(
    format= "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("log.txt"), logging.StreamHandler()],
    level=LOGGER_LEVEL
)

LOGGER = logging.getLogger(__name__)

application = ApplicationBuilder().token(BOT_TOKEN).build()


