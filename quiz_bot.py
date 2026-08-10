import re
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from telegram import Update, Poll
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# --- CONFIGURATION ---
BOT_TOKEN = "8929947153:AAF8JIXltVTY3AZA8WZJfmr2CZDSlzTareE"
WEBHOOK_URL = "https://arsenalxx.onrender.com"
# Your exact target group ID
TARGET_GROUP_ID = -4211404152


# --- UPSC SMART PARSER LOGIC ---
def parse_upsc_question(text: str):
    """
    Parses multi-line UPSC questions, extracting the question, options, correct answer, and explanation.
    """
    raw_lines = [line.strip() for line in text.split('\n') if line.strip()]
    if not raw_lines:
        return None

    explanation = ""
    content_lines = []
    
    exp_pattern = re.compile(r'^(explanation|exp|ans|answer|solution|notes?)[\s\:\-]', re.IGNORECASE)
    exp_index = -1
    
    for i, line in enumerate(raw_lines):
        if exp_pattern.match(line):
            exp_index = i
            break
            
    if exp_index != -1:
        content_lines = raw_lines[:exp_index]
        exp_lines = raw_lines[exp_index:]
        exp_lines[0] = exp_pattern.sub('', exp_lines[0]).strip()
        explanation = "\n".join(exp_lines).strip()
    else:
        content_lines = raw_lines

    correct_line_idx = -1
    for i, line in enumerate(content_lines):
        if '✅' in line:
            correct_line_idx = i
            break

    if correct_line_idx == -1:
        return None  

    opt_prefix_regex = re.compile(r'^\s*[\(\[]?([a-dA-D1-4])[\)\.\:\-]\s*')
    option_indices = [i for i, line in enumerate(content_lines) if opt_prefix_regex.match(line)]

    if option_indices:
        first_opt_idx = option_indices[0]
        last_opt_idx = option_indices[-1]
        
        if correct_line_idx > last_opt_idx:
            last_opt_idx = correct_line_idx

        question_lines = content_lines[:first_opt_idx]
        raw_options = content_lines[first_opt_idx:last_opt_idx + 1]
        
        if exp_index == -1 and last_opt_idx + 1 < len(content_lines):
            explanation = "\n".join(content_lines[last_opt_idx + 1:]).strip()
    else:
        start_opt = max(0, correct_line_idx - 3)
        end_opt = min(len(content_lines) - 1, correct_line_idx + 3)
        
        question_lines = content_lines[:start_opt]
        raw_options = content_lines[start_opt:end_opt + 1]
        
        if exp_index == -1 and end_opt + 1 < len(content_lines):
            explanation = "\n".join(content_lines[end_opt + 1:]).strip()

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

async def create_upsc_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    parsed = parse_upsc_question(text)
    source_chat_id = update.effective_chat.id

    if not parsed:
        await context.bot.send_message(
            chat_id=source_chat_id, 
            text="❌ Could not parse the question. Make sure you included the ✅ checkmark."
        )
        return

    question_text = parsed["question"]
    options = parsed["options"]
    correct_id = parsed["correct_option_id"]
    explanation = parsed["explanation"]

    try:
        # Handle Telegram 300-char question limit (Sends to Target Group)
        if len(question_text) > 300:
            await context.bot.send_message(
                chat_id=TARGET_GROUP_ID, 
                text=f"📌 **QUESTION:**\n\n{question_text}", 
                parse_mode="Markdown"
            )
            poll_question = "👇 Refer to the question above and select the correct option:"
        else:
            poll_question = question_text

        short_exp = explanation[:200] if explanation else ""

        # Send the Poll to Target Group
        await context.bot.send_poll(
            chat_id=TARGET_GROUP_ID,
            question=poll_question,
            options=options,
            type=Poll.QUIZ,
            correct_option_id=correct_id,
            explanation=short_exp,
            is_anonymous=False
        )

        # Send long detailed explanation to Target Group
        if len(explanation) > 200:
            await context.bot.send_message(
                chat_id=TARGET_GROUP_ID, 
                text=f"📖 **DETAILED EXPLANATION:**\n\n{explanation}",
                parse_mode="Markdown"
            )

        # Send success confirmation to you
        await context.bot.send_message(
            chat_id=source_chat_id, 
            text="✅ Quiz successfully generated and posted to the group!"
        )

    except Exception as e:
        await context.bot.send_message(
            chat_id=source_chat_id, 
            text=f"❌ Error creating UPSC quiz. Make sure the bot is an Admin in the target group. Error details: {e}"
        )


# --- FASTAPI WEBHOOK SERVER ---

ptb = Application.builder().updater(None).token(BOT_TOKEN).build()
ptb.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, create_upsc_quiz))

@asynccontextmanager
async def lifespan(_: FastAPI):
    # Register Webhook URL
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
