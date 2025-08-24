from telega.settings import Settings
from telegram.ext import ContextTypes

import structlog

from plugins.homeassistant import HomeAssistant

class ScheduleData:
    def __init__(self, settings: Settings, genai_client):
        self.settings = settings
        self.genai_client = genai_client

PROMPT_TEMPLATE = """
You are a helpful digital assistant.

Your primary role is to provide a daily briefing.

Adopt the following persona for your response: The city's a cold, hard
place. You're a world-weary film noir detective. Deliver the facts,
straight, no chaser.

Organize the information clearly. Use emojis if they genuinely enhance the
message and fit your adopted persona.

If there's no information for a section, acknowledge its absence in
character.

Avoid using markdown formatting. Use extra whitelines and line breaks to enhance readability.

Good morning! Here is your morning briefing.

Weather Update:
    {weather_data}

Upcoming Calendar Events (next 24 hours):
    {calendar_data}

Please synthesize this into a single, coherent message, adhering to your
persona. If a section is empty or explicitly states no information,
acknowledge it cheerfully or omit it gracefully.
"""

async def send_agenda(context: ContextTypes.DEFAULT_TYPE):
    log = structlog.get_logger()
    log.info("Sending agenda")

    job = context.job
    if not job:
        print("Job is missing")
        return
    job_data = job.data
    if not job_data:
        print("Job data is missing")
        return
    chat_id = job.chat_id
    if not chat_id:
        print("Chat ID is missing")
        return

    settings = job_data.__getattribute__("settings")
    genai_client = job_data.__getattribute__("genai_client")

    settings.logger.info("Generating agenda")

    ha = HomeAssistant(settings.ha_url, settings.ha_token, settings.logger, settings.timezone)
    # try:
    #     calendar_data = ha.get_calendar(settings.ha_calendar_entity)
    # except Exception as e:
    #     settings.logger.error(f"Error fetching calendar data: {e}")
    #     calendar_data = None
    calendar_data = None

    try:
        weather_data = ha.get_weather_forecast(settings.ha_weather_entity_id)
    except Exception as e:
        settings.logger.error(f"Error fetching weather data: {e}")
        weather_data = None
    weather_data = None

    prompt = PROMPT_TEMPLATE.format(weather_data=weather_data, calendar_data=calendar_data)

    response = await genai_client.aio.models.generate_content(
        model=settings.model_name,
        contents=[prompt]
    )
    text = response.text
    if not text:
        settings.logger.error("Empty response from AI when generating agenda")
        raise ValueError("Empty response from AI")

    await context.bot.send_message(chat_id=chat_id, text=text)
