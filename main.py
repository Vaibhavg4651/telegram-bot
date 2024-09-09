import logging
from contextlib import asynccontextmanager
from telegram.ext import Application, CommandHandler, MessageHandler, filters 
from typing import Final
import os
from dotenv import load_dotenv
from BotController import handle_message , policies, end
from pyngrok import ngrok
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


public_url= os.getenv('PUBLIC_URL')

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
    req = await request.json()
    update = Update.de_json(req, application.bot)
    await application.process_update(update)
    return Response(status_code=HTTPStatus.OK)


application.add_handler(CommandHandler("policies", policies))
application.add_handler(CommandHandler("end", end))
application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))


def main() -> None:
    # public_url = ngrok.connect(port).public_url
    # logger.info(f"ngrok tunnel \"{public_url}\" -> \"http://127.0.0.1:{port}\"")
    
    # Manually run the event loop for the async setup_webhook
    # loop = asyncio.get_event_loop()
    # loop.run_until_complete(setup_webhook(application, public_url))

    # Run FastAPI app
    uvicorn.run(app)

if __name__ == '__main__':
    main()