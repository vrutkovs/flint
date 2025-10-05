#!/usr/bin/env python3
"""
Manual Diary Update Script for Flint

This script allows manual generation/update of diary entries for specific dates.
It can be used to:
1. Generate a diary entry for a specific date
2. Update an existing diary entry
3. Regenerate diary entries for past dates

Usage:
    python scripts/update_diary.py [date] [options]

Examples:
    python scripts/update_diary.py                    # Generate for today
    python scripts/update_diary.py 2024-01-15        # Generate for specific date
    python scripts/update_diary.py --yesterday       # Generate for yesterday
    python scripts/update_diary.py --force 2024-01-15 # Force regenerate existing entry

Requirements:
    - Same environment variables as the main bot
    - DAILY_NOTE_FOLDER must be configured
    - MCP_CALENDAR_NAME and MCP_TODOIST_NAME should be configured for full functionality
"""

import argparse
import asyncio
import datetime
import os
import sys
from pathlib import Path
from typing import Final

import structlog
from dotenv import find_dotenv, load_dotenv
from google import genai

# Add src directory to path to import modules
current_dir = Path(__file__).parent
src_dir = current_dir.parent / "src"
sys.path.insert(0, str(src_dir))

from plugins.diary import (  # noqa: E402
    DIARY_CALENDAR_PROMPT,
    DIARY_TEMPLATE,
    replace_diary_section,
)
from plugins.mcp import MCPClient, MCPConfigReader  # noqa: E402
from telega.settings import Settings  # noqa: E402

# Load environment variables
load_dotenv(find_dotenv())

# Configure structured logging
structlog.configure(
    processors=[
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO level
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

log: structlog.BoundLogger = structlog.get_logger()

# Default system instructions for AI
DEFAULT_SYSTEM_INSTRUCTIONS: Final[str] = """
You are a helpful assistant for generating diary entries.
Organize the information clearly and concisely.
Focus on factual information about completed events and tasks.
"""


def validate_environment() -> tuple[Settings, genai.Client]:
    """
    Validate required environment variables and create settings.

    Returns:
        Tuple of Settings and GenAI client

    Raises:
        SystemExit: If required environment variables are missing
    """
    required_vars = {
        "GOOGLE_API_KEY": "Google API key for AI functionality",
        "MODEL_NAME": "AI model name to use",
        "MCP_CONFIG_PATH": "Path to MCP configuration file",
        "DAILY_NOTE_FOLDER": "Directory where diary files will be saved",
    }

    missing_vars = []
    for var, description in required_vars.items():
        if not os.getenv(var):
            missing_vars.append(f"  {var}: {description}")

    if missing_vars:
        log.error("Missing required environment variables:")
        for var in missing_vars:
            log.error(var)
        sys.exit(1)

    # Get required variables
    api_key = os.getenv("GOOGLE_API_KEY")
    model_name = os.getenv("MODEL_NAME", "")
    mcp_config_path = os.getenv("MCP_CONFIG_PATH", "")
    daily_note_folder = os.getenv("DAILY_NOTE_FOLDER")

    # Get optional variables
    mcp_calendar_name = os.getenv("MCP_CALENDAR_NAME", "")
    mcp_todoist_name = os.getenv("MCP_TODOIST_NAME", "")
    mcp_weather_name = os.getenv("MCP_WEATHER_NAME", "")
    tz = os.getenv("TZ", "UTC")
    system_instructions = os.getenv("SYSTEM_INSTRUCTIONS", DEFAULT_SYSTEM_INSTRUCTIONS)

    # Initialize GenAI client
    try:
        genai_client = genai.Client(api_key=api_key)
        log.info("GenAI client initialized successfully")
    except Exception as e:
        log.error("Failed to initialize GenAI client", error=str(e))
        sys.exit(1)

    # Create Settings instance
    settings = Settings(
        genai_client=genai_client,
        logger=log,
        model_name=model_name,
        chat_id="manual_script",  # Placeholder for script usage
        tz=tz,
        mcp_config_path=mcp_config_path,
        mcp_calendar_name=mcp_calendar_name,
        mcp_todoist_name=mcp_todoist_name,
        mcp_weather_name=mcp_weather_name,
        user_filter=[],
        system_instructions=system_instructions,
        daily_note_folder=daily_note_folder,
        rag_embedding_model=None,
        rag_location=None,
        rag_vector_storage=None,
        google_api_key=api_key,
    )

    return settings, genai_client


def parse_arguments() -> argparse.Namespace:
    """
    Parse command line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Manual diary update script for Flint",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                        Generate diary for today
  %(prog)s 2024-01-15             Generate diary for January 15, 2024
  %(prog)s --yesterday            Generate diary for yesterday
  %(prog)s --force 2024-01-15     Force regenerate existing diary entry
  %(prog)s --dry-run 2024-01-15   Preview diary content without saving
        """,
    )

    parser.add_argument("date", nargs="?", help="Date in YYYY-MM-DD format (default: today)")

    parser.add_argument("--yesterday", action="store_true", help="Generate diary for yesterday")

    parser.add_argument("--force", action="store_true", help="Force regenerate even if diary entry already exists")

    parser.add_argument("--dry-run", action="store_true", help="Preview diary content without saving to file")

    parser.add_argument(
        "--no-calendar", action="store_true", help="Skip calendar data (useful if calendar MCP is not configured)"
    )

    parser.add_argument(
        "--no-tasks", action="store_true", help="Skip task data (useful if Todoist MCP is not configured)"
    )

    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

    return parser.parse_args()


def parse_date_string(date_str: str) -> datetime.date:
    """
    Parse date string in YYYY-MM-DD format.

    Args:
        date_str: Date string to parse

    Returns:
        Parsed date object

    Raises:
        ValueError: If date format is invalid
    """
    try:
        return datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError as err:
        raise ValueError(f"Invalid date format: {date_str}. Expected YYYY-MM-DD") from err


async def fetch_calendar_data(settings: Settings, target_date: datetime.date) -> str | None:
    """
    Fetch calendar data for the specified date.

    Args:
        settings: Settings object with MCP configuration
        target_date: Date to fetch calendar data for

    Returns:
        Calendar data string or None if unavailable
    """
    if not settings.agenda_mcp_calendar_name:
        log.info("Calendar MCP not configured, skipping calendar data")
        return None

    mcps = MCPConfigReader(settings)
    mcps.reload_config()

    calendar_mcp_config = mcps.get_mcp_configuration(settings.agenda_mcp_calendar_name)
    if not calendar_mcp_config:
        log.warning("Calendar MCP configuration not found")
        return None

    try:
        server_params = await calendar_mcp_config.get_server_params()
        calendar_mcp = MCPClient(
            name=calendar_mcp_config.name,
            server_params=server_params,
            logger=settings.logger,
        )

        # Create date-specific prompt
        date_prompt = f"{DIARY_CALENDAR_PROMPT}\n\nFocus on events from {target_date.strftime('%Y-%m-%d')} only."

        calendar_data = await calendar_mcp.get_response(settings=settings, prompt=date_prompt)
        log.info("Calendar data fetched successfully")
        return calendar_data
    except Exception as e:
        log.error(f"Failed to fetch calendar data: {e}")
        return None


async def fetch_tasks_data(settings: Settings, target_date: datetime.date) -> str | None:
    """
    Fetch completed tasks data for the specified date.

    Args:
        settings: Settings object with MCP configuration
        target_date: Date to fetch tasks data for

    Returns:
        Tasks data string or None if unavailable
    """
    if not settings.agenda_mcp_todoist_name:
        log.info("Todoist MCP not configured, skipping tasks data")
        return None

    mcps = MCPConfigReader(settings)
    mcps.reload_config()

    todoist_mcp_config = mcps.get_mcp_configuration(settings.agenda_mcp_todoist_name)
    if not todoist_mcp_config:
        log.warning("Todoist MCP configuration not found")
        return None

    try:
        server_params = await todoist_mcp_config.get_server_params()
        todoist_mcp = MCPClient(
            name=todoist_mcp_config.name,
            server_params=server_params,
            logger=settings.logger,
        )

        # Create date-specific prompt
        date_prompt = f"Summarize tasks I completed today from Todoist - list only tasks completed today.\nFocus on tasks completed on {target_date.strftime('%Y-%m-%d')} only."

        tasks_data = await todoist_mcp.get_response(settings=settings, prompt=date_prompt)
        log.info("Tasks data fetched successfully")
        return tasks_data
    except Exception as e:
        log.error(f"Failed to fetch tasks data: {e}")
        return None


def create_diary_entry(calendar_data: str | None, tasks_data: str | None) -> str:
    """
    Create diary entry from fetched data.

    Args:
        calendar_data: Calendar events data
        tasks_data: Completed tasks data

    Returns:
        Formatted diary entry
    """
    return DIARY_TEMPLATE.format(
        calendar_data=calendar_data or "No calendar events recorded for this day",
        tasks_done=tasks_data or "No tasks completed on this day",
    )


def get_diary_file_path(settings: Settings, target_date: datetime.date) -> Path:
    """
    Get the file path for the diary entry.

    Args:
        settings: Settings object containing daily note folder
        target_date: Date for the diary entry

    Returns:
        Path to diary file
    """
    if settings.daily_note_folder is None:
        raise ValueError("daily_note_folder setting is required")
    notes_path = Path(settings.daily_note_folder)
    filename = f"{target_date.strftime('%Y-%m-%d')}.md"
    return notes_path / filename


def save_diary_entry(file_path: Path, diary_content: str, force: bool = False) -> bool:
    """
    Save diary entry to file.

    Args:
        file_path: Path where to save the diary
        diary_content: Diary content to save
        force: Whether to overwrite existing content

    Returns:
        True if saved successfully, False otherwise
    """
    # Create directory if it doesn't exist
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        log.error(f"Failed to create directory {file_path.parent}: {e}")
        return False

    # Check if file already exists and handle accordingly
    existing_content = ""
    if file_path.exists():
        if not force:
            log.warning(f"Diary file already exists: {file_path}")
            log.info("Use --force to overwrite existing entry")
            return False

        try:
            with open(file_path, encoding="utf-8") as file:
                existing_content = file.read()
        except Exception as e:
            log.error(f"Failed to read existing file {file_path}: {e}")
            return False

    # Replace or add diary section
    updated_content = replace_diary_section(existing_content, diary_content)

    # Write to file
    try:
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(updated_content)
        log.info(f"Diary entry saved to: {file_path}")
        return True
    except Exception as e:
        log.error(f"Failed to write diary entry to file: {e}")
        return False


async def main() -> None:
    """Main function to run the diary update script."""
    args = parse_arguments()

    # Configure verbose logging if requested
    if args.verbose:
        structlog.configure(
            processors=[
                structlog.dev.ConsoleRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(10),  # DEBUG level
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )

    log.info("Starting manual diary update script")

    # Validate environment and create settings
    try:
        settings, _ = validate_environment()
    except SystemExit:
        return

    # Determine target date
    if args.yesterday:
        target_date = datetime.date.today() - datetime.timedelta(days=1)
        log.info(f"Using yesterday's date: {target_date}")
    elif args.date:
        try:
            target_date = parse_date_string(args.date)
            log.info(f"Using specified date: {target_date}")
        except ValueError as e:
            log.error(str(e))
            sys.exit(1)
    else:
        target_date = datetime.date.today()
        log.info(f"Using today's date: {target_date}")

    # Get file path for diary entry
    file_path = get_diary_file_path(settings, target_date)

    # Check if file exists and handle --force logic
    if file_path.exists() and not args.force and not args.dry_run:
        log.warning(f"Diary entry already exists: {file_path}")
        log.info("Use --force to overwrite or --dry-run to preview")
        sys.exit(1)

    log.info(f"Generating diary entry for {target_date.strftime('%Y-%m-%d')}")

    # Fetch data from MCPs
    calendar_data = None
    tasks_data = None

    if not args.no_calendar:
        log.info("Fetching calendar data...")
        calendar_data = await fetch_calendar_data(settings, target_date)

    if not args.no_tasks:
        log.info("Fetching tasks data...")
        tasks_data = await fetch_tasks_data(settings, target_date)

    # Create diary entry
    diary_content = create_diary_entry(calendar_data, tasks_data)

    if args.dry_run:
        log.info("Dry run mode - previewing diary content:")
        print("\n" + "=" * 50)
        print(f"Diary entry for {target_date.strftime('%Y-%m-%d')}")
        print("=" * 50)
        print(diary_content)
        print("=" * 50)
        log.info(f"Would be saved to: {file_path}")
    else:
        # Save diary entry
        if save_diary_entry(file_path, diary_content, args.force):
            log.info("Diary entry generated successfully!")
        else:
            log.error("Failed to generate diary entry")
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
