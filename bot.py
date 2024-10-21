from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, CallbackContext
import requests
import pymongo
import os
from pymongo import MongoClient

# Environment variables
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
OMDB_API_KEY = os.getenv('OMDB_API_KEY')
MONGO_URI = os.getenv('MONGO_URI')

PORT = int(os.environ.get("PORT", 8080))

client = MongoClient(MONGO_URI)
db = client['telegram_bot']
settings_collection = db['settings']

# Admins list: Add your admin IDs here
ADMIN_IDS = [6018060368, 6025969005, 6237722078]  # Add more admin IDs if necessary

# Default caption format in HTML
DEFAULT_CAPTION = "<b>🎬 Title : </b> {movie_name}<br><br><b>🗓 Release Date : {release_date}</b><br><b>🌟 IMDB Rating : {rating}<br>📢 Audio : Multi <br>🎭 Genres : {genres}<br>◀️ Quality : HD</b><br><br><b>🚨❓How To Download❓🚨</b><br><br><b>Now you can search this file on our movie request group or directly search in bot PM.<br>Tap on File Name, Copy & Search..</b><br><br><b>अब आप इस फ़ाइल को हमारे मूवी सर्च ग्रुप पर सर्च कर सकते हैं या सीधे बॉट पर सर्च सकते हैं।<br>फ़ाइल का नाम कॉपी करने के लीये फ़ाइल के नाम पर टैप करें, और सर्च करे ||</b>"

# Helper function to fetch movie details from OMDb API
def fetch_movie_details(movie_name, year=None):
    url = f'http://www.omdbapi.com/?t={movie_name}&apikey={OMDB_API_KEY}'
    if year:
        url += f'&y={year}'
    response = requests.get(url)
    return response.json()

# Helper function to get caption format from MongoDB or use default
async def get_caption():
    settings = settings_collection.find_one({"_id": "caption"})
    return settings['caption'] if settings else DEFAULT_CAPTION

# Helper function to check if posters are disabled
async def are_posters_disabled():
    settings = settings_collection.find_one({"_id": "posters"})
    return settings.get('disabled', False) if settings else False

# Helper function to get forward channels
async def get_forward_channels():
    settings = settings_collection.find_one({"_id": "forward_channels"})
    return settings.get('channels', []) if settings else []

# Helper function to check if user is an admin
def check_admin(user_id):
    return user_id in ADMIN_IDS

# Command: start
async def start(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if not check_admin(user_id):
        await update.message.reply_text("You are not authorized to use this command.\n Contact developer to use this bot\n\n 🅓🅔🅥🅔🅛🅞🅟🅔🅡\n @Assistant_24_7_bot")
        return
        
    await update.message.reply_text('Welcome! Use the commands below to interact with the bot.\n'
                                    '/get_movie <movie name> - Fetch movie details and create post\n'
                                    '/setcaption <caption_format> - Set caption format for posts\n'
                                    '/setposter - Set poster as the thumbnail\n'
                                    '/offposter - Disable poster as thumbnail\n'
                                    '/replace <old_text> to <new_text> - Replace text in the replied post\n'
                                    '/addforward <channel_id_1> <channel_id_2> ... - Add channels to forward posts\n'
                                    '/forward - Forward the last edited post to all added channels')

# Command: set custom caption format
async def set_caption(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if not check_admin(user_id):
        await update.message.reply_text("You are not authorized to use this command.\n Contact developer to use this bot\n\n 🅓🅔🅥🅔🅛🅞🅟🅔🅡\n @Assistant_24_7_bot")
        return

    caption = " ".join(context.args)
    if caption:
        settings_collection.update_one({"_id": "caption"}, {"$set": {"caption": caption}}, upsert=True)
        await update.message.reply_text(f'Post caption set to: {caption}')
    else:
        await update.message.reply_text('Usage: /setcaption <caption_format>')

# Command: get movie details and handle optional year
async def get_movie(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if not check_admin(user_id):
        await update.message.reply_text("You are not authorized to use this command.\n Contact developer to use this bot\n\n 🅓🅔🅥🅔🅛🅞🅟🅔🅡\n @Assistant_24_7_bot")
        return
        
    query = " ".join(context.args).strip()
    if "," in query:
        movie_name, year = [x.strip() for x in query.split(",", 1)]
    else:
        movie_name, year = query, None

    if year:
        movie = fetch_movie_details(movie_name, year)
        if movie['Response'] == 'True':
            await send_movie_post(update, movie)
        else:
            await update.message.reply_text(f"No movie found for '{movie_name}' in {year}.")
    else:
        search_response = requests.get(f'http://www.omdbapi.com/?s={movie_name}&apikey={OMDB_API_KEY}')
        search_results = search_response.json()

        if search_results['Response'] == 'True':
            keyboard = []
            for result in search_results['Search'][:10]:  # Limit to 10 results
                button_text = f"{result['Title']} ({result.get('Year', 'Unknown')})"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=result['imdbID'])])

            if len(search_results['Search']) > 10:
                keyboard.append([InlineKeyboardButton("Next", callback_data="next")])  # Next button

            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text('Select a movie:', reply_markup=reply_markup)
        else:
            await update.message.reply_text(f"No movies found for '{movie_name}'.")

# Function to send movie post based on selected details
async def send_movie_post(update, movie):
        caption_format = await get_caption()
        thumbnails_disabled = await are_posters_disabled()

        thumbnail = movie.get('Poster', None) if not thumbnails_disabled else None

        # Caption formatted for Markdown
        caption = caption_format.format(
            movie_name=f"`{movie.get('Title', 'Unknown')} {movie.get('Year', 'Unknown')}`",
            release_date=movie.get('Year', 'Unknown'),
            rating=movie.get('imdbRating', 'N/A'),
            language=movie.get('Language', 'Unknown'),
            genres=movie.get('Genre', 'Unknown')
        )

        # Markdown formatting
        caption = caption.replace('<b>', '*').replace('</b>', '*')
        caption = caption.replace('<i>', '_').replace('</i>', '_')
        caption = caption.replace('<br>', '\n')

        # Create buttons
        buttons = [
            [InlineKeyboardButton("Search In Group",
                                  url="https://t.me/movie_request_group_moviesmarket")],
            [InlineKeyboardButton("Search In Bot", url="https://t.me/LazyAngelbot")]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)

        # Send message with or without thumbnail
        if thumbnail:
            await update.message.reply_photo(photo=thumbnail, caption=caption,
                                             parse_mode='Markdown',
                                             reply_markup=reply_markup)
        else:
            await update.message.reply_text(text=caption, parse_mode='Markdown',
                                            reply_markup=reply_markup)

# CallbackQuery: handle movie selection from button list
async def movie_selection(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    movie_id = query.data

    movie = requests.get(f'http://www.omdbapi.com/?i={movie_id}&apikey={OMDB_API_KEY}').json()

    if movie['Response'] == 'True':
        await send_movie_post(query, movie)

    await query.answer()

# Command: set poster as thumbnail
async def set_poster(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if not check_admin(user_id):
        await update.message.reply_text("You are not authorized to use this command.\n Contact developer to use this bot\n\n 🅓🅔🅥🅔🅛🅞🅟🅔🅡\n @Assistant_24_7_bot")
        return

    settings_collection.update_one({"_id": "posters"}, {"$set": {"disabled": False}}, upsert=True)
    await update.message.reply_text('Poster will be used as thumbnail.')

# Command: off poster from thumbnail
async def off_poster(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if not check_admin(user_id):
        await update.message.reply_text("You are not authorized to use this command.\n Contact developer to use this bot\n\n 🅓🅔🅥🅔🅛🅞🅟🅔🅡\n @Assistant_24_7_bot")
        return

    settings_collection.update_one({"_id": "posters"}, {"$set": {"disabled": True}}, upsert=True)
    await update.message.reply_text('Poster will not be used as thumbnail until /setposter is called again.')

# Command: replace text in a post with simplified logic
async def replace_text(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if not check_admin(user_id):
        await update.message.reply_text("You are not authorized to use this command.\n Contact developer to use this bot\n\n 🅓🅔🅥🅔🅛🅞🅟🅔🅡\n @Assistant_24_7_bot")
        return

    if update.message.reply_to_message:
        reply_message = update.message.reply_to_message
        text = reply_message.text or reply_message.caption
        if not text:
            await update.message.reply_text("No text to replace in the replied post.")
            return

        if len(context.args) < 3 or "to" not in context.args:
            await update.message.reply_text("Usage: /replace <old_text> to <new_text>\n"
                                            "Example: /replace hello sir to Nice To Meet You sir\n"
                                            "This will replace 'hello sir' with 'Nice To Meet You sir' in the replied post.")
            return

        # Splitting the command input
        to_index = context.args.index("to")
        old_text = " ".join(context.args[:to_index])
        new_text = " ".join(context.args[to_index + 1:])

        new_message_text = text.replace(old_text, new_text)

        if reply_message.text:
            await update.message.reply_text(new_message_text)
        elif reply_message.caption:
            await update.message.reply_photo(photo=reply_message.photo[-1].file_id, caption=new_message_text)
    else:
        await update.message.reply_text("Please reply to a message to replace text.")

# Add Forward Channels and replace existing ones
async def add_forward(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if not check_admin(user_id):
        await update.message.reply_text("You are not authorized to use this command.\n Contact developer to use this bot\n\n 🅓🅔🅥🅔🅛🅞🅟🅔🅡\n @Assistant_24_7_bot")
        return
        
    channel_ids = context.args
    if not channel_ids:
        await update.message.reply_text("Usage: /addforward <channel_id_1> <channel_id_2> ...")
        return

    # Replace existing channel IDs with new ones
    settings_collection.update_one({"_id": "forward_channels"}, {"$set": {"channels": channel_ids}}, upsert=True)

    await update.message.reply_text(f'Forward channels updated: {", ".join(channel_ids)}')

# Command: forward last edited post to all channels
async def forward_post(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if not check_admin(user_id):
        await update.message.reply_text("You are not authorized to use this command.\n Contact developer to use this bot\n\n 🅓🅔🅥🅔🅛🅞🅟🅔🅡\n @Assistant_24_7_bot")
        return
        
    forward_channels = await get_forward_channels()
    if not forward_channels:
        await update.message.reply_text("No channels set for forwarding. Use /addforward to add channels.")
        return

    if update.message.reply_to_message:
        reply_message = update.message.reply_to_message

        # Forward the original message to each channel
        for channel_id in forward_channels:
            try:
                await context.bot.forward_message(chat_id=channel_id, from_chat_id=reply_message.chat.id, message_id=reply_message.message_id)
            except Exception as e:
                await update.message.reply_text(f"Error forwarding to channel {channel_id}: {str(e)}")

        await update.message.reply_text(f"Post forwarded to: {', '.join(forward_channels)}")
    else:
        await update.message.reply_text("Please reply to a message to forward.")



# Create Application instance and add handlers
def main() -> None:
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("get_movie", get_movie))
    application.add_handler(CommandHandler("setcaption", set_caption))
    application.add_handler(CommandHandler("setposter", set_poster))
    application.add_handler(CommandHandler("offposter", off_poster))
    application.add_handler(CommandHandler("replace", replace_text))
    application.add_handler(CommandHandler("addforward", add_forward))
    application.add_handler(CommandHandler("forward", forward_post))

    # Callback query handler for movie selection
    application.add_handler(CallbackQueryHandler(movie_selection))

    # Start the bot
    # Change this to use webhooks for services like Koyeb/Replit:
    application.run_webhook(
        listen="0.0.0.0",  # Listen on all available network interfaces
        port=PORT,         # Port 8080 or any port defined in the environment
        url_path=TELEGRAM_BOT_TOKEN,  # The token as the URL path for the webhook
        webhook_url=f"https://accurate-cordula-imdb07-87daeb39.koyeb.app/{TELEGRAM_BOT_TOKEN}"  # Replace with your actual server URL
    )

if __name__ == '__main__':
    main()
