"""Unit tests for the diary plugin."""

from unittest.mock import AsyncMock, Mock, patch
import datetime

import pytest
import pytz
from google import genai
from telegram.ext import ContextTypes

from plugins.mcp import MCPClient, MCPConfigReader, MCPConfiguration, StdioServerParameters
from plugins.diary import (
    DIARY_TEMPLATE,
    DIARY_CALENDAR_PROMPT,
    DIARY_TODOIST_PROMPT,
    DiaryData,
    generate_diary_entry,
)
from telega.settings import Settings


class TestDiaryData:
    """Test cases for the DiaryData class."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = Mock(spec=Settings)
        settings.logger = Mock()
        settings.timezone = pytz.timezone("Europe/Prague")
        settings.agenda_mcp_calendar_name = "calendar_mcp"
        settings.agenda_mcp_todoist_name = "todoist_mcp"
        settings.daily_note_folder = "/tmp/daily-notes"
        return settings

    @pytest.fixture
    def mock_genai_client(self):
        """Create mock GenAI client."""
        return Mock(spec=genai.Client)

    def test_diary_data_initialization(self, mock_settings, mock_genai_client):
        """Test DiaryData initialization."""
        diary_data = DiaryData(mock_settings, mock_genai_client)

        assert diary_data.settings == mock_settings
        assert diary_data.genai_client == mock_genai_client


class TestGenerateDiaryEntry:
    """Test cases for the generate_diary_entry function."""

    @pytest.fixture
    def mock_context(self):
        """Create mock context."""
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.bot = AsyncMock()
        context.bot.send_message = AsyncMock()
        context.job = Mock()
        context.job.data = Mock(spec=DiaryData)
        context.job.chat_id = 123456789
        return context

    @pytest.fixture
    def mock_diary_data(self, mock_settings, mock_genai_client):
        """Create mock DiaryData."""
        settings = mock_settings
        settings.agenda_mcp_calendar_name = "calendar_mcp"
        settings.agenda_mcp_todoist_name = "todoist_mcp"
        return DiaryData(settings, mock_genai_client)

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = Mock(spec=Settings)
        settings.logger = Mock()
        settings.timezone = pytz.timezone("Europe/Prague")
        settings.model_name = "gemini-pro"
        settings.genconfig = Mock()
        settings.agenda_mcp_calendar_name = "calendar_mcp"
        settings.agenda_mcp_todoist_name = "todoist_mcp"
        settings.mcp_config_path = "/mock/config/path"
        settings.daily_note_folder = "/tmp/daily-notes"
        return settings

    @pytest.fixture
    def mock_genai_client(self):
        """Create mock GenAI client."""
        return Mock(spec=genai.Client)

    @pytest.mark.asyncio
    @patch("builtins.open")
    @patch("plugins.diary.Path")
    @patch("plugins.diary.MCPConfigReader")
    @patch("plugins.diary.MCPClient")
    @patch("plugins.diary.datetime")
    async def test_generate_diary_entry_success(
        self, mock_datetime, mock_mcp_client_class, mock_mcp_reader_class, mock_path, mock_open, mock_context, mock_diary_data
    ):
        """Test successful diary entry generation."""
        # Setup context
        mock_context.job.data = mock_diary_data
        mock_context.job.chat_id = 123456789

        # Setup datetime mock
        mock_now = Mock()
        mock_now.strftime.side_effect = lambda fmt: {
            "%Y-%m-%d": "2024-01-15",
            "%H:%M": "23:59"
        }.get(fmt, "")
        mock_datetime.datetime.now.return_value = mock_now

        # Setup MCP reader
        mock_mcp_reader = Mock(spec=MCPConfigReader)
        mock_mcp_reader.reload_config = Mock()
        mock_mcp_reader.get_mcp_configuration = Mock()
        mock_mcp_reader_class.return_value = mock_mcp_reader

        # Setup calendar MCP
        mock_calendar_config = Mock(spec=MCPConfiguration)
        mock_calendar_config.name = "calendar_mcp"
        mock_calendar_config.get_server_params = AsyncMock(return_value=Mock(spec=StdioServerParameters))

        # Setup todoist MCP
        mock_todoist_config = Mock(spec=MCPConfiguration)
        mock_todoist_config.name = "todoist_mcp"
        mock_todoist_config.get_server_params = AsyncMock(return_value=Mock(spec=StdioServerParameters))

        # Configure MCP reader to return configurations
        def get_mcp_config(name):
            if name == "calendar_mcp":
                return mock_calendar_config
            elif name == "todoist_mcp":
                return mock_todoist_config
            return None

        mock_mcp_reader.get_mcp_configuration.side_effect = get_mcp_config

        # Setup MCP clients
        mock_calendar_mcp = Mock(spec=MCPClient)
        mock_calendar_mcp.get_response = AsyncMock(return_value="Meeting with team at 2 PM, completed project review")

        mock_todoist_mcp = Mock(spec=MCPClient)
        mock_todoist_mcp.get_response = AsyncMock(return_value="* 10:30 - Completed project documentation task")

        def mcp_client_factory(name, server_params, logger):
            if name == "calendar_mcp":
                return mock_calendar_mcp
            elif name == "todoist_mcp":
                return mock_todoist_mcp
            return Mock(spec=MCPClient)

        mock_mcp_client_class.side_effect = mcp_client_factory

        # Setup file path mocking
        mock_notes_path = Mock()
        mock_notes_path.mkdir = Mock()
        mock_notes_path.__truediv__ = Mock(return_value="/tmp/daily-notes/2024-01-15.md")
        mock_path.return_value = mock_notes_path

        # Setup file writing
        mock_file = Mock()
        mock_open.return_value.__enter__.return_value = mock_file

        # Execute
        await generate_diary_entry(mock_context)

        # Verify MCP interactions
        mock_calendar_mcp.get_response.assert_called_once_with(
            settings=mock_diary_data.settings,
            prompt=DIARY_CALENDAR_PROMPT
        )
        mock_todoist_mcp.get_response.assert_called_once_with(
            settings=mock_diary_data.settings,
            prompt=DIARY_TODOIST_PROMPT
        )

        # Verify directory creation
        mock_notes_path.mkdir.assert_called_once_with(parents=True, exist_ok=True)

        # Verify file was written
        mock_open.assert_called_once()
        mock_file.write.assert_called_once()
        written_content = mock_file.write.call_args[0][0]
        assert "# Daily Note - 2024-01-15" in written_content
        assert "Meeting with team at 2 PM" in written_content
        assert "10:30 - Completed project documentation" in written_content

        # Verify confirmation message was sent
        mock_context.bot.send_message.assert_called_once()
        call_args = mock_context.bot.send_message.call_args
        assert call_args[1]["chat_id"] == 123456789
        assert "Daily diary entry saved to" in call_args[1]["text"]
        assert call_args[1]["parse_mode"] == "Markdown"

    @pytest.mark.asyncio
    @patch("plugins.diary.MCPConfigReader")
    async def test_generate_diary_entry_missing_folder_setting(
        self, mock_mcp_reader_class, mock_context, mock_diary_data
    ):
        """Test diary generation when DAILY_NOTE_FOLDER is not set in settings."""
        mock_context.job.data = mock_diary_data
        mock_context.job.chat_id = 123456789

        # Setup MCP reader mock
        mock_mcp_reader = Mock(spec=MCPConfigReader)
        mock_mcp_reader.reload_config = Mock()
        mock_mcp_reader_class.return_value = mock_mcp_reader

        # Mock missing daily_note_folder in settings
        mock_diary_data.settings.daily_note_folder = None

        # Execute
        await generate_diary_entry(mock_context)

        # Verify error message was sent
        mock_context.bot.send_message.assert_called_once()
        call_args = mock_context.bot.send_message.call_args
        assert call_args[1]["chat_id"] == 123456789
        assert "DAILY_NOTE_FOLDER is not configured" in call_args[1]["text"]

    @pytest.mark.asyncio
    @patch("builtins.open")
    @patch("plugins.diary.Path")
    @patch("plugins.diary.MCPConfigReader")
    @patch("plugins.diary.MCPClient")
    @patch("plugins.diary.datetime")
    async def test_generate_diary_entry_no_mcp_config(
        self, mock_datetime, mock_mcp_client_class, mock_mcp_reader_class, mock_path, mock_open, mock_context, mock_diary_data
    ):
        """Test diary generation when MCP configurations are not available."""
        mock_context.job.data = mock_diary_data
        mock_context.job.chat_id = 123456789

        # Setup datetime mock
        mock_now = Mock()
        mock_now.strftime.side_effect = lambda fmt: {
            "%Y-%m-%d": "2024-01-15",
            "%H:%M": "23:59"
        }.get(fmt, "")
        mock_datetime.datetime.now.return_value = mock_now

        # Setup MCP reader to return None for configurations
        mock_mcp_reader = Mock(spec=MCPConfigReader)
        mock_mcp_reader.reload_config = Mock()
        mock_mcp_reader.get_mcp_configuration.return_value = None
        mock_mcp_reader_class.return_value = mock_mcp_reader

        # Setup file path mocking
        mock_notes_path = Mock()
        mock_notes_path.mkdir = Mock()
        mock_notes_path.__truediv__ = Mock(return_value="/tmp/daily-notes/2024-01-15.md")
        mock_path.return_value = mock_notes_path

        # Setup file writing
        mock_file = Mock()
        mock_open.return_value.__enter__.return_value = mock_file

        # Execute
        await generate_diary_entry(mock_context)

        # Verify warnings were logged
        mock_diary_data.settings.logger.warning.assert_called()

        # Verify file was written with no data placeholders
        mock_file.write.assert_called_once()
        written_content = mock_file.write.call_args[0][0]
        assert "# Daily Note - 2024-01-15" in written_content
        assert "No calendar events recorded for today" in written_content
        assert "No tasks completed today" in written_content

        # Verify confirmation message was sent
        mock_context.bot.send_message.assert_called_once()
        call_args = mock_context.bot.send_message.call_args
        assert call_args[1]["chat_id"] == 123456789
        assert "Daily diary entry saved to" in call_args[1]["text"]
        assert call_args[1]["parse_mode"] == "Markdown"

    @pytest.mark.asyncio
    async def test_generate_diary_entry_missing_job(self, mock_context):
        """Test diary generation when job is missing."""
        mock_context.job = None

        await generate_diary_entry(mock_context)

        # Verify no message was sent
        mock_context.bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_diary_entry_missing_job_data(self, mock_context):
        """Test diary generation when job data is missing."""
        mock_context.job.data = None

        await generate_diary_entry(mock_context)

        # Verify no message was sent
        mock_context.bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_diary_entry_missing_chat_id(self, mock_context):
        """Test diary generation when chat ID is missing."""
        mock_context.job.chat_id = None

        await generate_diary_entry(mock_context)

        # Verify no message was sent
        mock_context.bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    @patch("builtins.open")
    @patch("plugins.diary.Path")
    @patch("plugins.diary.MCPConfigReader")
    @patch("plugins.diary.datetime")
    async def test_generate_diary_entry_file_write_error(
        self, mock_datetime, mock_mcp_reader_class, mock_path, mock_open, mock_context, mock_diary_data
    ):
        """Test diary generation when file writing fails."""
        mock_context.job.data = mock_diary_data
        mock_context.job.chat_id = 123456789

        # Setup datetime mock
        mock_now = Mock()
        mock_now.strftime.side_effect = lambda fmt: {
            "%Y-%m-%d": "2024-01-15",
            "%H:%M": "23:59"
        }.get(fmt, "")
        mock_datetime.datetime.now.return_value = mock_now

        # Setup MCP reader
        mock_mcp_reader = Mock(spec=MCPConfigReader)
        mock_mcp_reader.reload_config = Mock()
        mock_mcp_reader.get_mcp_configuration.return_value = None
        mock_mcp_reader_class.return_value = mock_mcp_reader

        # Setup file path mocking
        mock_notes_path = Mock()
        mock_notes_path.mkdir = Mock()
        mock_notes_path.__truediv__ = Mock(return_value="/tmp/daily-notes/2024-01-15.md")
        mock_path.return_value = mock_notes_path

        # Setup file writing to fail
        mock_open.side_effect = IOError("Permission denied")

        # Execute
        await generate_diary_entry(mock_context)

        # Verify error was logged
        mock_diary_data.settings.logger.error.assert_called()

        # Verify error message was sent
        mock_context.bot.send_message.assert_called_once()
        call_args = mock_context.bot.send_message.call_args
        assert "Failed to write diary entry to file" in call_args[1]["text"]


def test_diary_template():
    """Test that the diary template contains required elements."""
    assert "{date}" in DIARY_TEMPLATE
    assert "{calendar_data}" in DIARY_TEMPLATE
    assert "{tasks_done}" in DIARY_TEMPLATE
    assert "## Events" in DIARY_TEMPLATE
    assert "## Tasks" in DIARY_TEMPLATE


def test_diary_prompts():
    """Test that diary prompts are properly defined."""
    assert DIARY_CALENDAR_PROMPT
    assert DIARY_TODOIST_PROMPT
    assert "calendar" in DIARY_CALENDAR_PROMPT.lower()
    assert "tasks" in DIARY_TODOIST_PROMPT.lower()
