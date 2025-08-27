import os
import sys
from typing import Final
import datetime
from dotenv import load_dotenv, find_dotenv

import structlog
from telegram.ext import Application, MessageHandler, CommandHandler, filters
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

HA_URL = os.environ.get("HA_URL")
if not HA_URL:
    print("HA_URL environment variable is required")
    sys.exit(1)

HA_TOKEN = os.environ.get("HA_TOKEN")
if not HA_TOKEN:
    print("HA_TOKEN environment variable is required")
    sys.exit(1)

HA_WEATHER_ENTITY_ID = os.environ.get("HA_WEATHER_ENTITY_ID")
if not HA_WEATHER_ENTITY_ID:
    print("HA_WEATHER_ENTITY_ID environment variable is required")
    sys.exit(1)

MCP_CONFIG_PATH = os.environ.get("MCP_CONFIG_PATH")
if not MCP_CONFIG_PATH:
    print("MCP_CONFIG_PATH environment variable is required")
    sys.exit(1)

SUMMARY_MCP_CALENDAR_NAME = os.environ.get("SUMMARY_MCP_CALENDAR_NAME")
if not SUMMARY_MCP_CALENDAR_NAME:
    print("SUMMARY_MCP_CALENDAR_NAME environment variable is required")
    sys.exit(1)

SCHEDULED_AGENDA_TIME = os.environ.get("SCHEDULED_AGENDA_TIME")
TZ = os.getenv('TZ', 'UTC')

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
settings = Settings(
    genai_client=genai_client,
    logger=log,
    model_name=MODEL_NAME,
    chat_id=CHAT_ID,
    tz=TZ,
    ha_url=HA_URL,
    ha_token=HA_TOKEN,
    ha_weather_entity_id=HA_WEATHER_ENTITY_ID,
    mcp_config_path=MCP_CONFIG_PATH,
    summary_mcp_calendar_name=SUMMARY_MCP_CALENDAR_NAME,
)
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

# Add handlers for MCP clients
telega.mcps.reload_config()

for mcp_name in telega.mcps.get_enabled_mcps():
    log.info(f'Registering handler for MCP client: {mcp_name}')
    app.add_handler(CommandHandler(mcp_name, telega.handle_mcp_message))

app.add_handler(CommandHandler("list_mcps", telega.handle_list_mcps_message))
app.add_handler(CommandHandler("gemini", telega.handle_text_message))
log.info('Registered handler for Gemini')

log.info('Message handlers registered')

# Create scheduler for periodic tasks
if SCHEDULED_AGENDA_TIME:
    job_queue = app.job_queue
    if not job_queue:
        log.error('Failed to create job queue')
        sys.exit(1)

    hour, minute = map(int, SCHEDULED_AGENDA_TIME.split(':'))
    schedule_time = datetime.time(hour=hour, minute=minute, tzinfo=settings.timezone)
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
