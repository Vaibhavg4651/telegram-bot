from telegram import Update
from telegram.ext import ContextTypes
import PyPDF2
import io
from typing import Dict
from Session import UserSession
import threading
from openai import OpenAI
import os
from dotenv import load_dotenv
import base64
from transform_json import send_to_coda
import re
import json
from datetime import datetime

load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")


client = OpenAI(
    api_key=openai_api_key
)


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
    print(update)
    session.start_capture(update)
    context.job_queue.run_once(check_timeout, 120, chat_id=chat_id, name=str(chat_id))



async def end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    session = get_user_session(chat_id)
    if session.capturing_policies:
        await send_collected_policies(update, context,chat_id)
    else:
        await update.message.reply_text("No active policy capture session. Start with /policies first.")



async def process_message(message, context):
    content = []
    if message.document and message.document.mime_type == 'application/pdf':
        file = await context.bot.get_file(message.document.file_id)
        f = io.BytesIO(await file.download_as_bytearray())
        pdf_reader = PyPDF2.PdfReader(f)
        policiesText = "\n".join([page.extract_text() for page in pdf_reader.pages])
        content.append({"type": "text", "text": f"PDF Content:\n{policiesText}"})
    
    elif message.photo:
        file = await context.bot.get_file(message.photo[-1].file_id)
        file_bytes = await file.download_as_bytearray()
        base64_image = base64.b64encode(file_bytes).decode('utf-8')

        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_image}"
            }
        })
    
    else:
        content.append({"type": "text", "text": f"Text Message:\n{message.text}"})
    if message.caption:
        content.append({"type": "text", "text": f"Caption:\n{message.caption}"})

    return content



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
            await context.bot.send_message(chat_id=int(chat_id), text="Policies saved.")
        else:
            await context.bot.send_message(chat_id=int(chat_id), text="Auto Policy capture session ended.")  # Convert chat_id to int



async def send_collected_policies(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id) -> None:
    print(context)
    session = get_user_session(chat_id)
    response_Data = "{}"
    data = session.policy_messages[:5]

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": '''Help me find all the details from the images and message below, only reply in JSON structure given with all the information.

                    {
                    "$schema": "http://json-schema.org/draft-07/schema#",
                    "type": "object",
                    "properties": {
                    "RegistrationNo": {
                    "type": "string",
                    "description": "The registration number of the vehicle as given in the documents."
                    },
                    "ManufacturingYear": {
                    "type": "string",
                    "description": "The year in which the vehicle was manufactured as given in the documents."
                    },
                    "MakeModelVariant": {
                    "type": "string",
                    "description": "The make, model, and variant of the vehicle as given in the documents."
                    },
                    "SeatingCapacity": {
                    "type": "string",
                    "description": "The seating capacity of the vehicle as given in the documents."
                    },
                    "FuelType": {
                    "type": "string",
                    "description": "The type of fuel used by the vehicle as given in the documents."
                    },
                    "CubicCapacity": {
                    "type": "string",
                    "description": "The cubic capacity (CC) of the vehicle's engine as given in the documents."
                    },
                    "VehicleIDV": {
                    "type": "string",
                    "description": "The Insured Declared Value (IDV) of the vehicle as given in the documents."
                    },
                    "NoClaimBonus": {
                    "type": "string",
                    "description": "The percentage of No Claim Bonus (NCB) applicable to the vehicle as given in the documents."
                    },
                    "ExpiryDate": {
                    "type": "string",
                    "description": "The expiry date of the vehicle insurance policy as given in the documents."
                    },
                    "ClaimConfirmation": {
                    "type": "string",
                    "enum": ["Yes", "No", "N/A"],
                    "description": "Did the customer confirm any claims on the vehicle as given in the documents? Reply 'Yes', 'No', or 'N/A'."
                    },
                    "AddOns": {
                    "type": "string",
                    "description": "Any additional coverage or add-ons on the vehicle insurance policy as given in the documents."
                    },
                    "CompanyName": {
                    "type": "string",
                    "description": "The name of the insurance company providing coverage for the vehicle as given in the documents."
                    },
                    "LastYearPremium": {
                    "type": "string",
                    "description": "The amount of the premium paid for the last year as given in the documents."
                    }
                    },
                    "required": [
                    "RegistrationNo",
                    "ManufacturingYear",
                    "MakeModelVariant",
                    "SeatingCapacity",
                    "FuelType",
                    "CubicCapacity",
                    "VehicleIDV",
                    "NoClaimBonus",
                    "ExpiryDate",
                    "ClaimConfirmation",
                    "AddOns",
                    "CompanyName",
                    "LastYearPremium"
                    ],
                    "additionalProperties": false
                    }


                    [Message]


                    Only reply in JSON and does not include the word json just give it in this {} format, and include all the information asked and give N/A for any information which you are not able to retrieve, do not give any other remarks or message along JSON.

                    '''
                }
            ]
        }
    ]
    if data:
        for sublist in data:
            for item in sublist:
                if item["type"] == "text":
                    messages[0]["content"].append({"type": "text", "text": item["text"]})
                elif item["type"] == "image_url":
                    messages[0]["content"].append({
                        "type": "image_url",
                        "image_url": item["image_url"]
                    })

        if messages[0]["content"]:
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    max_tokens=500
                )
                response_Data = response.choices[0].message.content
            except Exception as e:
                response_Data = f"Error processing content: {str(e)}"
    else:
        response_Data = "{}"

    if response_Data.startswith("json"):
        response_Data = response_Data[7:].strip()
    print(response_Data)

    processed_data = {}

    if response_Data and response_Data != "{}":
        try:
            # Attempt to parse the entire response as JSON
            processed_data = json.loads(response_Data)
        except json.JSONDecodeError:
            # If that fails, try to find a JSON object within the string
            match = re.search(r'\{.*\}', response_Data)
            if match:
                try:
                    processed_data = json.loads(match.group())
                except json.JSONDecodeError:
                    processed_data = {"error": "Failed to parse JSON from GPT response"}
                    await update.message.reply_text("No policies were captured. Please try again with /policies.")
                    return
            else:
                processed_data = {"error": "No valid JSON object found in GPT response"}
                await update.message.reply_text("No policies were captured. Please try again with /policies.")
                return

        print("Processed data:", processed_data)  # For debugging

        if all(value == "N/A" for value in processed_data.values()):
            message = "No policies were captured." if update else "Policy capture session ended without any messages."
            if update:
                await update.message.reply_text(message)
            session.end_capture()
            return
        
        message_id = session.message_id
        username = session.username or ""
        formatted_date = datetime.now().strftime("%d/%m/%y")

        processed_data.update({
            "chat_id": str(chat_id),
            "message_id": str(message_id),
            "username": username,
            "Date": str(formatted_date)
        })
    
        await send_to_coda(processed_data)
        
        session.end_capture()
    else:
        message = "No policies were captured." if update else "Policy capture session ended without any messages."
        if update:
            await update.message.reply_text(message)
        else:
            await context.bot.send_message(chat_id=chat_id, text=message)
        session.end_capture()