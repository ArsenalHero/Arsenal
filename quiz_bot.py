import os
import re
import uvicorn
import pytz
from datetime import datetime, time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from telegram import Update, Poll
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- CONFIGURATION ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_NEW_TOKEN_HERE")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://arsenalxx.onrender.com")
TARGET_GROUP_ID = int(os.getenv("TARGET_GROUP_ID", "-1004211404152"))

# --- EXAM COUNTDOWN CONFIG ---
# Set these in your Render Environment Variables!
EXAM_DATE_STR = os.getenv("EXAM_DATE", "2027-05-23") # May 23, 2027
EXAM_NAME = os.getenv("EXAM_NAME", "UPSC CSP 2027") # UPSC CSP 2027

# --- COMMAND HANDLERS ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != "private": return
    
    welcome_text = (
        "👋 **Welcome to the ARSENAL QUIZMASTER BOT 🧿!**\n\n"
        "I can publish text quizzes AND image quizzes directly to the main group!\n\n"
        "**How to use me:**\n"
        "1. Send text with a ✅ next to the answer.\n"
        "2. Upload an image, and put the answer (`1`, `2`, `3`, or `4`) in the caption.\n\n"
        "👉 Tap /help to see the exact format."
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != "private": return
    
    help_text = (
        "📖 **How to format your questions:**\n\n"
        "**Method 1: Text**\n"
        "`1. Statement one.`\n"
        "`1 and 2 only`\n"
        "`1, 2 and 3 only✅`\n"
        "`Exp: Put your explanation here.`\n\n"
        "**Method 2: Image Shortcut**\n"
        "Upload a photo and set the caption to just the answer and explanation:\n"
        "`2`\n"
        "`Exp: Put your explanation here.`"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != "private": return
    
    status_text = (
        "🟢 **Bot Status:** Online & Active\n"
        f"🎯 **Publishing to Group:** `{TARGET_GROUP_ID}`\n"
        f"⏳ **Target Exam:** `{EXAM_NAME}` on `{EXAM_DATE_STR}`\n"
        "⚡️ **Server:** Render Webhooks"
    )
    await update.message.reply_text(status_text, parse_mode="Markdown")

# --- DAILY COUNTDOWN JOB ---
async def send_countdown(context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        # Calculate days left based on IST (Indian Standard Time)
        ist_tz = pytz.timezone('Asia/Kolkata')
        today = datetime.now(ist_tz).date()
        exam_date = datetime.strptime(EXAM_DATE_STR, "%Y-%m-%d").date()
        
        days_left = (exam_date - today).days

        if days_left > 0:
            msg = (
                "🌅 **Good Morning, Aspirants!**\n\n"
                f"⏳ **{days_left} Days Left** until the **{EXAM_NAME}**!\n\n"
                "Keep grinding! Every single question counts. 🎯📖"
            )
            await context.bot.send_message(chat_id=TARGET_GROUP_ID, text=msg, parse_mode="Markdown")
        elif days_left == 0:
            msg = f"🚨 **It's Exam Day!** Best of luck to everyone writing the {EXAM_NAME} today! Stay calm and crush it! 🎯"
            await context.bot.send_message(chat_id=TARGET_GROUP_ID, text=msg, parse_mode="Markdown")
    except Exception as e:
        print(f"Failed to send countdown message: {e}")

# --- PARSER FUNCTIONS (Paste your existing logic inside here) ---
def parse_shorthand_caption(text: str):
    # PASTE YOUR EXISTING IMAGE PARSER LOGIC HERE
    pass

def parse_upsc_question(text: str, has_photo: bool = False):
    # PASTE YOUR EXISTING TEXT PARSER LOGIC HERE
    pass

async def send_long_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str, parse_mode: str = "HTML", reply_to=None):
    # PASTE YOUR EXISTING LONG MESSAGE SENDER LOGIC HERE
    pass

async def create_upsc_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # PASTE YOUR EXISTING CREATE QUIZ LOGIC HERE
    pass

# --- FASTAPI WEBHOOK SERVER & SCHEDULER ---
ptb = Application.builder().updater(None).token(BOT_TOKEN).build()

# 1. Add Handlers
ptb.add_handler(CommandHandler("start", start_command, filters=filters.ChatType.PRIVATE))
ptb.add_handler(CommandHandler("help", help_command, filters=filters.ChatType.PRIVATE))
ptb.add_handler(CommandHandler("status", status_command, filters=filters.ChatType.PRIVATE))
ptb.add_handler(MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND & filters.ChatType.PRIVATE, create_upsc_quiz))

# 2. Schedule the Morning Countdown Message (6:06 AM IST)
ist_tz = pytz.timezone('Asia/Kolkata')
morning_time = time(hour=6, minute=6, tzinfo=ist_tz)  # Set to 6:06 AM IST
ptb.job_queue.run_daily(send_countdown, time=morning_time)

# 3. Lifespan config
@asynccontextmanager
async def lifespan(_: FastAPI):
    await ptb.bot.set_webhook(url=WEBHOOK_URL)
    async with ptb:
        # Starting PTB also starts the JobQueue scheduler automatically
        await ptb.start()
        yield
        await ptb.stop()

app = FastAPI(lifespan=lifespan)

@app.post("/")
async def process_update(request: Request):
    req = await request.json()
    update = Update.de_json(req, ptb.bot)
    await ptb.process_update(update)
    return Response(status_code=200)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
