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


class ScheduleData:
    def __init__(self, settings: Settings, genai_client: genai.Client) -> None:
        self.settings: Settings = settings
        self.genai_client: genai.Client = genai_client


PROMPT_TEMPLATE: Final[str] = """
You are a helpful digital assistant.

Your primary role is to provide a daily briefing.

Organize the information clearly. Use emojis if they genuinely enhance the
message and fit your adopted persona.

If there's no information for a section, acknowledge its absence in
character.

Avoid using markdown formatting. Use extra whitelines and line breaks to enhance readability.

Its important to mention unusual weather conditions. Condense weather data into no more than three sentences.

Condense calendar data into a list, no more than three sentences.

Good morning! Here is your morning briefing.

Weather Update:
    {weather_data}

Upcoming Calendar Events (next 24 hours):
    {calendar_data}

Please synthesize this into a single, coherent message, adhering to your
persona. If a section is empty or explicitly states no information,
acknowledge it cheerfully or omit it gracefully.
"""

CALENDAR_MCP_PROMPT: Final[str] = (
    "List upcoming calendar events today. Use 24h time and DD-MM-YYYY formats, remove any date and timezone markers from the output. Output a single list with events sorted by start time"
)
WEATHER_MCP_PROMPT: Final[str] = "What is the weather like in Brno today?"


async def send_agenda(context: ContextTypes.DEFAULT_TYPE) -> None:
    log: structlog.BoundLogger = structlog.get_logger()
    log.info("Sending agenda")

    job = context.job
    if not job:
        print("Job is missing")
        return
    job_data = job.data
    if not job_data:
        print("Job data is missing")
        return
    chat_id: int | None = job.chat_id
    if not chat_id:
        print("Chat ID is missing")
        return

    settings: Settings = job_data.__getattribute__("settings")
    genai_client: genai.Client = job_data.__getattribute__("genai_client")

    settings.logger.info("Generating agenda")

    mcps: MCPConfigReader = MCPConfigReader(settings)
    mcps.reload_config()

    weather_data: str | None = None
    weather_mcp_config: MCPConfiguration | None = mcps.get_mcp_configuration(settings.agenda_mcp_weather_name)
    if not weather_mcp_config:
        settings.logger.error("Weather MCP configuration not found")
        weather_data = None
    else:
        server_params: StdioServerParameters = await weather_mcp_config.get_server_params()
        weather_mcp: MCPClient = MCPClient(
            name=weather_mcp_config.name,
            server_params=server_params,
            logger=settings.logger,
        )
        if weather_mcp is None:
            pass
        else:
            weather_data = await weather_mcp.get_response(settings=settings, prompt=WEATHER_MCP_PROMPT)
    settings.logger.info(f"Weather data fetched: {weather_data}")

    calendar_data: str | None = None
    if hasattr(settings, "agenda_mcp_calendar_name") and settings.agenda_mcp_calendar_name:
        calendar_mcp_config: MCPConfiguration | None = mcps.get_mcp_configuration(settings.agenda_mcp_calendar_name)
        if not calendar_mcp_config:
            settings.logger.error("Calendar MCP configuration not found")
            calendar_data = None
        else:
            server_params = await calendar_mcp_config.get_server_params()
            calendar_mcp: MCPClient = MCPClient(
                name=calendar_mcp_config.name,
                server_params=server_params,
                logger=settings.logger,
            )
            if calendar_mcp is None:
                pass
            else:
                calendar_data = await calendar_mcp.get_response(settings=settings, prompt=CALENDAR_MCP_PROMPT)
        settings.logger.info(f"Calendar data fetched: {calendar_data}")
    else:
        settings.logger.info("Calendar MCP not configured, skipping calendar data")

    prompt: str = PROMPT_TEMPLATE.format(
        weather_data=weather_data or "No weather data available",
        calendar_data=calendar_data or "No calendar events scheduled for today",
    )
    settings.logger.info(f"Prompt sent:\n{prompt}")

    response = await genai_client.aio.models.generate_content(
        model=settings.model_name,
        contents=cast(list[str | Image.Image | Any | Any], [prompt]),
        config=settings.genconfig,
    )
    text: str | None = response.text
    if not text:
        settings.logger.error("Empty response from AI when generating agenda")
        raise ValueError("Empty response from AI")

    settings.logger.info(f"Agenda prepared:\n{text}")
    await settings.send_message(context.bot, chat_id, text)
