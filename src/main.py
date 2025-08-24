import os
import sys
from typing import Final
import datetime
import pytz
from dotenv import load_dotenv, find_dotenv

import structlog
from telegram.ext import Application, MessageHandler, filters
from google import genai

from telega.main import Telega
from telega.settings import Settings
from plugins.schedule import send_agenda, ScheduleData

load_dotenv(find_dotenv())

# Settings are read from environment variables
TOKEN: Final = os.getenv('TELEGRAM_TOKEN')
if not TOKEN:
    print("TELEGRAM_TOKEN environment variable is required")
    sys.exit(1)

CHAT_ID: Final = os.getenv('TELEGRAM_CHAT_ID')
if not CHAT_ID:
    print("TELEGRAM_CHAT_ID environment variable is required")
    sys.exit(1)

API_KEY = os.environ.get("GOOGLE_API_KEY")
if not API_KEY:
    print("GOOGLE_API_KEY environment variable is required")
    sys.exit(1)

MODEL_NAME = os.environ.get("MODEL_NAME")
if not MODEL_NAME:
    print("MODEL_NAME environment variable is required")
    sys.exit(1)

SCHEDULED_AGENDA_TIME = os.environ.get("SCHEDULED_AGENDA_TIME")

# Configure structured logging
log = structlog.get_logger()
log.info('Starting up bot...')

# Initialize Google's Gemini client for text generation
try:
    genai_client = genai.Client(api_key=API_KEY)
    log.info('GenAI client initialized successfully')
except Exception as e:
    log.error('Failed to initialize GenAI client', error=str(e))
    sys.exit(1)

# Create Settings instance
settings = Settings(genai_client=genai_client, logger=log, model_name=MODEL_NAME, chat_id=CHAT_ID)
log.info('Settings instance created')

# Create Telega instance
telega = Telega(settings=settings)
log.info('Telega instance created')

# Create Telegram application
try:
    app = Application.builder().token(TOKEN).build()
    log.info('Telegram application created')
except Exception as e:
    log.error('Failed to create Telegram application', error=str(e))
    sys.exit(1)

# Add handlers for different message types
# Handler for photo messages
app.add_handler(MessageHandler(filters.PHOTO, telega.handle_photo_message))

# Handler for text messages
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, telega.handle_text_message))

log.info('Message handlers registered')

# Create scheduler for periodic tasks
if SCHEDULED_AGENDA_TIME:
    job_queue = app.job_queue
    if not job_queue:
        log.error('Failed to create job queue')
        sys.exit(1)

    hour, minute = map(int, SCHEDULED_AGENDA_TIME.split(':'))

    tz = pytz.timezone(os.getenv('TZ', 'UTC'))
    schedule_time = datetime.time(hour=hour, minute=minute, tzinfo=tz)

    scheduleData = ScheduleData(settings=settings, genai_client=genai_client)
    job_queue.run_daily(
        send_agenda,
        time=schedule_time,
        chat_id=int(CHAT_ID),
        data=scheduleData,
    )
    log.info(f"Scheduled agenda updated at {schedule_time}")

# Start the bot
try:
    log.info('Starting bot polling...')
    app.run_polling(poll_interval=3, timeout=10)
except KeyboardInterrupt:
    log.info('Bot stopped by user')
except Exception as e:
    log.error('Bot encountered an error', error=str(e))
    sys.exit(1)
