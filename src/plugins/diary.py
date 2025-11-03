"""Diary plugin for generating daily diary entries in markdown format."""

import datetime
from pathlib import Path
from typing import Final

import structlog
from google import genai
from telegram.ext import ContextTypes

from plugins.mcp import MCPClient, MCPConfigReader, MCPConfiguration
from telega.settings import Settings
from utils.file_operations import ensure_directory_exists
from utils.obsidian import read_obsidian_file, replace_diary_section, write_obsidian_file
from utils.todoist import scan_todoist_comments_for_today, scan_todoist_completed_tasks_today


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

### Completed tasks
{tasks_done}{in_progress_section}
"""

DIARY_TEMPLATE_WITH_IN_PROGRESS: Final[str] = """

### In progress
{tasks_in_progress}"""

DIARY_CALENDAR_PROMPT: Final[str] = """
Summarize what happened {date} in my calendar - list completed events and meetings from today only.
Output them in format:
* <time> - <short one sentence description of the event>

Use only 24 hours format for time. Convert all times to Europe/Prague timezone, don't show any timezone indicators.
IT IS VITAL NOT TO INCLUDE ANY OTHER INFORMATION OR LINES EXCEPT THE LIST OF EVENTS AND MEETINGS.
"""


async def fetch_calendar_data(settings: Settings, mcps: MCPConfigReader, target_date: datetime.date) -> str | None:
    """Fetch calendar data using MCP client.

    Args:
        settings: Settings object containing configuration
        mcps: MCP configuration reader
        target_date: Date for which to fetch calendar data

    Returns:
        Calendar data string or None if not available
    """
    if not (hasattr(settings, "agenda_mcp_calendar_name") and settings.agenda_mcp_calendar_name):
        settings.logger.info("Calendar MCP not configured, skipping calendar data")
        return None

    calendar_mcp_config: MCPConfiguration | None = mcps.get_mcp_configuration(settings.agenda_mcp_calendar_name)
    if not calendar_mcp_config:
        settings.logger.warning("Calendar MCP configuration not found for diary")
        return None

    try:
        server_params = await calendar_mcp_config.get_server_params()
        calendar_mcp: MCPClient = MCPClient(
            name=calendar_mcp_config.name,
            server_params=server_params,
            logger=settings.logger,
        )
        prompt = DIARY_CALENDAR_PROMPT.format(date=target_date.strftime("%Y-%m-%d"))
        calendar_data = await calendar_mcp.get_response(settings=settings, prompt=prompt)
        settings.logger.info("Calendar data fetched for diary")
        return calendar_data
    except Exception as e:
        settings.logger.error(f"Failed to fetch calendar data: {e}")
        return None


def fetch_completed_tasks_data(settings: Settings, today: datetime.date) -> str | None:
    """Fetch completed tasks data from Todoist folder.

    Args:
        settings: Settings object containing configuration
        today: Today's date

    Returns:
        Completed tasks data string or None if not available
    """
    if not settings.todoist_notes_folder:
        settings.logger.info("todoist_notes_folder not configured, skipping completed tasks data")
        return None

    try:
        tasks_done = scan_todoist_completed_tasks_today(settings.todoist_notes_folder, today)
        settings.logger.info("Todoist completed tasks scanned from folder")
        return tasks_done
    except Exception as e:
        settings.logger.error(f"Failed to scan Todoist folder for completed tasks: {e}")
        return None


def fetch_in_progress_tasks_data(settings: Settings, today: datetime.date) -> str:
    """Fetch in-progress tasks data from Todoist folder.

    Args:
        settings: Settings object containing configuration
        today: Today's date

    Returns:
        Formatted in-progress section string (empty if not available)
    """
    if not settings.todoist_notes_folder:
        settings.logger.info("todoist_notes_folder not configured, skipping in-progress tasks data")
        return ""

    try:
        tasks_in_progress = scan_todoist_comments_for_today(settings.todoist_notes_folder, today)
        settings.logger.info("Todoist in-progress data scanned from folder")
        return DIARY_TEMPLATE_WITH_IN_PROGRESS.format(
            tasks_in_progress=tasks_in_progress or "No tasks in progress today"
        )
    except Exception as e:
        settings.logger.error(f"Failed to scan Todoist folder for in-progress data: {e}")
        return ""


def create_diary_content(calendar_data: str | None, tasks_done: str | None, in_progress_section: str) -> str:
    """Create diary entry content from components.

    Args:
        calendar_data: Calendar events data
        tasks_done: Completed tasks data
        in_progress_section: In-progress tasks section

    Returns:
        Formatted diary entry content
    """
    return DIARY_TEMPLATE.format(
        calendar_data=calendar_data or "No calendar events recorded for today",
        tasks_done=tasks_done or "No tasks completed today",
        in_progress_section=in_progress_section,
    )


def get_daily_note_file_path(settings: Settings, date_str: str) -> Path | None:
    """Get the file path for the daily note.

    Args:
        settings: Settings object containing configuration
        date_str: Date string in YYYY-MM-DD format

    Returns:
        Path to daily note file or None if configuration is missing
    """
    if not settings.daily_note_folder:
        settings.logger.error("DAILY_NOTE_FOLDER is not configured in settings")
        return None

    notes_path = Path(settings.daily_note_folder)
    if not ensure_directory_exists(notes_path):
        settings.logger.error(f"Failed to create daily notes directory: {notes_path}")
        return None

    filename = f"{date_str}.md"
    return notes_path / filename


def update_daily_note_file(file_path: Path, diary_entry: str, logger: structlog.BoundLogger) -> bool:
    """Update daily note file with diary entry.

    Args:
        file_path: Path to the daily note file
        diary_entry: Diary entry content
        logger: Logger instance

    Returns:
        True if update was successful, False otherwise
    """
    # Read existing file content if it exists
    existing_content = ""
    if file_path.exists():
        content = read_obsidian_file(file_path)
        if content is None:
            logger.error(f"Failed to read existing file {file_path}")
            return False
        existing_content = content

    # Replace or add diary section
    updated_content = replace_diary_section(existing_content, diary_entry)

    # Write the updated content to the file
    if write_obsidian_file(file_path, updated_content):
        logger.info(f"Daily diary entry written to {file_path}")
        return True
    else:
        logger.error(f"Failed to write diary entry to file: {file_path}")
        return False


async def generate_diary_entry(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate and send a daily diary entry.

    Args:
        context: Telegram context containing job and bot information
    """
    log: structlog.BoundLogger = structlog.get_logger()
    log.info("Generating daily diary entry")

    # Validate job context
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
    settings.logger.info("Starting diary entry generation")

    # Get current date and time
    today = datetime.datetime.today()
    date_str = today.strftime("%Y-%m-%d")

    # Initialize MCP configuration
    mcps: MCPConfigReader = MCPConfigReader(settings)
    mcps.reload_config()

    # Fetch all diary components
    calendar_data = await fetch_calendar_data(settings, mcps, today)
    tasks_done = fetch_completed_tasks_data(settings, today)
    in_progress_section = fetch_in_progress_tasks_data(settings, today)

    # Create diary entry content
    diary_entry = create_diary_content(calendar_data, tasks_done, in_progress_section)
    settings.logger.info("Diary entry created")

    # Get file path for daily note
    file_path = get_daily_note_file_path(settings, date_str)
    if not file_path:
        return

    # Update the daily note file
    update_daily_note_file(file_path, diary_entry, settings.logger)
