### Anime module for zerotwo bot

from zerotwo import application
from httpx import AsyncClient
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CommandHandler, ContextTypes, CallbackQueryHandler, CallbackContext

api_url = "https://api.jikan.moe/v4/"

async def anime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    message = update.effective_message
    query = " ".join(context.args)

    if not query:
        await message.reply_text("You should search something, not void!")
        return

    async with AsyncClient() as client:
        r = await client.get(url=api_url + f'anime?q={query}&limit=10')
        if r.status_code in [400, 404, 405, 429, 500, 503]:
            await message.reply_text("Couldn't find this one, could be internal issue or no found.")
            return

        response = r.json()['data']
        buttons = []
        for anime in response:
            title = anime["title"]
            anime_id = anime["mal_id"]
            buttons.append([InlineKeyboardButton(title, callback_data=f"anime_{anime_id}")])

    await message.reply_text("Select an anime:", reply_markup=InlineKeyboardMarkup(buttons))

async def anime_handler(update: Update, context: CallbackContext):
    message = update.effective_message
    query = update.callback_query
    anime_id = query.data.split("_")[1]
    if not update.effective_chat.PRIVATE:
        if query.from_user.id != message.reply_to_message.from_user.id:
            await query.answer("You aren't supposed to do this, ask me on your own")
            return

    async with AsyncClient() as client:
        r = await client.get(url=f'{api_url}anime/{anime_id}')
        if r.status_code in [400, 404, 405, 429, 500, 503]:
            await query.answer("Couldn't find this one, could be internal issue or no found.")
            return

        response = r.json()['data']
        anime_type = response['type']
        if anime_type.lower() == "tv":
            emoji = "📺"
        elif anime_type.lower() == "movie":
            emoji = "🎬"
        else:
            emoji = ""

        title_english = response.get('title_english') or ''
        title_japanese = response.get('title_japanese') or ''
        anime_type = response.get('type') or ''
        title = f"{emoji} {title_english} - {title_japanese} - {anime_type}"

        image_url = response.get('images', {}).get('jpg', {}).get('large_image_url') or ''
        rating = response.get('rating') or 'N/A'
        episodes = response.get('episodes') or 'N/A'
        status = response.get('status') or 'N/A'
        score = response.get('score') or 'N/A'
        airing = response.get('airing')
        if airing is None:
            airing = 'N/A'
        duration = response.get('duration') or 'N/A'
        rank = response.get('rank') or 'N/A'

        description = response.get('synopsis') or ''
        max_desc_length = 600
        if len(description) > max_desc_length:
            description = description[:max_desc_length].rsplit(' ', 1)[0] + '...'

        year = response.get('year') or 'N/A'
        trailer_url = response.get('trailer', {}).get('url')
        buttons = []
        if trailer_url:
            buttons.append([InlineKeyboardButton("Trailer", url=trailer_url)])

        await message.reply_photo(
            photo=image_url,
            caption=f"""
<b>Title:</b> <code>{title}</code>
<b>Year:</b> <code>{year}</code>
<b>Rating:</b> <code>{rating}</code>
<b>Episodes:</b> <code>{episodes}</code>
<b>Status:</b> <code>{status}</code>
<b>Score:</b> <code>{score}</code>
<b>Airing:</b> <code>{airing}</code>
<b>Duration:</b> <code>{duration}</code>
<b>Rank:</b> <code>{rank}</code>
<b>Description:</b> {description}
    """,
            reply_markup=InlineKeyboardMarkup(buttons) if buttons else None,
            parse_mode='HTML'
        )

        await query.answer()
        await query.delete_message()

__mod_name__ = "Anime"
__help__ = """
Search your favorite anime faster than any other bot.

*It's just simple:*
 • /anime <query>
 • Select the anime from the buttons

"""

application.add_handler(CommandHandler('anime', anime))
application.add_handler(CallbackQueryHandler(callback=anime_handler, pattern=r"^anime_\d+$"))
