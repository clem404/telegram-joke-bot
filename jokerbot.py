import requests
import time
from collections import defaultdict
from gtts import gTTS
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
import datetime

BOT_TOKEN = "7611532391:AAFIf9PHy4WsuFgiLQ4jW0hP4a22vadZVbk"

# In-memory feedback store
user_feedback = defaultdict(lambda: {"likes": 0, "dislikes": 0})
subscribers = set()


# Get a random joke from the API
def get_random_joke(last_joke_id=None):
    try:
        for _ in range(3):  # Try a few times to avoid duplicates
            response = requests.get(
                "https://official-joke-api.appspot.com/jokes/random"
            )
            if response.status_code == 200:
                joke = response.json()
                if joke["id"] != last_joke_id:
                    return f"{joke['setup']}\n{joke['punchline']}", joke["id"]
        return "Couldn't find a new joke right now.", None
    except Exception as e:
        with open("errors.log", "a") as log:
            log.write(f"[Joke Fetch Error] {e}\n")
        return "Something went wrong while fetching the joke.", None


# Log user feedback
def log_feedback(user_id, joke_text, reaction):
    with open("ratings.txt", "a", encoding="utf-8") as f:
        f.write(f"{user_id} | {joke_text.replace(chr(10), ' ')} | {reaction}\n")


# Reusable keyboard with 3 buttons
def get_rating_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("👍", callback_data="like"),
                InlineKeyboardButton("👎", callback_data="dislike"),
            ],
            [InlineKeyboardButton("😂 Another Joke", callback_data="new_joke")],
        ]
    )


# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hi! Send /joke to get a random joke.")


# /help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Use /joke to get a random joke. You can rate jokes using the buttons!"
    )


# /about command
async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "I'm a joke bot 🤖 that tells random jokes!\n\nMade with ❤️ by Clem\nGitHub: github.com/clem404/"
    )


# /joke command
async def joke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = time.time()
    last_used = context.user_data.get("last_used", 0)
    if now - last_used < 2:
        await update.message.reply_text("⏳ Wait a moment before asking again!")
        return
    context.user_data["last_used"] = now

    last_joke_id = context.user_data.get("last_joke_id")
    text, joke_id = get_random_joke(last_joke_id)
    context.user_data["last_joke_id"] = joke_id
    await update.message.reply_text(text, reply_markup=get_rating_keyboard())


# /voicejoke command
async def voicejoke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text, _ = get_random_joke()
    tts = gTTS(text)
    tts.save("joke.mp3")
    await update.message.reply_voice(voice=open("joke.mp3", "rb"))


# /stats command
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    likes = user_feedback[user_id]["likes"]
    dislikes = user_feedback[user_id]["dislikes"]
    await update.message.reply_text(
        f"You've liked {likes} joke(s) and disliked {dislikes} joke(s)."
    )


# /daily command
async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    subscribers.add(user_id)
    await update.message.reply_text("✅ You're now subscribed to daily jokes!")


# /stop command
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    subscribers.discard(user_id)
    await update.message.reply_text("❌ You’ve unsubscribed from daily jokes.")


# Send joke of the day
async def send_daily_jokes(context: ContextTypes.DEFAULT_TYPE):
    for user_id in subscribers:
        text, _ = get_random_joke()
        await context.bot.send_message(
            chat_id=user_id, text=f"🗞️ Joke of the Day:\n\n{text}"
        )


# Handle button presses
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "new_joke":
        now = time.time()
        last_used = context.user_data.get("last_used", 0)
        if now - last_used < 3:
            await query.message.reply_text("⏳ Wait a moment before asking again!")
            return
        context.user_data["last_used"] = now

        last_joke_id = context.user_data.get("last_joke_id")
        text, joke_id = get_random_joke(last_joke_id)
        context.user_data["last_joke_id"] = joke_id
        await query.message.reply_text(text, reply_markup=get_rating_keyboard())

    elif query.data == "like":
        user_feedback[user_id]["likes"] += 1
        log_feedback(user_id, query.message.text, "like")
        await query.message.reply_text("Thanks for the 👍!")

        # Mini reaction stats
        joke_key = query.message.text
        context.chat_data.setdefault("joke_likes", {})
        context.chat_data["joke_likes"][joke_key] = (
            context.chat_data["joke_likes"].get(joke_key, 0) + 1
        )
        if context.chat_data["joke_likes"][joke_key] == 5:
            await query.message.reply_text("🔥 This joke got 5 likes!")

    elif query.data == "dislike":
        user_feedback[user_id]["dislikes"] += 1
        log_feedback(user_id, query.message.text, "dislike")
        await query.message.reply_text("Thanks for the feedback! 👎")


# Main bot runner
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("about", about))
    app.add_handler(CommandHandler("joke", joke))
    app.add_handler(CommandHandler("voicejoke", voicejoke))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("daily", daily))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CallbackQueryHandler(handle_buttons))

    app.job_queue.run_daily(send_daily_jokes, time=datetime.time(hour=9, minute=0))

    print("Bot is running...")
    app.run_polling()
