import datetime
import os
import sys
from typing import Final

import structlog
from dotenv import find_dotenv, load_dotenv
from google import genai
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from plugins.diary import DiaryData, generate_diary_entry
from plugins.schedule import ScheduleData, send_agenda
from telega.main import Telega
from telega.settings import Settings

load_dotenv(find_dotenv())

DEFAULT_SYSTEM_INSTRUCTIONS: Final[str] = """
You are a helpful assistant.

CRITICAL: You need to speak in a comically overdone European accent

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

MCP_CALENDAR_NAME: str | None = os.environ.get("MCP_CALENDAR_NAME")
MCP_TODOIST_NAME: str | None = os.environ.get("MCP_TODOIST_NAME")
MCP_WEATHER_NAME: str | None = os.environ.get("MCP_WEATHER_NAME")

SYSTEM_INSTRUCTIONS: str = os.environ.get("SYSTEM_INSTRUCTIONS", DEFAULT_SYSTEM_INSTRUCTIONS)

RAG_EMBEDDING_MODEL: str | None = os.environ.get("RAG_EMBEDDING_MODEL")
RAG_LOCATION: str | None = os.environ.get("RAG_LOCATION")
RAG_VECTOR_STORAGE: str | None = os.environ.get("RAG_VECTOR_STORAGE")

SCHEDULED_AGENDA_TIME: str | None = os.environ.get("SCHEDULED_AGENDA_TIME")
SCHEDULED_DIARY_TIME: str | None = os.environ.get("SCHEDULED_DIARY_TIME", "23:59")
GOOGLE_OAUTH_CREDENTIALS: str | None = os.environ.get("GOOGLE_OAUTH_CREDENTIALS")
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
    mcp_calendar_name=MCP_CALENDAR_NAME or "",
    mcp_todoist_name=MCP_TODOIST_NAME or "",
    mcp_weather_name=MCP_WEATHER_NAME or "",
    user_filter=USER_FILTER,
    system_instructions=SYSTEM_INSTRUCTIONS,
    rag_embedding_model=RAG_EMBEDDING_MODEL,
    rag_location=RAG_LOCATION,
    rag_vector_storage=RAG_VECTOR_STORAGE,
    google_api_key=API_KEY,
)
log.info("Settings instance created")

# Create Telega instance
telega: Telega = Telega(settings=settings)
log.info("Telega instance created")

# Create Telegram application
try:
    app = Application.builder().token(TOKEN).build()
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
if SCHEDULED_AGENDA_TIME and MCP_CALENDAR_NAME and MCP_WEATHER_NAME:
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
elif SCHEDULED_AGENDA_TIME:
    log.warning("SCHEDULED_AGENDA_TIME is set but MCP_CALENDAR_NAME or MCP_WEATHER_NAME is missing. Daily agenda will not be scheduled.")

# Create scheduler for diary entries
if SCHEDULED_DIARY_TIME and MCP_CALENDAR_NAME and MCP_TODOIST_NAME:
    if GOOGLE_OAUTH_CREDENTIALS and not os.path.exists(GOOGLE_OAUTH_CREDENTIALS):
        log.warning(f"Google OAuth credentials file not found: {GOOGLE_OAUTH_CREDENTIALS}")
        log.warning("Diary feature will work with limited functionality (no calendar data)")

    job_queue = app.job_queue
    if not job_queue:
        log.error("Failed to create job queue")
        sys.exit(1)

    diary_hour: int
    diary_minute: int
    diary_hour, diary_minute = map(int, SCHEDULED_DIARY_TIME.split(":"))
    diary_schedule_time: datetime.time = datetime.time(hour=diary_hour, minute=diary_minute, tzinfo=settings.timezone)
    diary_data: DiaryData = DiaryData(settings=settings, genai_client=genai_client)

    job_queue.run_daily(
        generate_diary_entry,
        time=diary_schedule_time,
        chat_id=int(CHAT_ID),
        data=diary_data,
    )
    log.info(f"Scheduled diary entry generation at {diary_schedule_time}")

    if GOOGLE_OAUTH_CREDENTIALS:
        log.info(f"Google Calendar integration enabled using: {GOOGLE_OAUTH_CREDENTIALS}")
    else:
        log.info("GOOGLE_OAUTH_CREDENTIALS not set - diary will work without calendar data")
elif SCHEDULED_DIARY_TIME:
    log.warning("SCHEDULED_DIARY_TIME is set but MCP_CALENDAR_NAME or MCP_TODOIST_NAME is missing. Diary scheduling will not be enabled.")

# Start the bot
try:
    log.info("Starting bot polling...")
    app.run_polling(poll_interval=3, timeout=10)
except KeyboardInterrupt:
    log.info("Bot stopped by user")
except Exception as e:
    log.error("Bot encountered an error", error=str(e))
    sys.exit(1)
