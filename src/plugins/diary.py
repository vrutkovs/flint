"""Diary plugin for generating daily diary entries in markdown format."""

import datetime
from typing import Any, Final, cast

import structlog
from google import genai
from PIL import Image
from telegram.ext import ContextTypes

from plugins.mcp import (
    MCPClient,
    MCPConfigReader,
    MCPConfiguration,
    StdioServerParameters,
)
from telega.settings import Settings


class DiaryData:
    """Data container for diary scheduling."""

    def __init__(self, settings: Settings, genai_client: genai.Client) -> None:
        """Initialize DiaryData with settings and client.

        Args:
            settings: Settings object containing configuration
            genai_client: Google GenAI client for content generation
        """
        self.settings: Settings = settings
        self.genai_client: genai.Client = genai_client


DIARY_PROMPT_TEMPLATE: Final[str] = """
You are a thoughtful diary companion and personal reflection assistant.

Your task is to create a daily diary entry in markdown format for {date}.

Guidelines for the diary entry:
1. Write in first person as if you are the user reflecting on their day
2. Use markdown formatting with proper headers and structure
3. Include sections for:
   - A brief summary of the day
   - Notable events or moments
   - Thoughts and feelings
   - Goals or plans for tomorrow
   - A gratitude note

4. Keep the tone personal, reflective, and authentic
5. The entry should feel like a genuine personal reflection
6. Use markdown formatting like headers (##), lists (-), and emphasis (*text*)
7. Length should be thoughtful but concise (200-400 words)

Based on any available information about today's events, create a meaningful diary entry.
If no specific events are provided, create a template-style entry that encourages reflection.

Calendar events from today:
{calendar_data}

Weather information:
{weather_data}

Current date: {date}
Current time: {time}

Please generate a complete diary entry in markdown format.
"""

DIARY_CALENDAR_PROMPT: Final[str] = (
    "Summarize what happened today in my calendar - list completed events and meetings from today only"
)

DIARY_WEATHER_PROMPT: Final[str] = "What was the weather like today? Provide a brief summary."


async def generate_diary_entry(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate and send a daily diary entry.

    Args:
        context: Telegram context containing job and bot information
    """
    log: structlog.BoundLogger = structlog.get_logger()
    log.info("Generating daily diary entry")

    job = context.job
    if not job:
        log.error("Job is missing")
        return

    job_data = job.data
    if not job_data:
        log.error("Job data is missing")
        return

    chat_id: int | None = job.chat_id
    if not chat_id:
        log.error("Chat ID is missing")
        return

    settings: Settings = job_data.__getattribute__("settings")
    genai_client: genai.Client = job_data.__getattribute__("genai_client")

    settings.logger.info("Starting diary entry generation")

    # Get current date and time
    now = datetime.datetime.now(settings.timezone)
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")

    mcps: MCPConfigReader = MCPConfigReader(settings)
    mcps.reload_config()

    # Fetch calendar data for context
    calendar_data: str | None = None
    if hasattr(settings, 'agenda_mcp_calendar_name') and settings.agenda_mcp_calendar_name:
        calendar_mcp_config: MCPConfiguration | None = mcps.get_mcp_configuration(settings.agenda_mcp_calendar_name)
        if calendar_mcp_config:
            try:
                server_params = await calendar_mcp_config.get_server_params()
                calendar_mcp: MCPClient = MCPClient(
                    name=calendar_mcp_config.name,
                    server_params=server_params,
                    logger=settings.logger,
                )
                calendar_data = await calendar_mcp.get_response(settings=settings, prompt=DIARY_CALENDAR_PROMPT)
                settings.logger.info(f"Calendar data fetched for diary: {calendar_data}")
            except Exception as e:
                settings.logger.error(f"Failed to fetch calendar data: {e}")
                calendar_data = None
        else:
            settings.logger.warning("Calendar MCP configuration not found for diary")

    # Fetch weather data for context
    weather_data: str | None = None
    if hasattr(settings, 'agenda_mcp_weather_name') and settings.agenda_mcp_weather_name:
        weather_mcp_config: MCPConfiguration | None = mcps.get_mcp_configuration(settings.agenda_mcp_weather_name)
        if weather_mcp_config:
            try:
                server_params = await weather_mcp_config.get_server_params()
                weather_mcp: MCPClient = MCPClient(
                    name=weather_mcp_config.name,
                    server_params=server_params,
                    logger=settings.logger,
                )
                weather_data = await weather_mcp.get_response(settings=settings, prompt=DIARY_WEATHER_PROMPT)
                settings.logger.info(f"Weather data fetched for diary: {weather_data}")
            except Exception as e:
                settings.logger.error(f"Failed to fetch weather data: {e}")
                weather_data = None
        else:
            settings.logger.warning("Weather MCP configuration not found for diary")

    # Create the diary prompt
    prompt: str = DIARY_PROMPT_TEMPLATE.format(
        date=date_str,
        time=time_str,
        calendar_data=calendar_data or "No calendar events recorded for today",
        weather_data=weather_data or "No weather information available"
    )

    settings.logger.info(f"Diary prompt created for {date_str}")

    try:
        # Generate diary entry using AI
        response = await genai_client.aio.models.generate_content(
            model=settings.model_name,
            contents=cast(list[str | Image.Image | Any | Any], [prompt]),
            config=settings.genconfig,
        )

        diary_text: str | None = response.text
        if not diary_text:
            settings.logger.error("Empty response from AI when generating diary entry")
            raise ValueError("Empty response from AI")

        # Format the final diary entry with a header
        diary_entry = f"# Diary Entry - {date_str}\n\n{diary_text}"

        settings.logger.info(f"Diary entry generated successfully for {date_str}")

        # Send the diary entry
        await context.bot.send_message(
            chat_id=chat_id,
            text=diary_entry,
            parse_mode="Markdown"
        )

        settings.logger.info("Daily diary entry sent successfully")

    except Exception as e:
        settings.logger.error(f"Error generating diary entry: {e}")

        # Send error message to user
        error_message = f"Sorry, I couldn't generate your diary entry for {date_str}. Please check the logs for more details."
        await context.bot.send_message(chat_id=chat_id, text=error_message)
