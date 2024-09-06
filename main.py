import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import PyPDF2
import io
from typing import Final, Dict
import os
from dotenv import load_dotenv
import easyocr
import asyncio
import cv2
import numpy as np
from Session import UserSession
from concurrent.futures import ThreadPoolExecutor
import threading


load_dotenv()

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN: Final = os.getenv("TOKEN")
BOT_NAME: Final = os.getenv("BOT_NAME")



user_sessions: Dict[int, UserSession] = {}
session_lock = threading.Lock()

def get_user_session(chat_id: int) -> UserSession:
    with session_lock:
        if chat_id not in user_sessions:
            user_sessions[chat_id] = UserSession()
        return user_sessions[chat_id]

async def policies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    session = get_user_session(chat_id)
    if session.capturing_policies:
        await update.message.reply_text("A policy capture session is already in progress. Please end it with /end before starting a new one.")
    else:
        # Start a new session
        session.start_capture()
        await update.message.reply_text("Started capturing policies. Send /end when you're finished, or wait 2 minutes for auto-capture.")
        # Set a timeout job for the session
        context.job_queue.run_once(check_timeout, 120, chat_id=chat_id, name=str(chat_id))

async def end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    session = get_user_session(chat_id)
    if session.capturing_policies:
        await send_collected_policies(update, context)
    else:
        await update.message.reply_text("No active policy capture session. Start with /policies first.")

async def process_message(message, context):
    policiesText = ""
    if message.document and message.document.mime_type == 'application/pdf':
        file = await context.bot.get_file(message.document.file_id)
        f = io.BytesIO(await file.download_as_bytearray())
        pdf_reader = PyPDF2.PdfReader(f)
        policiesText = "\n".join([page.extract_text() for page in pdf_reader.pages])
    
    elif message.photo:
        file = await context.bot.get_file(message.photo[-1].file_id)
        file_bytes = await file.download_as_bytearray()
        np_arr = np.frombuffer(file_bytes, np.uint8)
        image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        reader = easyocr.Reader(['en'])
        result = reader.readtext(image)
        for(_, text, _) in result:
            policiesText += text+" "
        if message.caption:
            policiesText += "\n\nImage Caption: " + message.caption
    else:
        policiesText = message.text or ""
    return policiesText

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    session = get_user_session(chat_id)
    if session.capturing_policies:
        policiesText = await process_message(update.message, context)
        session.add_message(policiesText)
    
    if session.min_messages_reached:
        await send_collected_policies(update, context, chat_id)


async def check_timeout(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    chat_id = job.chat_id
    session = get_user_session(chat_id)

    if session.capturing_policies:
        await send_collected_policies(None, context, chat_id)

    else:
        await context.bot.send_message(chat_id=chat_id, text="Policy capture session ended.")
    

async def send_collected_policies(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id=None) -> None:
    if chat_id is None:
        chat_id = update.effective_chat.id
    session = get_user_session(chat_id)

    data = session.policy_messages[:5]

    if data:
        response = "Here are the collected policies:\n\n" + "\n\n".join(data)
        if len(response) > 4096:
            response = response[:4093] + "..."  # Telegram message limit is 4096 characters
        if update:
            await update.message.reply_text(response)
        else:
            await context.bot.send_message(chat_id=chat_id, text=response)
        
        session.end_capture()
    else:
        message = "No policies were captured." if update else "Policy capture session ended without any messages."
        if update:
            await update.message.reply_text(message)
        else:
            await context.bot.send_message(chat_id=chat_id, text=message)
        session.end_capture()


def main() -> None:
    async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.error(f"Update {update} caused error {context.error}")


    application = Application.builder().token(TOKEN).connect_timeout(40).read_timeout(120).build()

    application.add_handler(CommandHandler("policies", policies))
    application.add_handler(CommandHandler("end", end))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    application.add_error_handler(error_handler)

    application.run_polling()

if __name__ == '__main__':
    main()