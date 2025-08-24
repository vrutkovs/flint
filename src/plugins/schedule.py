from telega.settings import Settings
from telegram.ext import ContextTypes

import structlog

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
    {calendar_events}

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

    weather_data = """
    Currently: 16.7°C, partlycloudy.
    Precipitation Chance: 0.0%.
    Today's Forecast: High of 23.9°C, Low of 14.5°C.
    """

    calendar_events = """
    - Recharge day (All day (Fri, Aug 22))
    - Vadim / VictoriaMetrics (3:00 PM on Fri, Aug 22)
    """

    prompt = PROMPT_TEMPLATE.format(weather_data=weather_data, calendar_events=calendar_events)

    response = await genai_client.aio.models.generate_content(
        model=settings.model,
        contents=[prompt]
    )
    text = response.text
    if not text:
        settings.logger.error("Empty response from AI when generating agenda")
        raise ValueError("Empty response from AI")

    await context.bot.send_message(chat_id=chat_id, text=text)
