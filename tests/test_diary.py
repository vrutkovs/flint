"""Unit tests for the diary plugin."""

from unittest.mock import AsyncMock, Mock, patch
import datetime

import pytest
import pytz
from google import genai
from telegram.ext import ContextTypes

from plugins.mcp import MCPClient, MCPConfigReader, MCPConfiguration, StdioServerParameters
from plugins.diary import (
    DIARY_PROMPT_TEMPLATE,
    DIARY_CALENDAR_PROMPT,
    DIARY_WEATHER_PROMPT,
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
        settings.agenda_mcp_weather_name = "weather_mcp"
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
        settings.agenda_mcp_weather_name = "weather_mcp"
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
        settings.agenda_mcp_weather_name = "weather_mcp"
        return settings

    @pytest.fixture
    def mock_genai_client(self):
        """Create mock GenAI client."""
        return Mock(spec=genai.Client)

    @pytest.mark.asyncio
    @patch("plugins.diary.MCPConfigReader")
    @patch("plugins.diary.MCPClient")
    @patch("plugins.diary.datetime")
    async def test_generate_diary_entry_success(
        self, mock_datetime, mock_mcp_client_class, mock_mcp_reader_class, mock_context, mock_diary_data
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

        # Setup weather MCP
        mock_weather_config = Mock(spec=MCPConfiguration)
        mock_weather_config.name = "weather_mcp"
        mock_weather_config.get_server_params = AsyncMock(return_value=Mock(spec=StdioServerParameters))

        # Configure MCP reader to return configurations
        def get_mcp_config(name):
            if name == "calendar_mcp":
                return mock_calendar_config
            elif name == "weather_mcp":
                return mock_weather_config
            return None

        mock_mcp_reader.get_mcp_configuration.side_effect = get_mcp_config

        # Setup MCP clients
        mock_calendar_mcp = Mock(spec=MCPClient)
        mock_calendar_mcp.get_response = AsyncMock(return_value="Meeting with team at 2 PM, completed project review")

        mock_weather_mcp = Mock(spec=MCPClient)
        mock_weather_mcp.get_response = AsyncMock(return_value="Sunny day with temperature 22°C")

        def mcp_client_factory(name, server_params, logger):
            if name == "calendar_mcp":
                return mock_calendar_mcp
            elif name == "weather_mcp":
                return mock_weather_mcp
            return Mock(spec=MCPClient)

        mock_mcp_client_class.side_effect = mcp_client_factory

        # Setup AI response
        mock_response = Mock()
        mock_response.text = "## Daily Reflection\n\nToday was productive with the team meeting and project review completed."
        mock_diary_data.genai_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        # Execute
        await generate_diary_entry(mock_context)

        # Verify MCP interactions
        mock_calendar_mcp.get_response.assert_called_once_with(
            settings=mock_diary_data.settings,
            prompt=DIARY_CALENDAR_PROMPT
        )
        mock_weather_mcp.get_response.assert_called_once_with(
            settings=mock_diary_data.settings,
            prompt=DIARY_WEATHER_PROMPT
        )

        # Verify AI was called
        mock_diary_data.genai_client.aio.models.generate_content.assert_called_once()

        # Verify message was sent
        mock_context.bot.send_message.assert_called_once()
        call_args = mock_context.bot.send_message.call_args
        assert call_args[1]["chat_id"] == 123456789
        assert "# Daily Diary Entry - 2024-01-15" in call_args[1]["text"]
        assert call_args[1]["parse_mode"] == "Markdown"

    @pytest.mark.asyncio
    @patch("plugins.diary.MCPConfigReader")
    @patch("plugins.diary.MCPClient")
    @patch("plugins.diary.datetime")
    async def test_generate_diary_entry_no_mcp_config(
        self, mock_datetime, mock_mcp_client_class, mock_mcp_reader_class, mock_context, mock_diary_data
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

        # Setup AI response
        mock_response = Mock()
        mock_response.text = "## Daily Reflection\n\nToday was a quiet day for reflection."
        mock_diary_data.genai_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        # Execute
        await generate_diary_entry(mock_context)

        # Verify warnings were logged
        mock_diary_data.settings.logger.warning.assert_called()

        # Verify AI was called with no data placeholders
        mock_diary_data.genai_client.aio.models.generate_content.assert_called_once()

        # Verify message was sent
        mock_context.bot.send_message.assert_called_once()

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
    @patch("plugins.diary.MCPConfigReader")
    @patch("plugins.diary.datetime")
    async def test_generate_diary_entry_ai_error(
        self, mock_datetime, mock_mcp_reader_class, mock_context, mock_diary_data
    ):
        """Test diary generation when AI returns empty response."""
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

        # Setup AI to return empty response
        mock_response = Mock()
        mock_response.text = None
        mock_diary_data.genai_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        # Execute
        await generate_diary_entry(mock_context)

        # Verify error was logged
        mock_diary_data.settings.logger.error.assert_called()

        # Verify error message was sent
        mock_context.bot.send_message.assert_called_once()
        call_args = mock_context.bot.send_message.call_args
        assert "Sorry, I couldn't generate your diary entry" in call_args[1]["text"]


def test_diary_prompt_template():
    """Test that the diary prompt template contains required elements."""
    assert "{date}" in DIARY_PROMPT_TEMPLATE
    assert "{time}" in DIARY_PROMPT_TEMPLATE
    assert "{calendar_data}" in DIARY_PROMPT_TEMPLATE
    assert "{weather_data}" in DIARY_PROMPT_TEMPLATE
    assert "markdown" in DIARY_PROMPT_TEMPLATE.lower()
    assert "first person" in DIARY_PROMPT_TEMPLATE.lower()


def test_diary_prompts():
    """Test that diary prompts are properly defined."""
    assert DIARY_CALENDAR_PROMPT
    assert DIARY_WEATHER_PROMPT
    assert "calendar" in DIARY_CALENDAR_PROMPT.lower()
    assert "weather" in DIARY_WEATHER_PROMPT.lower()
