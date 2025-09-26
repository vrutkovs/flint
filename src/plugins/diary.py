"""Diary plugin for generating daily diary entries in markdown format."""

import datetime
from pathlib import Path
from typing import Final

import structlog
from google import genai
from telegram.ext import ContextTypes

from plugins.mcp import (
    MCPClient,
    MCPConfigReader,
    MCPConfiguration,
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


DIARY_TEMPLATE: Final[str] = """## Diary

### Events
{calendar_data}

### Tasks
{tasks_done}
"""

DIARY_CALENDAR_PROMPT: Final[str] = """
Summarize what happened today in my calendar - list completed events and meetings from today only.
Output them in format:
* <time> - <short one sentence description of the event>
"""

DIARY_TODOIST_PROMPT: Final[str] = """
What tasks did I complete today? List the tasks I finished today with a brief summary. Format:
* <time when completed> - <short one sentence description of the task>
"""


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
    else:
        settings.logger.info("Calendar MCP not configured, skipping calendar data")

    # Fetch tasks done data for context
    tasks_done: str | None = None
    if hasattr(settings, 'agenda_mcp_todoist_name') and settings.agenda_mcp_todoist_name:
        todoist_mcp_config: MCPConfiguration | None = mcps.get_mcp_configuration(settings.agenda_mcp_todoist_name)
        if todoist_mcp_config:
            try:
                server_params = await todoist_mcp_config.get_server_params()
                todoist_mcp: MCPClient = MCPClient(
                    name=todoist_mcp_config.name,
                    server_params=server_params,
                    logger=settings.logger,
                )
                tasks_done = await todoist_mcp.get_response(settings=settings, prompt=DIARY_TODOIST_PROMPT)
                settings.logger.info(f"Todoist data fetched for diary: {tasks_done}")
            except Exception as e:
                settings.logger.error(f"Failed to fetch Todoist data: {e}")
                tasks_done = None
        else:
            settings.logger.warning("Todoist MCP configuration not found for diary")
    else:
        settings.logger.info("Todoist MCP not configured, skipping tasks data")

    # Create the diary entry
    diary_entry: str = DIARY_TEMPLATE.format(
        date=date_str,
        calendar_data=calendar_data or "No calendar events recorded for today",
        tasks_done=tasks_done or "No tasks completed today"
    )

    settings.logger.info("Diary entry created")

    # Get the daily notes folder from settings
    daily_note_folder: str | None = settings.daily_note_folder
    if not daily_note_folder:
        settings.logger.error("DAILY_NOTE_FOLDER is not configured in settings")
        return

    # Create the daily notes directory if it doesn't exist
    notes_path: Path = Path(daily_note_folder)
    try:
        notes_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        settings.logger.error(f"Failed to create daily notes directory: {e}")
        return

    # Create the filename using current date
    filename: str = f"{date_str}.md"
    file_path: Path = notes_path / filename

    # Write the diary entry to the file
    try:
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(diary_entry)

        settings.logger.info(f"Daily diary entry written to {file_path}")

    except Exception as e:
        settings.logger.error(f"Failed to write diary entry to file: {e}")
        return
