import datetime
import os
import sys
from typing import Final

import structlog
from dotenv import find_dotenv, load_dotenv
from google import genai
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from plugins.schedule import ScheduleData, send_agenda
from telega.main import Telega
from telega.settings import Settings

load_dotenv(find_dotenv())

DEFAULT_SYSTEM_INSTRUCTIONS: Final[str] = """
You are a helpful assistant.

Adopt the following persona for your response: The city's a cold, hard
place. You're a world-weary film noir detective called Fenton "Flint" Foster.
Deliver the facts, straight, no chaser.

Organize the information clearly. Use emojis if they genuinely enhance the
message and fit your adopted persona.

Always reply in the same language as the user. If user doesn't specify a language, default to English.
When running the tool, translate the user's message to English.
Always translate the response back to the user's language, including tool output.
"""

# Settings are read from environment variables
TOKEN: Final[str | None] = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    print("TELEGRAM_TOKEN environment variable is required")
    sys.exit(1)

CHAT_ID: Final[str | None] = os.getenv("TELEGRAM_CHAT_ID")
if not CHAT_ID:
    print("TELEGRAM_CHAT_ID environment variable is required")
    sys.exit(1)

API_KEY: str | None = os.environ.get("GOOGLE_API_KEY")
if not API_KEY:
    print("GOOGLE_API_KEY environment variable is required")
    sys.exit(1)

MODEL_NAME: str | None = os.environ.get("MODEL_NAME")
if not MODEL_NAME:
    print("MODEL_NAME environment variable is required")
    sys.exit(1)

MCP_CONFIG_PATH: str | None = os.environ.get("MCP_CONFIG_PATH")
if not MCP_CONFIG_PATH:
    print("MCP_CONFIG_PATH environment variable is required")
    sys.exit(1)

SUMMARY_MCP_CALENDAR_NAME: str | None = os.environ.get("SUMMARY_MCP_CALENDAR_NAME")
if not SUMMARY_MCP_CALENDAR_NAME:
    print("SUMMARY_MCP_CALENDAR_NAME environment variable is required")
    sys.exit(1)

SUMMARY_MCP_WEATHER_NAME: str | None = os.environ.get("SUMMARY_MCP_WEATHER_NAME")
if not SUMMARY_MCP_WEATHER_NAME:
    print("SUMMARY_MCP_WEATHER_NAME environment variable is required")
    sys.exit(1)

SYSTEM_INSTRUCTIONS: str = os.environ.get("SYSTEM_INSTRUCTIONS", DEFAULT_SYSTEM_INSTRUCTIONS)

RAG_EMBEDDING_MODEL: str | None = os.environ.get("RAG_EMBEDDING_MODEL")
RAG_LOCATION: str | None = os.environ.get("RAG_LOCATION")
RAG_GOOGLE_PROJECT_ID: str | None = os.environ.get("RAG_GOOGLE_PROJECT_ID")

SCHEDULED_AGENDA_TIME: str | None = os.environ.get("SCHEDULED_AGENDA_TIME")
TZ: str = os.getenv("TZ", "UTC")
USER_FILTER: list[str] = os.environ.get("USER_FILTER", "").split(",")

# Configure structured logging
log: structlog.BoundLogger = structlog.get_logger()
log.info("Starting up Flint...")

# Initialize Google's Gemini client for text generation
try:
    genai_client: genai.Client = genai.Client(api_key=API_KEY)
    log.info("GenAI client initialized successfully")
except Exception as e:
    log.error("Failed to initialize GenAI client", error=str(e))
    sys.exit(1)

# Create Settings instance
settings: Settings = Settings(
    genai_client=genai_client,
    logger=log,
    model_name=MODEL_NAME,
    chat_id=CHAT_ID,
    tz=TZ,
    mcp_config_path=MCP_CONFIG_PATH,
    summary_mcp_calendar_name=SUMMARY_MCP_CALENDAR_NAME,
    summary_mcp_weather_name=SUMMARY_MCP_WEATHER_NAME,
    user_filter=USER_FILTER,
    system_instructions=SYSTEM_INSTRUCTIONS,
    rag_embedding_model=RAG_EMBEDDING_MODEL,
    rag_location=RAG_LOCATION,
    google_api_key=API_KEY,
)
log.info("Settings instance created")

# Create Telega instance
telega: Telega = Telega(settings=settings)
log.info("Telega instance created")

# Create Telegram application
try:
    app: Application = Application.builder().token(TOKEN).build()
    log.info("Telegram application created")
except Exception as e:
    log.error("Failed to create Telegram application", error=str(e))
    sys.exit(1)

# Add handlers for different message types
# Handler for photo messages
app.add_handler(MessageHandler(filters.PHOTO, telega.handle_photo_message))

# Add handlers for MCP clients
telega.mcps.reload_config()

for mcp_name in telega.mcps.get_enabled_mcps():
    log.info(f"Registering handler for MCP client: {mcp_name}")
    app.add_handler(CommandHandler(mcp_name, telega.handle_mcp_message))

app.add_handler(CommandHandler("list_mcps", telega.handle_list_mcps_message))
app.add_handler(CommandHandler("rag", telega.handle_rag_request))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, telega.handle_text_message))
log.info("Registered handler for Gemini")

log.info("Message handlers registered")

# Create scheduler for periodic tasks
if SCHEDULED_AGENDA_TIME:
    job_queue = app.job_queue
    if not job_queue:
        log.error("Failed to create job queue")
        sys.exit(1)

    hour: int
    minute: int
    hour, minute = map(int, SCHEDULED_AGENDA_TIME.split(":"))
    schedule_time: datetime.time = datetime.time(hour=hour, minute=minute, tzinfo=settings.timezone)
    scheduleData: ScheduleData = ScheduleData(settings=settings, genai_client=genai_client)

    job_queue.run_daily(
        send_agenda,
        time=schedule_time,
        chat_id=int(CHAT_ID),
        data=scheduleData,
    )
    log.info(f"Scheduled agenda updated at {schedule_time}")

# Start the bot
try:
    log.info("Starting bot polling...")
    app.run_polling(poll_interval=3, timeout=10)
except KeyboardInterrupt:
    log.info("Bot stopped by user")
except Exception as e:
    log.error("Bot encountered an error", error=str(e))
    sys.exit(1)
