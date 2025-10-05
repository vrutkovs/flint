"""Unit tests for the diary plugin."""

from unittest.mock import ANY, AsyncMock, Mock, patch

import pytest
import pytz
from google import genai
from telegram.ext import ContextTypes

from plugins.diary import (
    DIARY_CALENDAR_PROMPT,
    DIARY_TEMPLATE,
    DiaryData,
    generate_diary_entry,
    replace_diary_section,
)
from plugins.mcp import MCPClient, MCPConfigReader, MCPConfiguration, StdioServerParameters
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
        self,
        mock_datetime,
        mock_mcp_client_class,
        mock_mcp_reader_class,
        mock_path,
        mock_open,
        mock_context,
        mock_diary_data,
    ):
        """Test successful diary entry generation."""
        # Setup context
        mock_context.job.data = mock_diary_data
        mock_context.job.chat_id = 123456789

        # Setup datetime mock
        mock_now = Mock()
        mock_now.strftime.side_effect = lambda fmt: {"%Y-%m-%d": "2024-01-15", "%H:%M": "23:59"}.get(fmt, "")
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
        mock_file_path = Mock()
        mock_file_path.exists.return_value = False  # File doesn't exist initially
        mock_notes_path.__truediv__ = Mock(return_value=mock_file_path)
        mock_path.return_value = mock_notes_path

        # Setup file operations
        mock_file = Mock()
        mock_open.return_value.__enter__.return_value = mock_file

        # Execute
        await generate_diary_entry(mock_context)

        # Verify MCP interactions
        mock_calendar_mcp.get_response.assert_called_once_with(
            settings=mock_diary_data.settings, prompt=DIARY_CALENDAR_PROMPT
        )
        mock_todoist_mcp.get_response.assert_called_once_with(settings=mock_diary_data.settings, prompt=ANY)

        # Verify directory creation
        mock_notes_path.mkdir.assert_called_once_with(parents=True, exist_ok=True)

        # Verify file was written
        mock_open.assert_called_once()
        mock_file.write.assert_called_once()
        written_content = mock_file.write.call_args[0][0]
        assert "## Diary" in written_content
        assert "Meeting with team at 2 PM" in written_content
        assert "10:30 - Completed project documentation" in written_content

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

        # Verify no message was sent since function returns early
        mock_context.bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    @patch("builtins.open")
    @patch("plugins.diary.Path")
    @patch("plugins.diary.MCPConfigReader")
    @patch("plugins.diary.MCPClient")
    @patch("plugins.diary.datetime")
    async def test_generate_diary_entry_no_mcp_config(
        self,
        mock_datetime,
        mock_mcp_client_class,
        mock_mcp_reader_class,
        mock_path,
        mock_open,
        mock_context,
        mock_diary_data,
    ):
        """Test diary generation when MCP configurations are not available."""
        mock_context.job.data = mock_diary_data
        mock_context.job.chat_id = 123456789

        # Setup datetime mock
        mock_now = Mock()
        mock_now.strftime.side_effect = lambda fmt: {"%Y-%m-%d": "2024-01-15", "%H:%M": "23:59"}.get(fmt, "")
        mock_datetime.datetime.now.return_value = mock_now

        # Setup MCP reader to return None for configurations
        mock_mcp_reader = Mock(spec=MCPConfigReader)
        mock_mcp_reader.reload_config = Mock()
        mock_mcp_reader.get_mcp_configuration.return_value = None
        mock_mcp_reader_class.return_value = mock_mcp_reader

        # Setup file path mocking
        mock_notes_path = Mock()
        mock_notes_path.mkdir = Mock()
        mock_file_path = Mock()
        mock_file_path.exists.return_value = False  # File doesn't exist initially
        mock_notes_path.__truediv__ = Mock(return_value=mock_file_path)
        mock_path.return_value = mock_notes_path

        # Setup file operations
        mock_file = Mock()
        mock_open.return_value.__enter__.return_value = mock_file

        # Execute
        await generate_diary_entry(mock_context)

        # Verify warnings were logged
        mock_diary_data.settings.logger.warning.assert_called()

        # Verify file was written with no data placeholders
        mock_file.write.assert_called_once()
        written_content = mock_file.write.call_args[0][0]
        assert "## Diary" in written_content
        assert "No calendar events recorded for today" in written_content
        assert "No tasks completed today" in written_content

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
        mock_now.strftime.side_effect = lambda fmt: {"%Y-%m-%d": "2024-01-15", "%H:%M": "23:59"}.get(fmt, "")
        mock_datetime.datetime.now.return_value = mock_now

        # Setup MCP reader
        mock_mcp_reader = Mock(spec=MCPConfigReader)
        mock_mcp_reader.reload_config = Mock()
        mock_mcp_reader.get_mcp_configuration.return_value = None
        mock_mcp_reader_class.return_value = mock_mcp_reader

        # Setup file path mocking
        mock_notes_path = Mock()
        mock_notes_path.mkdir = Mock()
        mock_file_path = Mock()
        mock_file_path.exists.return_value = False  # File doesn't exist initially
        mock_notes_path.__truediv__ = Mock(return_value=mock_file_path)
        mock_path.return_value = mock_notes_path

        # Setup file writing to fail
        mock_open.side_effect = OSError("Permission denied")

        # Execute
        await generate_diary_entry(mock_context)

        # Verify error was logged
        mock_diary_data.settings.logger.error.assert_called()


def test_diary_template():
    """Test that the diary template contains required elements."""
    assert "{calendar_data}" in DIARY_TEMPLATE
    assert "{tasks_done}" in DIARY_TEMPLATE
    assert "## Diary" in DIARY_TEMPLATE
    assert "### Events" in DIARY_TEMPLATE
    assert "### Tasks" in DIARY_TEMPLATE


def test_diary_prompts():
    """Test that diary prompts are properly defined."""
    assert DIARY_CALENDAR_PROMPT
    assert "calendar" in DIARY_CALENDAR_PROMPT.lower()


def test_replace_diary_section_new_file():
    """Test replace_diary_section with empty content."""
    new_diary = "## Diary\n\n### Events\n* Test event\n\n### Tasks\n* Test task"
    result = replace_diary_section("", new_diary)
    assert result == new_diary


def test_replace_diary_section_existing_content_no_diary():
    """Test replace_diary_section with existing content but no diary section."""
    existing = "# Daily Note - 2024-01-15\n\n## Other Section\nSome content"
    new_diary = "## Diary\n\n### Events\n* Test event\n\n### Tasks\n* Test task"
    expected = "# Daily Note - 2024-01-15\n\n## Other Section\nSome content\n\n## Diary\n\n### Events\n* Test event\n\n### Tasks\n* Test task"
    result = replace_diary_section(existing, new_diary)
    assert result == expected


def test_replace_diary_section_replace_existing():
    """Test replace_diary_section replacing existing diary section."""
    existing = """# Daily Note - 2024-01-15

## Diary

### Events
* Old event

### Tasks
* Old task

## Other Section
Some other content"""

    new_diary = "## Diary\n\n### Events\n* New event\n\n### Tasks\n* New task"

    expected = """# Daily Note - 2024-01-15

## Diary

### Events
* New event

### Tasks
* New task

## Other Section
Some other content"""

    result = replace_diary_section(existing, new_diary)
    assert result == expected


def test_replace_diary_section_diary_at_end():
    """Test replace_diary_section when diary is at the end of file."""
    existing = """# Daily Note - 2024-01-15

## Other Section
Some content

## Diary

### Events
* Old event

### Tasks
* Old task"""

    new_diary = "## Diary\n\n### Events\n* New event\n\n### Tasks\n* New task"

    expected = """# Daily Note - 2024-01-15

## Other Section
Some content

## Diary

### Events
* New event

### Tasks
* New task"""

    result = replace_diary_section(existing, new_diary)
    assert result == expected


def test_replace_diary_section_existing_file():
    """Test diary generation with existing file content."""
    existing_file_content = """# Daily Note - 2024-01-15

## Morning Notes
Did some planning

## Diary

### Events
* Old meeting

### Tasks
* Old task

## Evening Reflection
Good day overall"""

    new_diary_section = """## Diary

### Events
* Team standup at 09:00

### Tasks
* Completed documentation review"""

    expected = """# Daily Note - 2024-01-15

## Morning Notes
Did some planning

## Diary

### Events
* Team standup at 09:00

### Tasks
* Completed documentation review

## Evening Reflection
Good day overall"""

    result = replace_diary_section(existing_file_content, new_diary_section)
    assert result == expected


class TestGenerateDiaryEntryWithExistingFile:
    """Test cases for diary generation with existing file content."""

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
    def mock_diary_data(self):
        """Create mock DiaryData."""
        settings = Mock(spec=Settings)
        settings.logger = Mock()
        settings.timezone = pytz.timezone("Europe/Prague")
        settings.agenda_mcp_calendar_name = "calendar_mcp"
        settings.agenda_mcp_todoist_name = "todoist_mcp"
        settings.mcp_config_path = "/mock/config/path"
        settings.daily_note_folder = "/tmp/daily-notes"
        genai_client = Mock(spec=genai.Client)
        return DiaryData(settings, genai_client)

    @pytest.mark.asyncio
    @patch("builtins.open")
    @patch("plugins.diary.Path")
    @patch("plugins.diary.MCPConfigReader")
    @patch("plugins.diary.MCPClient")
    @patch("plugins.diary.datetime")
    async def test_generate_diary_entry_with_existing_file(
        self,
        mock_datetime,
        mock_mcp_client_class,
        mock_mcp_reader_class,
        mock_path,
        mock_open,
        mock_context,
        mock_diary_data,
    ):
        """Test diary generation with existing file content."""
        # Setup context
        mock_context.job.data = mock_diary_data
        mock_context.job.chat_id = 123456789

        # Setup datetime mock
        mock_now = Mock()
        mock_now.strftime.side_effect = lambda fmt: {"%Y-%m-%d": "2024-01-15", "%H:%M": "23:59"}.get(fmt, "")
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
        mock_calendar_mcp.get_response = AsyncMock(return_value="* 10:00 - Team meeting completed")

        mock_todoist_mcp = Mock(spec=MCPClient)
        mock_todoist_mcp.get_response = AsyncMock(return_value="* 15:30 - Finished project documentation")

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
        mock_file_path = Mock()
        mock_file_path.exists.return_value = True  # File already exists
        mock_notes_path.__truediv__ = Mock(return_value=mock_file_path)
        mock_path.return_value = mock_notes_path

        # Existing file content
        existing_content = """# Daily Note - 2024-01-15

## Morning Notes
Had coffee and reviewed emails

## Diary

### Events
* 09:00 - Old meeting

### Tasks
* Old task completed

## Evening Notes
Need to wrap up the day"""

        # Setup file operations
        mock_read_file = Mock()
        mock_read_file.read.return_value = existing_content

        mock_write_file = Mock()

        def mock_open_side_effect(file_path, mode="r", **kwargs):
            context_manager = Mock()
            if "r" in mode:  # Reading mode
                context_manager.__enter__ = Mock(return_value=mock_read_file)
            else:  # Writing mode
                context_manager.__enter__ = Mock(return_value=mock_write_file)
            context_manager.__exit__ = Mock(return_value=None)
            return context_manager

        mock_open.side_effect = mock_open_side_effect

        # Execute
        await generate_diary_entry(mock_context)

        # Verify file was read and written
        assert mock_open.call_count >= 2  # At least one read and one write
        mock_write_file.write.assert_called_once()
        written_content = mock_write_file.write.call_args[0][0]

        # Verify the diary section was replaced correctly
        assert "# Daily Note - 2024-01-15" in written_content
        assert "## Morning Notes" in written_content
        assert "Had coffee and reviewed emails" in written_content
        assert "## Diary" in written_content
        assert "* 10:00 - Team meeting completed" in written_content
        assert "* 15:30 - Finished project documentation" in written_content
        assert "## Evening Notes" in written_content
        assert "Need to wrap up the day" in written_content

        # Verify old diary content was replaced
        assert "Old meeting" not in written_content
        assert "Old task completed" not in written_content
