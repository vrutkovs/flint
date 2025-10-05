"""Tests for todoist plugin functionality."""

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import pytest
import structlog
from telegram.ext import ContextTypes

from plugins.todoist import TodoistData, sync_todoist_tasks
from telega.settings import Settings
from utils.todoist import ExportConfig, TodoistAPIError


@pytest.fixture
def mock_settings():
    """Create a mock Settings object."""
    settings = Mock(spec=Settings)
    settings.logger = structlog.get_logger()
    return settings


@pytest.fixture
def export_config():
    """Create a test export configuration."""
    with TemporaryDirectory() as temp_dir:
        yield ExportConfig(
            output_dir=Path(temp_dir), include_completed=False, include_comments=True, tag_prefix="todoist"
        )


@pytest.fixture
def todoist_data(mock_settings, export_config):
    """Create test TodoistData."""
    return TodoistData(settings=mock_settings, api_token="test-token", export_config=export_config)


@pytest.fixture
def mock_context():
    """Create a mock Telegram context."""
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot = Mock()

    # Create a mock job
    job = Mock()
    job.chat_id = 123456789
    job.data = None  # Will be set in individual tests
    context.job = job

    return context


class TestTodoistData:
    """Test TodoistData dataclass."""

    def test_todoist_data_creation(self, mock_settings, export_config):
        """Test TodoistData creation."""
        data = TodoistData(settings=mock_settings, api_token="test-token", export_config=export_config)

        assert data.settings == mock_settings
        assert data.api_token == "test-token"
        assert data.export_config == export_config


class TestSyncTodoistTasks:
    """Test sync_todoist_tasks function."""

    @pytest.mark.asyncio
    async def test_sync_todoist_tasks_library_unavailable(self, mock_context):
        """Test sync when todoist library is unavailable."""
        with patch("plugins.todoist.todoist_available", False):
            await sync_todoist_tasks(mock_context)

        # Should exit early without errors when library is not available

    @pytest.mark.asyncio
    async def test_sync_todoist_tasks_no_job(self):
        """Test sync when job is missing."""
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.job = None

        await sync_todoist_tasks(context)

        # Should handle missing job gracefully

    @pytest.mark.asyncio
    async def test_sync_todoist_tasks_no_job_data(self, mock_context):
        """Test sync when job data is missing."""
        mock_context.job.data = None

        await sync_todoist_tasks(mock_context)

        # Should handle missing job data gracefully

    @pytest.mark.asyncio
    async def test_sync_todoist_tasks_no_chat_id(self, mock_context, todoist_data):
        """Test sync when chat ID is missing."""
        mock_context.job.data = todoist_data
        mock_context.job.chat_id = None

        await sync_todoist_tasks(mock_context)

        # Should handle missing chat ID gracefully

    @pytest.mark.asyncio
    async def test_sync_todoist_tasks_invalid_job_data_type(self, mock_context):
        """Test sync when job data is not TodoistData type."""
        mock_context.job.data = "invalid-data-type"

        await sync_todoist_tasks(mock_context)

        # Should handle invalid job data type gracefully

    @pytest.mark.asyncio
    @patch("plugins.todoist.todoist_available", True)
    @patch("plugins.todoist.TodoistClient")
    @patch("plugins.todoist.export_tasks_internal")
    async def test_sync_todoist_tasks_success(self, mock_export_tasks, mock_client_class, mock_context, todoist_data):
        """Test successful sync."""
        mock_context.job.data = todoist_data

        # Mock the export function to return 5 exported tasks
        mock_export_tasks.return_value = 5

        # Mock the TodoistClient
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        # Run the sync in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()

        with patch("asyncio.get_event_loop", return_value=loop), patch.object(loop, "run_in_executor") as mock_executor:
            mock_executor.return_value = asyncio.Future()
            mock_executor.return_value.set_result(5)

            await sync_todoist_tasks(mock_context)

        # Verify that the client was created with correct token
        mock_client_class.assert_called_once_with("test-token")

        # Verify that export_tasks_internal was called
        mock_executor.assert_called_once()

    @pytest.mark.asyncio
    @patch("plugins.todoist.todoist_available", True)
    @patch("plugins.todoist.TodoistClient")
    async def test_sync_todoist_tasks_api_error(self, mock_client_class, mock_context, todoist_data):
        """Test sync with Todoist API error."""
        mock_context.job.data = todoist_data

        # Mock the client to raise TodoistAPIError
        mock_client_class.side_effect = TodoistAPIError("API Error")

        await sync_todoist_tasks(mock_context)

    @pytest.mark.asyncio
    @patch("plugins.todoist.todoist_available", True)
    @patch("plugins.todoist.TodoistClient")
    @patch("plugins.todoist.export_tasks_internal")
    async def test_sync_todoist_tasks_unexpected_error(
        self, mock_export_tasks, mock_client_class, mock_context, todoist_data
    ):
        """Test sync with unexpected error."""
        mock_context.job.data = todoist_data

        # Mock the export function to raise unexpected error
        loop = asyncio.get_event_loop()

        with patch("asyncio.get_event_loop", return_value=loop), patch.object(loop, "run_in_executor") as mock_executor:
            future = asyncio.Future()
            future.set_exception(Exception("Unexpected error"))
            mock_executor.return_value = future

            await sync_todoist_tasks(mock_context)

    @pytest.mark.asyncio
    @patch("plugins.todoist.todoist_available", True)
    @patch("plugins.todoist.TodoistClient")
    @patch("plugins.todoist.export_tasks_internal")
    async def test_sync_todoist_tasks_zero_exports(
        self, mock_export_tasks, mock_client_class, mock_context, todoist_data
    ):
        """Test sync when no tasks are exported."""
        mock_context.job.data = todoist_data

        # Mock the export function to return 0 exported tasks
        mock_export_tasks.return_value = 0

        loop = asyncio.get_event_loop()

        with patch("asyncio.get_event_loop", return_value=loop), patch.object(loop, "run_in_executor") as mock_executor:
            mock_executor.return_value = asyncio.Future()
            mock_executor.return_value.set_result(0)

            await sync_todoist_tasks(mock_context)

    @pytest.mark.asyncio
    @patch("plugins.todoist.todoist_available", True)
    @patch("plugins.todoist.TodoistClient")
    @patch("plugins.todoist.export_tasks_internal")
    async def test_sync_todoist_tasks_export_parameters(
        self, mock_export_tasks, mock_client_class, mock_context, todoist_data
    ):
        """Test that export_tasks_internal is called with correct parameters."""
        mock_context.job.data = todoist_data

        mock_export_tasks.return_value = 3
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        loop = asyncio.get_event_loop()

        with patch("asyncio.get_event_loop", return_value=loop), patch.object(loop, "run_in_executor") as mock_executor:
            mock_executor.return_value = asyncio.Future()
            mock_executor.return_value.set_result(3)

            await sync_todoist_tasks(mock_context)

        # Verify that run_in_executor was called with correct parameters
        mock_executor.assert_called_once()
        call_args = mock_executor.call_args

        # First argument should be None (default thread pool)
        assert call_args[0][0] is None

        # Second argument should be export_tasks_internal function
        # Note: We can't check __name__ on a mock, so we'll just verify it's callable
        assert callable(call_args[0][1])

        # Remaining arguments should be the parameters for export_tasks_internal
        args = call_args[0][2:]
        assert args[0] == mock_client  # client
        assert args[1] == todoist_data.export_config  # export_config
        assert args[2] is None  # project_id
        assert args[3] is None  # project_name
        assert args[4] is None  # filter_expr
        assert args[5] is False  # include_completed


class TestTodoistPluginIntegration:
    """Test integration between plugin components."""

    def test_import_all_components(self):
        """Test that all plugin components can be imported."""
        from plugins.todoist import TodoistData, sync_todoist_tasks
        from utils.todoist import (
            ExportConfig,
            TodoistClient,
            TodoistProject,
            TodoistTask,
            export_tasks_internal,
        )

        # Verify all components are available
        assert TodoistData is not None
        assert sync_todoist_tasks is not None
        assert ExportConfig is not None
        assert TodoistClient is not None
        assert TodoistProject is not None
        assert TodoistTask is not None
        assert export_tasks_internal is not None

    def test_plugin_main_import(self):
        """Test that main.py can import plugin components."""
        # This tests the import that main.py uses
        from plugins.todoist import ExportConfig, TodoistData, sync_todoist_tasks

        assert ExportConfig is not None
        assert TodoistData is not None
        assert sync_todoist_tasks is not None

    @patch("plugins.todoist.todoist_available", False)
    def test_graceful_handling_when_library_unavailable(self):
        """Test that plugin handles missing todoist library gracefully."""
        # Should be able to import even when library is not available
        from plugins.todoist import TodoistData, sync_todoist_tasks
        from utils.todoist import ExportConfig

        # Creating ExportConfig should work
        with TemporaryDirectory() as temp_dir:
            config = ExportConfig(output_dir=Path(temp_dir))
            assert config is not None

        # Creating TodoistData should work
        mock_settings = Mock()
        data = TodoistData(settings=mock_settings, api_token="test", export_config=config)
        assert data is not None

        # sync_todoist_tasks should be callable (though it will exit early)
        assert callable(sync_todoist_tasks)
