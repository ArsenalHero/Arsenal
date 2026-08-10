import re
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from telegram import Update, Poll
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- CONFIGURATION ---
BOT_TOKEN = "8929947153:AAF8JIXltVTY3AZA8WZJfmr2CZDSlzTareE"
WEBHOOK_URL = "https://arsenalxx.onrender.com"
TARGET_GROUP_ID = -1004211404152

# --- COMMAND HANDLERS ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Only respond to commands in private DMs
    if update.effective_chat.type != "private": return
    
    welcome_text = (
        "👋 **Welcome to the ARSENAL QUIZMASTER BOT 🧿!**\n\n"
        "I am the official quiz submission bot. Send me a question here in our private chat, and I will publish it to the main group!\n\n"
        "**How to use me:**\n"
        "1. Paste your question with options here.\n"
        "2. Mark the correct answer with a ✅.\n"
        "3. I will instantly format it and post it to the group!\n\n"
        "👉 Tap /help to see the exact format."
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != "private": return
    
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
    if update.effective_chat.type != "private": return
    
    status_text = (
        "🟢 **Bot Status:** Online & Active\n"
        f"🎯 **Publishing to Group:** `{TARGET_GROUP_ID}`\n"
        "⚡️ **Server:** Render Webhooks"
    )
    await update.message.reply_text(status_text, parse_mode="Markdown")

# --- UPSC SMART PARSER LOGIC ---
def parse_upsc_question(text: str):
    text = re.sub(r'(?m)^(\s*[\(\[]?[a-eA-E1-5][\)\]\.\:\-]+)\s*\n\s*(.*)', r'\1 \2', text)
    raw_lines = [line.strip() for line in text.split('\n') if line.strip()]
    if not raw_lines: return None

    correct_line_idx = -1
    for i, line in enumerate(raw_lines):
        if '✅' in line:
            correct_line_idx = i
            break
    if correct_line_idx == -1: return None  

    exp_pattern = re.compile(r'^(explanation|exp|ans|answer|solution|notes?)[\s\:\-]', re.IGNORECASE)
    exp_start_idx = -1
    for i in range(correct_line_idx + 1, len(raw_lines)):
        if exp_pattern.match(raw_lines[i]):
            exp_start_idx = i
            break

    opt_prefix_regex = re.compile(r'^\s*(?:[\(\[]?[a-eA-E][\)\]\.\:\-]+|[\(\[]?[1-5][\)\]\:\-]+)\s*')
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
    if not question_text or len(options) < 2 or correct_option_id == -1: return None

    return {
        "question": question_text,
        "options": options[:10],  
        "correct_option_id": correct_option_id,
        "explanation": explanation
    }

async def send_long_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str, parse_mode: str = "HTML"):
    chunk_size = 4000
    for i in range(0, len(text), chunk_size):
        await context.bot.send_message(chat_id=chat_id, text=text[i:i + chunk_size], parse_mode=parse_mode)

async def create_upsc_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # 1. STOP IF NOT A PRIVATE DM
    if update.effective_chat.type != "private":
        return

    text = update.message.text
    parsed = parse_upsc_question(text)
    user_dm_id = update.effective_chat.id

    author_name = update.effective_user.first_name
    if update.effective_user.last_name:
        author_name += f" {update.effective_user.last_name}"

    if not parsed:
        await context.bot.send_message(chat_id=user_dm_id, text="❌ **Could not parse the question.**\nDid you forget the ✅?")
        return

    question_text = parsed["question"]
    options = parsed["options"]
    correct_id = parsed["correct_option_id"]
    explanation = parsed["explanation"]

    try:
        safe_question = question_text.replace('<', '&lt;').replace('>', '&gt;')
        safe_author = author_name.replace('<', '&lt;').replace('>', '&gt;')
        author_append = f"\n\n👤 <i>Quiz by: {safe_author}</i>"
        raw_length = len(question_text) + len(f"\n\n👤 Quiz by: {author_name}")

        if raw_length > 300:
            long_question_text = f"📌 <b>QUESTION:</b>\n\n{safe_question}"
            # Posts long question to the Target Group
            await send_long_message(context, TARGET_GROUP_ID, long_question_text, "HTML")
            poll_question = f"👇 Refer to the question above:{author_append}"
        else:
            poll_question = f"{safe_question}{author_append}"

        short_exp = explanation[:200] if explanation else ""

        # 2. POST THE QUIZ TO THE PUBLIC GROUP
        await context.bot.send_poll(
            chat_id=TARGET_GROUP_ID,
            question=poll_question,
            options=options,
            type=Poll.QUIZ,
            correct_option_id=correct_id,
            explanation=short_exp,
            is_anonymous=False,
            question_parse_mode="HTML"
        )
        
        # 3. SEND SUCCESS MESSAGE TO THE USER'S DM
        await context.bot.send_message(chat_id=user_dm_id, text="✅ **Success!** Your quiz was published to the main group.", parse_mode="Markdown")

    except Exception as e:
        await context.bot.send_message(chat_id=user_dm_id, text=f"❌ **Error posting to group.**\nError details: `{e}`", parse_mode="Markdown")

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
