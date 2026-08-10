from contextlib import asynccontextmanager
from http import HTTPStatus
from fastapi import FastAPI, Request, Response
from telegram import Update, Poll
from telegram.ext import Application, MessageHandler, filters, ContextTypes
import uvicorn

# --- CONFIGURATION ---
# 1. Put your actual Bot Token here
BOT_TOKEN = "8929947153:AAF8JIXltVTY3AZA8WZJfmr2CZDSlzTareE" 
# 2. Put the public URL that your free hosting provider gives you here
WEBHOOK_URL = "https://your-app-name.onrender.com" 


# --- YOUR BOT LOGIC (Unchanged) ---
async def create_quiz_from_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    if len(lines) < 4:
        return

    question = lines[0]
    explanation = lines[-1]
    raw_options = lines[1:-1] 

    options = []
    correct_option_id = -1

    for i, option in enumerate(raw_options):
        if '✅' in option:
            correct_option_id = i
            options.append(option.replace('✅', '').strip())
        else:
            options.append(option)

    if correct_option_id == -1 or len(options) < 2 or len(options) > 10:
        return

    try:
        await context.bot.send_poll(
            chat_id=update.effective_chat.id,
            question=question,
            options=options,
            type=Poll.QUIZ,
            correct_option_id=correct_option_id,
            explanation=explanation,
            is_anonymous=False
        )
        await update.message.delete()
    except Exception as e:
        print(f"Error: {e}")

# --- WEBHOOK SERVER SETUP ---

# Initialize the bot but DISABLE the default updater (since we aren't polling anymore)
ptb = Application.builder().updater(None).token(BOT_TOKEN).build()
ptb.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, create_quiz_from_text))

# This tells Telegram where our "doorbell" is when the server starts
@asynccontextmanager
async def lifespan(_: FastAPI):
    # Register the webhook with Telegram
    await ptb.bot.setWebhook(url=WEBHOOK_URL)
    
    # Start the bot application
    async with ptb:
        await ptb.start()
        yield
        await ptb.stop()

# Initialize the FastAPI web server
app = FastAPI(lifespan=lifespan)

# This is the exact door/endpoint Telegram will knock on when someone sends a message
@app.post("/")
async def process_update(request: Request):
    req = await request.json()
    
    # Convert Telegram's JSON data into an Update object and feed it to the bot
    update = Update.de_json(req, ptb.bot)
    await ptb.process_update(update)
    
    # Tell Telegram we received it successfully
    return Response(status_code=HTTPStatus.OK)

if __name__ == "__main__":
    # Run the web server on port 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)
