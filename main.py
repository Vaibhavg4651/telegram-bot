import logging
from contextlib import asynccontextmanager
from telegram.ext import Application, CommandHandler, MessageHandler, filters 
from typing import Final
import os
from dotenv import load_dotenv
from BotController import handle_message , policies, end
from pyngrok import ngrok
import httpx
from http import HTTPStatus
from telegram import Update
import uvicorn
from fastapi import FastAPI, Request,Response


load_dotenv()

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN: Final = os.getenv("TOKEN")
BOT_NAME: Final = os.getenv("BOT_NAME")
application = (Application.builder().token(TOKEN).connect_timeout(20).read_timeout(120).build())
forward_url = os.getenv("SUCH_CHAT_URL")
public_url = os.getenv("PUBLIC_URL")


@asynccontextmanager
async def setup_webhook( _: FastAPI):
    webhook_url = f"{public_url}/telegram"
    await application.initialize()
    await application.bot.set_webhook(url=webhook_url)
    async with application:
        await application.start()
        yield
        await application.stop()
    logger.info(f"Webhook set up at {webhook_url}")

app = FastAPI(lifespan=setup_webhook)

@app.get("/")
def home():
    return {"Hello": "World"}


@app.post(f'/telegram')
async def webhook( request: Request):
    try:
        req = await request.json()
        
        update = Update.de_json(req, application.bot)
        
        await application.process_update(update)
        
        if 'message' in req and 'text' in req['message']:
            text = req['message']['text']
            if text.startswith('/'):
                # If it's a slash command, don't forward to the API
                return Response(status_code=HTTPStatus.OK)
        async with httpx.AsyncClient() as client:
            await client.post(forward_url, json=req, timeout=10.0)
        return Response(status_code=HTTPStatus.OK)
    except httpx.RequestError as e:
        # This exception is raised for network-related errors
        logger.error(f"An error occurred while forwarding the request: {e}")
        return Response(status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

    except httpx.HTTPStatusError as e:
        # This exception is raised when the forwarded request returns a 4xx or 5xx status code
        logger.error(f"Error response {e.response.status_code} while forwarding the request: {e}")
        return Response(status_code=HTTPStatus.BAD_GATEWAY)

    except Exception as e:
        # Catch any other unexpected errors
        logger.error(f"An unexpected error occurred: {e}")
        return Response(status_code=HTTPStatus.INTERNAL_SERVER_ERROR)


application.add_handler(CommandHandler("policies", policies))
application.add_handler(CommandHandler("end", end))
application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))


# def main() -> None:
#     port = 5000
#     global public_url
#     public_url = ngrok.connect(port).public_url
#     logger.info(f"ngrok tunnel \"{public_url}\" -> \"http://127.0.0.1:{port}\"")
    
#     uvicorn.run(app, port=port)

# if __name__ == '__main__':
#     main()