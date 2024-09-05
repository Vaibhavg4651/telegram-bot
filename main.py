# import logging
# from telegram import Update
# from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
# import PyPDF2
# import pytesseract
# from PIL import Image
# from dotenv import load_dotenv
# from typing import Final
# import io
# import os

# load_dotenv()

# # Enable logging
# logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
# logger = logging.getLogger(__name__)

# # Replace 'YOUR_BOT_TOKEN' with your actual bot token
# TOKEN: Final = os.getenv("TOKEN")
# BOT_NAME: Final = os.getenv("BOT_NAME")

# # Store messages after /policies
# policy_messages = []

# async def policies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
#     global policy_messages
#     policy_messages = []
#     await update.message.reply_text("Please send the next 5 messages (text, PDF, or images).")
#     context.user_data['expecting_policies'] = 5

# async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
#     if 'expecting_policies' in context.user_data and context.user_data['expecting_policies'] > 0:
#         message = update.message
#         text = ""

#         if message.document and message.document.mime_type == 'application/pdf':
#             file = await context.bot.get_file(message.document.file_id)
#             f = io.BytesIO(await file.download_as_bytearray())
#             pdf_reader = PyPDF2.PdfReader(f)
#             text = "\n".join([page.extract_text() for page in pdf_reader.pages])
#         elif message.photo:
#             file = await context.bot.get_file(message.photo[-1].file_id)
#             image = Image.open(io.BytesIO(await file.download_as_bytearray()))
#             text = pytesseract.image_to_string(image)
#         else:
#             text = message.text or ""

#         policy_messages.append(text)
#         context.user_data['expecting_policies'] -= 1

#         if context.user_data['expecting_policies'] == 0:
#             response = "Here are the collected policies:\n\n" + "\n\n".join(policy_messages)
#             await update.message.reply_text(response)
#             del context.user_data['expecting_policies']

# def main() -> None:
#     application = Application.builder().token(TOKEN).build()

#     application.add_handler(CommandHandler("policies", policies))
#     application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

#     print(f"polling")
#     application.run_polling()

# if __name__ == '__main__':
#     print(f"Starting {BOT_NAME}...")
#     main()


import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import PyPDF2
import io
from typing import Final
import os
from dotenv import load_dotenv
import easyocr
import cv2
import numpy as np

load_dotenv

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN: Final = os.getenv("TOKEN")
BOT_NAME: Final = os.getenv("BOT_NAME")

async def policies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data['policy_messages'] = []
    context.user_data['capturing_policies'] = True
    context.user_data['policy_start_time'] = asyncio.get_event_loop().time()
    await update.message.reply_text("Started capturing policies. Send /end when you're finished, or wait 2 minutes for auto-capture.")
    context.job_queue.run_once(check_timeout, 120, chat_id=update.effective_chat.id, name=str(update.effective_chat.id))

async def end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get('capturing_policies', False):
        await send_collected_policies(update, context)
    else:
        await update.message.reply_text("No active policy capture session. Start with /policies first.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get('capturing_policies', False):
        message = update.message
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

        else:
            policiesText = message.text or ""

        context.user_data['policy_messages'].append(policiesText)

        # Check if we've reached 5 messages
        if len(context.user_data['policy_messages']) >= 5:
            context.user_data['min_messages_reached'] = True

async def check_timeout(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    chat_id = job.chat_id
    user_data = context.application.user_data.get(chat_id, {})

    if user_data.get('capturing_policies', False):
        if user_data.get('min_messages_reached', False):
            await send_collected_policies(None, context, chat_id)
        else:
            # If 5 messages haven't been reached, schedule another check in 30 seconds
            context.job_queue.run_once(check_timeout, 30, chat_id=chat_id, name=str(chat_id))

async def send_collected_policies(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id=None) -> None:
    if chat_id is None:
        chat_id = update.effective_chat.id
    user_data = context.user_data if update else context.application.user_data.get(chat_id, {})

    data = user_data.get('policy_messages', [])[:5]

    if 'policy_messages' in user_data:
        response = "Here are the collected policies:\n\n" + "\n\n".join(data)
        if len(response) > 4096:
            response = response[:4093] + "..."  # Telegram message limit is 4096 characters
        if update:
            await update.message.reply_text(response)
        else:
            await context.bot.send_message(chat_id=chat_id, text=response)
        
        user_data.pop('policy_messages', None)
        user_data.pop('capturing_policies', None)
        user_data.pop('policy_start_time', None)
        user_data.pop('min_messages_reached', None)
    else:
        message = "No policies were captured." if update else "Policy capture session ended without any messages."
        if update:
            await update.message.reply_text(message)
        else:
            await context.bot.send_message(chat_id=chat_id, text=message)

def main() -> None:
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("policies", policies))
    application.add_handler(CommandHandler("end", end))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))

    application.run_polling()

if __name__ == '__main__':
    main()