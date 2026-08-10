import re
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from telegram import Update, Poll
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- CONFIGURATION ---
BOT_TOKEN = "8929947153:AAF8JIXltVTY3AZA8WZJfmr2CZDSlzTareE"
WEBHOOK_URL = "https://arsenalxx.onrender.com"

# --- COMMAND HANDLERS ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    welcome_text = (
        "👋 **Welcome to the ARSENAL QUIZMASTER BOT 🧿!**\n\n"
        "I can instantly convert raw text into beautiful Telegram Polls.\n\n"
        "**How to use me:**\n"
        "1. Add me to ANY group and make me an Admin (so I can delete messages).\n"
        "2. Paste your question with options and mark the answer with a ✅.\n"
        "3. I will delete your text and replace it with a native Quiz!\n\n"
        "👉 Tap /help to see the exact format and examples."
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "📖 **How to format your questions:**\n\n"
        "Simply send a message in this format:\n\n"
        "`Consider the following statements:`\n"
        "`1. First statement here.`\n"
        "`2. Second statement here.`\n"
        "`(a) 1 only`\n"
        "`(b) 2 only✅`\n"
        "`(c) Both 1 and 2`\n"
        "`(d) Neither 1 nor 2`\n"
        "`Explanation: Put your explanation here (max 200 chars).`\n\n"
        "**Golden Rules:**\n"
        "1️⃣ Always put a ✅ next to the correct option.\n"
        "2️⃣ I can understand options like a., (a), 1), A-, etc.\n"
        "3️⃣ Explanations are strictly kept inside the poll's pop-up box (200-char limit)."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    status_text = (
        "🟢 **Bot Status:** Online & Active\n"
        "🌐 **Mode:** Generalized (Works in any group)\n"
        "⚡️ **Server:** Render Webhooks"
    )
    await update.message.reply_text(status_text, parse_mode="Markdown")

# --- UPSC SMART PARSER LOGIC ---
def parse_upsc_question(text: str):
    text = re.sub(r'(?m)^(\s*[\(\[]?[a-eA-E1-5][\)\]\.\:\-]+)\s*\n\s*(.*)', r'\1 \2', text)

    raw_lines = [line.strip() for line in text.split('\n') if line.strip()]
    if not raw_lines:
        return None

    correct_line_idx = -1
    for i, line in enumerate(raw_lines):
        if '✅' in line:
            correct_line_idx = i
            break

    if correct_line_idx == -1:
        return None  

    exp_pattern = re.compile(r'^(explanation|exp|ans|answer|solution|notes?)[\s\:\-]', re.IGNORECASE)
    exp_start_idx = -1
    for i in range(correct_line_idx + 1, len(raw_lines)):
        if exp_pattern.match(raw_lines[i]):
            exp_start_idx = i
            break

    opt_prefix_regex = re.compile(r'^\s*[\(\[]?([a-eA-E1-5])[\)\]\.\:\-]+\s*')
    option_indices = [i for i, line in enumerate(raw_lines) if opt_prefix_regex.match(line)]
    
    valid_opts = [i for i in option_indices if abs(i - correct_line_idx) <= 6]
    
    if valid_opts:
        first_opt_idx = min(valid_opts[0], correct_line_idx)
        last_opt_idx = max(valid_opts[-1], correct_line_idx)
        
        if exp_start_idx == -1 and last_opt_idx + 1 < len(raw_lines):
            exp_start_idx = last_opt_idx + 1
    else:
        first_opt_idx = max(0, correct_line_idx - 3)
        if first_opt_idx == 0 and correct_line_idx > 0:
            first_opt_idx = 1
            
        if exp_start_idx != -1:
            last_opt_idx = exp_start_idx - 1
        else:
            last_opt_idx = min(len(raw_lines) - 1, correct_line_idx + max(0, 3 - (correct_line_idx - first_opt_idx)))
            if last_opt_idx + 1 < len(raw_lines):
                exp_start_idx = last_opt_idx + 1

    question_lines = raw_lines[:first_opt_idx]
    raw_options = raw_lines[first_opt_idx:(last_opt_idx + 1) if exp_start_idx == -1 else exp_start_idx]

    explanation = ""
    if exp_start_idx != -1 and exp_start_idx < len(raw_lines):
        exp_lines = raw_lines[exp_start_idx:]
        exp_lines[0] = exp_pattern.sub('', exp_lines[0]).strip()
        explanation = "\n".join(exp_lines).strip()

    options = []
    correct_option_id = -1

    for i, opt_line in enumerate(raw_options):
        if '✅' in opt_line:
            correct_option_id = i
        clean_opt = opt_line.replace('✅', '').strip()
        options.append(clean_opt[:100])  

    question_text = "\n".join(question_lines).strip()

    if not question_text or len(options) < 2 or correct_option_id == -1:
        return None

    return {
        "question": question_text,
        "options": options[:10],  
        "correct_option_id": correct_option_id,
        "explanation": explanation
    }

async def send_long_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str, parse_mode: str = "HTML"):
    chunk_size = 4000
    for i in range(0, len(text), chunk_size):
        await context.bot.send_message(
            chat_id=chat_id,
            text=text[i:i + chunk_size],
            parse_mode=parse_mode
        )

async def create_upsc_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    parsed = parse_upsc_question(text)
    
    # The chat where the message was sent (can be any group, channel, or DM)
    current_chat_id = update.effective_chat.id

    author_name = update.effective_user.first_name
    if update.effective_user.last_name:
        author_name += f" {update.effective_user.last_name}"

    if not parsed:
        # Ignore unparseable messages entirely to prevent spamming normal group chats
        return

    question_text = parsed["question"]
    options = parsed["options"]
    correct_id = parsed["correct_option_id"]
    explanation = parsed["explanation"]

    try:
        # Step 1: Try to delete the user's raw message so the answer isn't spoiled
        try:
            await update.message.delete()
        except Exception:
            pass # If the bot lacks admin delete permissions, it just ignores and continues

        safe_question = question_text.replace('<', '&lt;').replace('>', '&gt;')
        safe_author = author_name.replace('<', '&lt;').replace('>', '&gt;')
        author_append = f"\n\n👤 <i>Quiz by: {safe_author}</i>"
        
        raw_length = len(question_text) + len(f"\n\n👤 Quiz by: {author_name}")

        # Step 2: Handle long questions
        if raw_length > 300:
            long_question_text = f"📌 <b>QUESTION:</b>\n\n{safe_question}"
            await send_long_message(context, current_chat_id, long_question_text, "HTML")
            poll_question = f"👇 Refer to the question above:{author_append}"
        else:
            poll_question = f"{safe_question}{author_append}"

        short_exp = explanation[:200] if explanation else ""

        # Step 3: Send the Poll into the current chat
        await context.bot.send_poll(
            chat_id=current_chat_id,
            question=poll_question,
            options=options,
            type=Poll.QUIZ,
            correct_option_id=correct_id,
            explanation=short_exp,
            is_anonymous=False,
            question_parse_mode="HTML"
        )

    except Exception as e:
        print(f"Error creating quiz in chat {current_chat_id}: {e}")

# --- FASTAPI WEBHOOK SERVER ---

ptb = Application.builder().updater(None).token(BOT_TOKEN).build()

ptb.add_handler(CommandHandler("start", start_command))
ptb.add_handler(CommandHandler("help", help_command))
ptb.add_handler(CommandHandler("status", status_command))
ptb.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, create_upsc_quiz))

@asynccontextmanager
async def lifespan(_: FastAPI):
    await ptb.bot.set_webhook(url=WEBHOOK_URL)
    async with ptb:
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
