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

Use only 24 hours format for time. Convert all times to Europe/Prague timezone, don't show any timezone indicators.
IT IS VITAL NOT TO INCLUDE ANY OTHER INFORMATION OR LINES EXCEPT THE LIST OF EVENTS AND MEETINGS.
"""

DIARY_TODOIST_PROMPT: Final[str] = """
What tasks did I complete today? List the tasks I finished today with a brief summary. Format:
* [x] <short one sentence description of the task> ✅ <date in YYYY-MM-DD format>

IT IS VITAL NOT TO INCLUDE ANY OTHER INFORMATION OR LINES EXCEPT THE LIST OF COMPLETED TASKS.
"""


def replace_diary_section(existing_content: str, new_diary_section: str) -> str:
    """Replace existing diary section with new content.

    Args:
        existing_content: Current file content
        new_diary_section: New diary section to insert

    Returns:
        Updated file content with diary section replaced
    """
    if not existing_content.strip():
        return new_diary_section.strip()

    # Split content by lines to work with sections
    lines = existing_content.split("\n")
    result_lines = []
    in_diary_section = False
    diary_section_found = False

    for line in lines:
        if line.strip() == "## Diary":
            # Start of diary section - replace with new content
            diary_section_found = True
            in_diary_section = True
            result_lines.extend(new_diary_section.strip().split("\n"))
        elif in_diary_section and line.startswith("## "):
            # End of diary section, start of new section
            in_diary_section = False
            result_lines.append("")  # Add blank line before next section
            result_lines.append(line)
        elif not in_diary_section:
            # Not in diary section, keep the line
            result_lines.append(line)
        # Skip lines that are in diary section (they get replaced)

    if not diary_section_found:
        # No diary section found, append to end
        result_lines.extend(["", new_diary_section.strip()])

    return "\n".join(result_lines)


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

    settings.logger.info("Starting diary entry generation")

    # Get current date and time
    now = datetime.datetime.now(settings.timezone)
    date_str = now.strftime("%Y-%m-%d")

    mcps: MCPConfigReader = MCPConfigReader(settings)
    mcps.reload_config()

    # Fetch calendar data for context
    calendar_data: str | None = None
    if hasattr(settings, "agenda_mcp_calendar_name") and settings.agenda_mcp_calendar_name:
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
    if hasattr(settings, "agenda_mcp_todoist_name") and settings.agenda_mcp_todoist_name:
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
        calendar_data=calendar_data or "No calendar events recorded for today",
        tasks_done=tasks_done or "No tasks completed today",
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

    # Read existing file content if it exists
    existing_content: str = ""
    if file_path.exists():
        try:
            with open(file_path, encoding="utf-8") as file:
                existing_content = file.read()
        except Exception as e:
            settings.logger.error(f"Failed to read existing file {file_path}: {e}")
            return

    # Replace or add diary section
    updated_content = replace_diary_section(existing_content, diary_entry)

    # Write the updated content to the file
    try:
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(updated_content)

        settings.logger.info(f"Daily diary entry written to {file_path}")
    except Exception as e:
        settings.logger.error(f"Failed to write diary entry to file: {e}")
    return
