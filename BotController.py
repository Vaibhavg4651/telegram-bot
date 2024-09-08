from telegram import Update
from telegram.ext import ContextTypes
import PyPDF2
import io
from typing import Dict
import easyocr
import cv2
import numpy as np
from Session import UserSession
import threading



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
        await start_policy_capture(update, context, chat_id)



async def start_policy_capture(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    session = get_user_session(chat_id)
    session.start_capture()
    await context.bot.send_message(chat_id=chat_id, text="Started capturing policies. Send /end when you're finished, or wait 2 minutes for auto-capture.")
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
    message = update.message

    # Check if the message contains "/policies" in text, caption, or document filename
    contains_policies_command = False
    if message.text and "/policies" in message.text.lower():
        contains_policies_command = True
    elif message.caption and "/policies" in message.caption.lower():
        contains_policies_command = True
    elif message.document and message.document.file_name and "/policies" in message.document.file_name.lower():
        contains_policies_command = True

    if contains_policies_command and not session.capturing_policies:
        await start_policy_capture(update, context, chat_id)

    if session.capturing_policies:
        policiesText = await process_message(message, context)
        session.add_message(policiesText)
    
    if session.min_messages_reached:
        await send_collected_policies(update, context, chat_id)



async def check_timeout(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    chat_id = job.chat_id
    session = get_user_session(int(chat_id))  # Convert chat_id to int

    if session.capturing_policies:
        if not session.min_messages_reached:
            await send_collected_policies(None, context, int(chat_id))  # Convert chat_id to int
        else:
            await context.bot.send_message(chat_id=int(chat_id), text="Auto Policy capture session ended.")  # Convert chat_id to int



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