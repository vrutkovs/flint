#!/usr/bin/env python3
"""
Flint CLI - Command Line Interface for Flint Bot Operations

This module provides convenient command-line access to Flint's functionality,
including diary generation, without needing to run the full bot.

Usage:
    python -m cli diary [options]
    python -m cli --help

Examples:
    python -m cli diary                       # Generate diary for today
    python -m cli diary --date 2024-01-15    # Generate for specific date
    python -m cli diary --yesterday          # Generate for yesterday
    python -m cli diary --force              # Force overwrite existing entry
    python -m cli diary --dry-run            # Preview without saving

Requirements:
    - All environment variables must be configured as per main bot
    - DAILY_NOTE_FOLDER must be set for diary generation
    - Optional: MCP_CALENDAR_NAME and MCP_TODOIST_NAME for full functionality
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

from plugins.diary import (
    create_diary_content,
    fetch_calendar_data,
    fetch_completed_tasks_data,
    fetch_in_progress_tasks_data,
    get_daily_note_file_path,
    update_daily_note_file,
)
from plugins.mcp import MCPConfigReader
from telega.settings import Settings
from utils.todoist import ExportConfig, TodoistAPIError, TodoistClient, export_tasks_internal

# Load environment variables
print("Loading environment variables...")
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


def validate_environment() -> Settings:
    """
    Validate required environment variables and create settings.

    Returns:
        Settings object configured from environment

    Raises:
        SystemExit: If required environment variables are missing
    """
    required_vars = {
        "GOOGLE_API_KEY": "Google API key for AI functionality",
        "MODEL_NAME": "AI model name to use",
        "MCP_CONFIG_PATH": "Path to MCP configuration file",
        "DAILY_NOTE_FOLDER": "Directory where diary files will be saved",
        "TODOIST_API_TOKEN": "Todoist API token for task management",
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
    log.info(f"MCP Calendar Name: {mcp_calendar_name}")
    mcp_todoist_name = os.getenv("MCP_TODOIST_NAME", "")
    mcp_weather_name = os.getenv("MCP_WEATHER_NAME", "")
    todoist_notes_folder = os.getenv("TODOIST_NOTES_FOLDER", "")
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
        chat_id="cli_tool",  # Placeholder for CLI usage
        mcp_config_path=mcp_config_path,
        mcp_calendar_name=mcp_calendar_name,
        mcp_todoist_name=mcp_todoist_name,
        mcp_weather_name=mcp_weather_name,
        user_filter=[],
        system_instructions=system_instructions,
        daily_note_folder=daily_note_folder,
        todoist_notes_folder=todoist_notes_folder,
        rag_embedding_model=None,
        rag_location=None,
        rag_vector_storage=None,
        google_api_key=api_key,
    )

    return settings


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


def determine_target_date(args: argparse.Namespace) -> datetime.date:
    """
    Determine the target date based on command arguments.

    Args:
        args: Parsed command line arguments

    Returns:
        Target date for diary generation

    Raises:
        ValueError: If date format is invalid
        SystemExit: If conflicting date options provided
    """
    date_options = sum([bool(args.date), args.yesterday, args.today])
    if date_options > 1:
        log.error("Please specify only one date option: --date, --yesterday, or --today")
        sys.exit(1)

    if args.yesterday:
        target_date = datetime.date.today() - datetime.timedelta(days=1)
        log.info(f"Using yesterday's date: {target_date}")
    elif args.today:
        target_date = datetime.date.today()
        log.info(f"Using today's date: {target_date}")
    elif args.date:
        target_date = parse_date_string(args.date)
        log.info(f"Using specified date: {target_date}")
    else:
        # Default to today
        target_date = datetime.date.today()
        log.info(f"Using default date (today): {target_date}")

    return target_date


def check_existing_file(file_path: Path, force: bool, dry_run: bool) -> bool:
    """
    Check if diary file already exists and handle accordingly.

    Args:
        file_path: Path to diary file
        force: Whether to force overwrite
        dry_run: Whether this is a dry run

    Returns:
        True if we should proceed, False otherwise
    """
    if file_path.exists() and not force and not dry_run:
        log.warning(f"Diary entry already exists: {file_path}")
        log.info("Use --force to overwrite or --dry-run to preview")
        return False
    return True


async def generate_diary_content(
    settings: Settings, target_date: datetime.date, skip_calendar: bool, skip_tasks: bool
) -> str:
    """
    Generate diary content by fetching data from various sources.

    Args:
        settings: Settings object with configuration
        target_date: Date to generate diary for
        skip_calendar: Whether to skip calendar data
        skip_tasks: Whether to skip task data

    Returns:
        Generated diary content string
    """
    # Initialize MCP configuration
    mcps = MCPConfigReader(settings)
    mcps.reload_config()

    # Fetch calendar data
    calendar_data = None
    if not skip_calendar:
        log.info("Fetching calendar data...")
        calendar_data = await fetch_calendar_data(settings, mcps, target_date)
        if calendar_data:
            log.info("Calendar data fetched successfully")
        else:
            log.warning("No calendar data available")

    # Fetch tasks data
    tasks_done = None
    in_progress_section = ""
    if not skip_tasks:
        log.info("Fetching completed tasks data...")
        tasks_done = fetch_completed_tasks_data(settings, target_date)
        if tasks_done:
            log.info("Completed tasks data fetched successfully")

        log.info("Fetching in-progress tasks data...")
        in_progress_section = fetch_in_progress_tasks_data(settings, target_date)
        if in_progress_section:
            log.info("In-progress tasks data fetched successfully")

    # Create diary entry content
    return create_diary_content(calendar_data, tasks_done, in_progress_section)


def preview_diary_content(target_date: datetime.date, diary_content: str, file_path: Path) -> None:
    """
    Preview diary content in dry-run mode.

    Args:
        target_date: Target date for the diary
        diary_content: Generated diary content
        file_path: Path where file would be saved
    """
    print("\n" + "=" * 60)
    print(f"DIARY PREVIEW - {target_date.strftime('%Y-%m-%d')}")
    print("=" * 60)
    print(diary_content)
    print("=" * 60)
    print(f"Would be saved to: {file_path}")
    print("Use --force to save this content to the file")


async def diary_command(args: argparse.Namespace) -> None:
    """
    Handle diary generation command.

    Args:
        args: Parsed command line arguments
    """
    log.info("Starting diary generation")

    # Validate environment and create settings
    settings = validate_environment()

    # Determine target date
    target_date = determine_target_date(args)

    # Get file path for diary entry
    file_path = get_daily_note_file_path(settings, target_date.strftime("%Y-%m-%d"))
    if not file_path:
        log.error("Failed to determine daily note file path")
        sys.exit(1)

    # Check if file exists and handle --force logic
    if not check_existing_file(file_path, args.force, args.dry_run):
        sys.exit(1)

    log.info(f"Generating diary entry for {target_date.strftime('%Y-%m-%d')}")

    # Generate diary content
    try:
        diary_content = await generate_diary_content(
            settings=settings,
            target_date=target_date,
            skip_calendar=args.no_calendar,
            skip_tasks=args.no_tasks,
        )
    except Exception as e:
        log.error(f"Failed to generate diary content: {e}")
        sys.exit(1)

    if args.dry_run:
        preview_diary_content(target_date, diary_content, file_path)
    else:
        # Save diary entry
        if update_daily_note_file(file_path, diary_content, settings.logger):
            log.info("Diary entry generated successfully!")
        else:
            log.error("Failed to save diary entry")
            sys.exit(1)


async def export_todoist_tasks_command(args: argparse.Namespace) -> None:
    """
    Handle Todoist tasks export command.

    Args:
        args: Parsed command line arguments
    """
    _ = validate_environment()
    log.info("Starting Todoist tasks export")

    token = os.getenv("TODOIST_API_TOKEN")
    if not token:
        log.error("Missing required environment variable: TODOIST_API_TOKEN")
        sys.exit(1)
    folder = os.getenv("TODOIST_NOTES_FOLDER")
    if not folder:
        log.error("Missing required environment variable: TODOIST_NOTES_FOLDER")
        sys.exit(1)

    try:
        client = TodoistClient(token)
        export_config = ExportConfig(Path(folder), include_completed=True, include_comments=True)

        exported_count = await asyncio.get_event_loop().run_in_executor(
            None,
            export_tasks_internal,
            client,
            export_config,
            args.project_id,
            args.project_name,
            args.filter_expr,
            args.include_completed,
        )
        log.info(f"Successfully exported {exported_count} Todoist tasks.")
    except TodoistAPIError as e:
        log.error(f"Todoist API Error: {e}")
        sys.exit(1)
    except Exception as e:
        log.error(f"An unexpected error occurred during Todoist export: {e}")
        sys.exit(1)


def create_parser() -> argparse.ArgumentParser:
    """
    Create the main argument parser.

    Returns:
        Configured argument parser
    """
    parser = argparse.ArgumentParser(
        description="Flint CLI - Command line interface for Flint bot operations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging (DEBUG level)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Diary subcommand
    diary_parser = subparsers.add_parser(
        "diary",
        help="Generate diary entries",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s diary                          Generate diary for today
  %(prog)s diary --date 2024-01-15       Generate for January 15, 2024
  %(prog)s diary --yesterday             Generate for yesterday
  %(prog)s diary --force --today         Force regenerate today's entry
  %(prog)s diary --dry-run --yesterday   Preview yesterday's entry
        """,
    )

    # Date selection (mutually exclusive)
    date_group = diary_parser.add_mutually_exclusive_group()
    date_group.add_argument(
        "--date",
        metavar="YYYY-MM-DD",
        help="Generate diary for specific date (YYYY-MM-DD format)",
    )
    date_group.add_argument(
        "--yesterday",
        action="store_true",
        help="Generate diary for yesterday",
    )
    date_group.add_argument(
        "--today",
        action="store_true",
        help="Generate diary for today (default)",
    )

    # Options
    diary_parser.add_argument(
        "--force",
        action="store_true",
        help="Force overwrite existing diary entry",
    )
    diary_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview diary content without saving to file",
    )
    diary_parser.add_argument(
        "--no-calendar",
        action="store_true",
        help="Skip calendar data (useful if calendar MCP is not configured)",
    )
    diary_parser.add_argument(
        "--no-tasks",
        action="store_true",
        help="Skip task data (useful if task management is not configured)",
    )

    # Todoist Export subcommand
    todoist_export_parser = subparsers.add_parser(
        "export-todoist-tasks",
        help="Manually export Todoist tasks to markdown files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s export-todoist-tasks                               Export all tasks
  %(prog)s export-todoist-tasks --project-name "My Project"   Export tasks from "My Project"
  %(prog)s export-todoist-tasks --filter-expr "today"         Export tasks due today
  %(prog)s export-todoist-tasks --include-completed           Include completed tasks in export
        """,
    )

    todoist_export_parser.add_argument(
        "--project-id",
        type=str,
        default=None,
        help="Filter tasks by Todoist project ID",
    )
    todoist_export_parser.add_argument(
        "--project-name",
        type=str,
        default=None,
        help="Filter tasks by Todoist project name",
    )
    todoist_export_parser.add_argument(
        "--filter-expr",
        type=str,
        default=None,
        help="Filter tasks by Todoist filter expression (e.g., 'today', 'p1')",
    )
    todoist_export_parser.add_argument(
        "--include-completed",
        action="store_true",
        help="Include completed tasks in the export",
    )

    return parser


async def main() -> None:
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()

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

    # Handle commands
    if args.command == "diary":
        await diary_command(args)
    elif args.command == "export-todoist-tasks":
        await export_todoist_tasks_command(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
