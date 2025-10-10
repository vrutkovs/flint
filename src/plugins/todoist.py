"""Todoist plugin for syncing tasks to Obsidian notes."""

import asyncio
from dataclasses import dataclass

import structlog
from telegram.ext import ContextTypes

from telega.settings import Settings
from utils.todoist import (
    ExportConfig,
    TodoistAPIError,
    TodoistClient,
    export_tasks_internal,
    todoist_available,
)


@dataclass
class TodoistData:
    """Data class for Todoist sync job."""

    settings: Settings
    api_token: str
    export_config: ExportConfig


async def sync_todoist_tasks(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sync Todoist tasks to notes."""
    log: structlog.BoundLogger = structlog.get_logger()
    log.info("Starting Todoist sync")

    if not todoist_available:
        log.error("todoist-api-python library is not available")
        return

    job = context.job
    if not job or not job.data:
        log.error("Job or job data is missing")
        return

    chat_id: int | None = job.chat_id
    if not chat_id:
        log.error("Chat ID is missing")
        return

    job_data = job.data
    if not isinstance(job_data, TodoistData):
        log.error("Invalid job data type")
        return
    settings = job_data.settings
    api_token = job_data.api_token
    export_config = job_data.export_config

    settings.logger.info("Syncing Todoist tasks to notes")

    try:
        # Initialize client
        client = TodoistClient(api_token)

        # Export tasks
        exported_count = await asyncio.get_event_loop().run_in_executor(
            None,
            export_tasks_internal,
            client,
            export_config,
            None,  # project_id
            None,  # project_name
            None,  # filter_expr
            True,  # include_completed
        )

        settings.logger.info(f"Todoist sync completed: {exported_count} tasks exported")

    except TodoistAPIError as e:
        settings.logger.error(f"Todoist API error during sync: {e}")
        await settings.send_message(context.bot, chat_id, f"❌ Todoist sync failed: {e}")
    except Exception as e:
        settings.logger.error(f"Unexpected error during Todoist sync: {e}")
        await settings.send_message(context.bot, chat_id, f"❌ Todoist sync failed: {e}")
