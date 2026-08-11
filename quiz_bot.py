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
    if update.effective_chat.type != "private": return
    
    welcome_text = (
        "👋 **Welcome to the ARSENAL QUIZMASTER BOT 🧿!**\n\n"
        "I can publish text quizzes AND image quizzes directly to the main group!\n\n"
        "**How to use me:**\n"
        "1. Send text with a ✅ next to the answer (even without a, b, c, d prefixes!).\n"
        "2. Upload an image, and put the answer (`1`, `2`, `3`, or `4`) in the caption.\n\n"
        "👉 Tap /help to see the exact format."
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != "private": return
    
    help_text = (
        "📖 **How to format your questions:**\n\n"
        "**Method 1: Text (With or Without a,b,c,d)**\n"
        "`1. Statement one.`\n"
        "`2. Statement two.`\n"
        "`1`\n"
        "`2✅`\n"
        "`Both 1 and 2`\n"
        "`None`\n"
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
        "🧠 **Features:** \"Exp:\" Un-flattener & Strict Cleaner Enabled\n"
        "⚡️ **Server:** Render Webhooks"
    )
    await update.message.reply_text(status_text, parse_mode="Markdown")

# --- IMAGE SHORTHAND PARSER ---
def parse_shorthand_caption(text: str):
    match = re.match(r'^\s*(?:ans(?:wer)?\s*[:\-\.]?\s*)?([1-4a-dA-D])\s*(?:$|\n(.*))', text, re.IGNORECASE | re.DOTALL)
    
    if match:
        ans = match.group(1).lower()
        remainder = match.group(2) or ""
        
        if ans in ['1', 'a']: correct_id = 0
        elif ans in ['2', 'b']: correct_id = 1
        elif ans in ['3', 'c']: correct_id = 2
        elif ans in ['4', 'd']: correct_id = 3
        else: return None
        
        explanation = remainder.strip()
        explanation = re.sub(r'^(?:exp(?:lanation)?|notes?)\s*[:\-\.]?\s*', '', explanation, flags=re.IGNORECASE).strip()
        
        return {
            "question": "👇 Please refer to the image above to answer the question.",
            "options": ["Option 1", "Option 2", "Option 3", "Option 4"],
            "correct_option_id": correct_id,
            "explanation": explanation
        }
    return None

# --- UPSC FULL TEXT PARSER LOGIC ---
def parse_upsc_question(text: str, has_photo: bool = False):
    
    # --- 🛠️ STRICT PDF AUTO-CLEANER 🛠️ ---
    
    # 1. Un-flattens "Exp:" or "Explanation:" if it gets stuck to the end of an option
    text = re.sub(r'(?<!\n)\s*\b(Explanation|Exp|Ans|Answer|Solution|Notes?)[\:\-]', r'\n\1:', text, flags=re.IGNORECASE)
    
    # 2. Sequence Un-flattener specifically for "1 2 Both None" formats pasted on one line
    text = re.sub(
        r'(?<![A-Za-z0-9])1(✅)?\s+2(✅)?\s+(Both(?: 1 and 2)?)(✅)?\s+(None|Neither(?: 1 nor 2)?)(✅)?(?=[\s\n]|$|\bExp)', 
        r'\n1\1\n2\2\n\3\4\n\5\6', 
        text, 
        flags=re.IGNORECASE
    )
    
    text = re.sub(r'[ \t]+(\(?\d{1,2}[\)\.]\s+)', r'\n\1', text)
    text = re.sub(r'[ \t]+(\(?(?:[a-eA-E])[\)\.]\s+)', r'\n\1', text)
    text = re.sub(r'[ \t]+(Only\s+[1-4]\b|Only\s+(?:one|two|three|four)\s+pair|Both\s+1|Neither\s+1|None\s+of|All\s+(?:of|three|four))', r'\n\1', text, flags=re.IGNORECASE)
    text = re.sub(r'[ \t]+(Select the correct|Which of the|Choose the correct|How many of the)', r'\n\1', text, flags=re.IGNORECASE)
    text = re.sub(r'(?m)^(\s*[\(\[]?[a-eA-E][\)\]\.\:\-]+\s*)(.*)', r'\1 \2', text)

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

    # --- 🧠 ADVANCED EXAM VOCABULARY REGEX 🧠 ---
    opt_prefix_regex = re.compile(
        r'^\s*(?:'
        r'[\(\[]?[a-eA-E][\)\]\.\:\-]+\s*|'            
        r'^[1-4]\s*(?:✅)?$|'                             
        r'Only\s+[1-4]|'                               
        r'Only\s+(?:one|two|three|four)\s+pair|'       
        r'Both\b|'                                     
        r'Neither\b|'                                  
        r'Either\b|'                                   
        r'None\b|'                                     
        r'All\b|'                                      
        r'Statement\s+(?:I|II|1|2)\s+is|'              
        r'(?:[1-4]\s*,\s*)*[1-4]\s+and\s+[1-4]|'       
        r'[1-4]\s+(?:only|and)'                       
        r')', re.IGNORECASE
    )
    
    option_indices = [i for i, line in enumerate(raw_lines) if opt_prefix_regex.match(line)]
    valid_opts = [i for i in option_indices if abs(i - correct_line_idx) <= 6]
    
    if not valid_opts:
        statement_end_idx = 0
        for i, line in enumerate(raw_lines):
            if re.match(r'^\s*\d{1,2}[\.\)]', line):
                statement_end_idx = i
        first_opt_idx = statement_end_idx + 1 if statement_end_idx > 0 else max(0, correct_line_idx - 3)
        last_opt_idx = exp_start_idx - 1 if exp_start_idx != -1 else len(raw_lines) - 1
        
        if last_opt_idx - first_opt_idx > 5:
            first_opt_idx = max(0, correct_line_idx - 3)
            last_opt_idx = min(len(raw_lines) - 1, correct_line_idx + 2)
    else:
        first_opt_idx = min(valid_opts[0], correct_line_idx)
        last_opt_idx = max(valid_opts[-1], correct_line_idx)
        if exp_start_idx == -1 and last_opt_idx + 1 < len(raw_lines):
            exp_start_idx = last_opt_idx + 1

    if exp_start_idx == -1:
        for i in range(last_opt_idx + 1, len(raw_lines)):
            if exp_pattern.match(raw_lines[i]):
                exp_start_idx = i
                break

    question_lines = raw_lines[:first_opt_idx]
    
    if question_lines:
        last_line = question_lines[-1]
        cleaned_last_line = re.sub(r'(?:(?<=[.!?])(?:\s+[1-4a-dA-D]){1,4}|(?:\s+[1-4a-dA-D]){2,4})\s*$', '', last_line)
        if cleaned_last_line:
            question_lines[-1] = cleaned_last_line.strip()
            
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
    
    if not question_text and has_photo:
        question_text = "👇 Please refer to the image above to answer the question."

    if not question_text or len(options) < 2 or correct_option_id == -1: return None

    return {
        "question": question_text,
        "options": options[:10],  
        "correct_option_id": correct_option_id,
        "explanation": explanation
    }

async def send_long_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str, parse_mode: str = "HTML", reply_to=None):
    chunk_size = 4000
    for i in range(0, len(text), chunk_size):
        await context.bot.send_message(
            chat_id=chat_id, 
            text=text[i:i + chunk_size], 
            parse_mode=parse_mode,
            reply_to_message_id=reply_to
        )

async def create_upsc_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type != "private":
        return

    if update.message.photo:
        raw_text = update.message.caption
        photo_id = update.message.photo[-1].file_id
    else:
        raw_text = update.message.text
        photo_id = None

    user_dm_id = update.effective_chat.id

    if not raw_text:
        await context.bot.send_message(chat_id=user_dm_id, text="❌ **Missing text!** Please include the answer in the caption.")
        return

    author_name = update.effective_user.first_name
    if update.effective_user.last_name:
        author_name += f" {update.effective_user.last_name}"

    parsed = None
    if photo_id:
        parsed = parse_shorthand_caption(raw_text)
    if not parsed:
        parsed = parse_upsc_question(raw_text, has_photo=bool(photo_id))

    if not parsed:
        await context.bot.send_message(chat_id=user_dm_id, text="❌ **Could not parse.**\nDid you forget the ✅? Make sure options are placed cleanly above the explanation.")
        return

    question_text = parsed["question"]
    options = parsed["options"]
    correct_id = parsed["correct_option_id"]
    explanation = parsed["explanation"]

    try:
        safe_author = author_name.replace('<', '&lt;').replace('>', '&gt;')
        author_append = f"\n\n👤 <i>Quiz by: {safe_author}</i>"
        
        sent_photo_msg = None
        if photo_id:
            sent_photo_msg = await context.bot.send_photo(
                chat_id=TARGET_GROUP_ID,
                photo=photo_id,
                caption=f"📸 <b>Image Reference</b>\n\n👤 <i>Submitted by: {safe_author}</i>",
                parse_mode="HTML"
            )

        safe_question = question_text.replace('<', '&lt;').replace('>', '&gt;')
        raw_length = len(question_text) + len(f"\n\n👤 Quiz by: {author_name}")
        reply_target_id = sent_photo_msg.message_id if sent_photo_msg else None

        if raw_length > 300:
            long_question_text = f"📌 <b>QUESTION:</b>\n\n{safe_question}"
            await send_long_message(context, TARGET_GROUP_ID, long_question_text, "HTML", reply_target_id)
            poll_question = f"👇 Refer to the question above:{author_append}"
        else:
            poll_question = f"{safe_question}{author_append}"

        short_exp = explanation[:200] if explanation else ""

        await context.bot.send_poll(
            chat_id=TARGET_GROUP_ID,
            question=poll_question,
            options=options,
            type=Poll.QUIZ,
            correct_option_id=correct_id,
            explanation=short_exp,
            is_anonymous=False,
            question_parse_mode="HTML",
            reply_to_message_id=reply_target_id
        )
        
        await context.bot.send_message(chat_id=user_dm_id, text="✅ **Success!** Your unprefixed quiz was perfectly formatted and published.", parse_mode="Markdown")

    except Exception as e:
        await context.bot.send_message(chat_id=user_dm_id, text=f"❌ **Error posting to group.**\nError details: `{e}`", parse_mode="Markdown")

# --- FASTAPI WEBHOOK SERVER ---
ptb = Application.builder().updater(None).token(BOT_TOKEN).build()

ptb.add_handler(CommandHandler("start", start_command, filters=filters.ChatType.PRIVATE))
ptb.add_handler(CommandHandler("help", help_command, filters=filters.ChatType.PRIVATE))
ptb.add_handler(CommandHandler("status", status_command, filters=filters.ChatType.PRIVATE))
ptb.add_handler(MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND & filters.ChatType.PRIVATE, create_upsc_quiz))

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
