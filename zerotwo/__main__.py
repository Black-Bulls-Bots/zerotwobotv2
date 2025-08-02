from zerotwo import application
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from zerotwo.modules import ALL_MODULES
import importlib

for module in ALL_MODULES:
    imported_module = importlib.import_module("zerotwo.modules." + module)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot

    await bot.send_message(
        chat_id=update.effective_chat.id,
        text="Hola senor"
    )


if __name__ == "__main__":
    start_handler = CommandHandler('start', start)

    application.add_handler(start_handler)

    application.run_polling()