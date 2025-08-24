import os
import sys
from typing import Final

import structlog
from telegram.ext import Application, MessageHandler, filters
from google import genai

from telega.main import Telega

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

# Create Telega instance
telega = Telega(genai_client=genai_client, logger=log)
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

# Start the bot
try:
    log.info('Starting bot polling...')
    app.run_polling(poll_interval=3, timeout=10)
except KeyboardInterrupt:
    log.info('Bot stopped by user')
except Exception as e:
    log.error('Bot encountered an error', error=str(e))
    sys.exit(1)
