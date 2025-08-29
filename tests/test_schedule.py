"""Unit tests for the schedule plugin."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
import pytz
from google import genai
from telegram.ext import ContextTypes

from plugins.mcp import MCPClient, MCPConfigReader, MCPConfiguration, StdioServerParameters
from plugins.schedule import (
    CALENDAR_MCP_PROMPT,
    PROMPT_TEMPLATE,
    WEATHER_MCP_PROMPT,
    ScheduleData,
    send_agenda,
)
from telega.settings import Settings


class TestScheduleData:
    """Test cases for the ScheduleData class."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = Mock(spec=Settings)
        settings.logger = Mock()
        settings.timezone = pytz.timezone("Europe/Prague")
        settings.agenda_mcp_calendar_name = "calendar_mcp"
        settings.agenda_mcp_weather_name = "weather_mcp"
        settings.mcp_config_path = "/path/to/config.yaml"
        return settings

    @pytest.fixture
    def mock_genai_client(self):
        """Create mock GenAI client."""
        return Mock(spec=genai.Client)

    def test_schedule_data_initialization(self, mock_settings, mock_genai_client):
        """Test ScheduleData initialization."""
        schedule_data = ScheduleData(mock_settings, mock_genai_client)

        assert schedule_data.settings == mock_settings
        assert schedule_data.genai_client == mock_genai_client


class TestSendAgenda:
    """Test cases for the send_agenda function."""

    @pytest.fixture
    def mock_context(self):
        """Create mock context."""
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.bot = AsyncMock()
        context.bot.send_message = AsyncMock()
        context.job = Mock()
        context.job.data = Mock(spec=ScheduleData)
        context.job.chat_id = 123456789
        return context

    @pytest.fixture
    def mock_schedule_data(self, mock_settings, mock_genai_client):
        """Create mock ScheduleData."""
        return ScheduleData(mock_settings, mock_genai_client)

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = Mock(spec=Settings)
        settings.logger = Mock()
        settings.timezone = pytz.timezone("Europe/Prague")
        settings.agenda_mcp_calendar_name = "calendar_mcp"
        settings.agenda_mcp_weather_name = "weather_mcp"
        settings.mcp_config_path = "/path/to/config.yaml"
        settings.model_name = "gemini-2.5-flash"
        settings.genconfig = Mock()
        return settings

    @pytest.mark.asyncio
    @patch("plugins.schedule.MCPConfigReader")
    @patch("plugins.schedule.MCPClient")
    async def test_send_agenda_success(
        self, mock_mcp_client_class, mock_mcp_reader_class, mock_context, mock_schedule_data
    ):
        """Test successful agenda sending."""
        # Setup context
        mock_context.job.data = mock_schedule_data
        mock_context.job.chat_id = 123456789

        # Setup MCP reader
        mock_mcp_reader = Mock(spec=MCPConfigReader)
        mock_mcp_reader.reload_config = Mock()
        mock_mcp_reader.load_config = Mock()
        mock_mcp_reader_class.return_value = mock_mcp_reader

        # Setup calendar MCP configuration
        mock_calendar_config = Mock(spec=MCPConfiguration)
        mock_calendar_config.name = "calendar_mcp"
        mock_calendar_config.get_server_params = AsyncMock(
            return_value=Mock(spec=StdioServerParameters, command="mock_command", args=[], env={}, cwd=None)
        )

        # Setup weather MCP configuration
        mock_weather_config = Mock(spec=MCPConfiguration)
        mock_weather_config.name = "weather_mcp"
        mock_weather_config.get_server_params = AsyncMock(
            return_value=Mock(spec=StdioServerParameters, command="mock_command", args=[], env={}, cwd=None)
        )

        mock_mcp_reader.get_mcp_configuration.side_effect = lambda name: {
            "calendar_mcp": mock_calendar_config,
            "weather_mcp": mock_weather_config,
        }.get(name)

        # Setup MCP clients
        mock_calendar_client = Mock(spec=MCPClient)
        mock_calendar_client.get_response = AsyncMock(return_value="Meeting at 10 AM, Lunch at 1 PM")

        mock_weather_client = Mock(spec=MCPClient)
        mock_weather_client.get_response = AsyncMock(return_value="Sunny, 25°C, light wind")

        mock_mcp_client_class.side_effect = [mock_weather_client, mock_calendar_client]

        # Setup GenAI response
        mock_response = Mock()
        mock_response.text = "Good morning! The weather is sunny at 25°C. You have a meeting at 10 AM."
        mock_schedule_data.genai_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        # Execute
        await send_agenda(mock_context)

        # Verify
        mock_context.bot.send_message.assert_called_once_with(
            chat_id=123456789,
            text="Good morning! The weather is sunny at 25°C. You have a meeting at 10 AM.",
            parse_mode="Markdown",
        )

        # Verify MCP clients were called with correct prompts
        mock_calendar_client.get_response.assert_called_once()
        calendar_call_args = mock_calendar_client.get_response.call_args
        assert calendar_call_args.kwargs["prompt"] == CALENDAR_MCP_PROMPT

        mock_weather_client.get_response.assert_called_once()
        weather_call_args = mock_weather_client.get_response.call_args
        assert weather_call_args.kwargs["prompt"] == WEATHER_MCP_PROMPT

    @pytest.mark.asyncio
    @patch("plugins.schedule.MCPConfigReader")
    @patch("plugins.schedule.MCPClient")
    async def test_send_agenda_mcp_error(
        self, mock_mcp_client_class, mock_mcp_reader_class, mock_context, mock_schedule_data
    ):
        """Test agenda sending when MCP fails."""
        mock_context.job.data = mock_schedule_data
        mock_context.job.chat_id = 123456789

        # Setup MCP reader to return None
        mock_mcp_reader = Mock(spec=MCPConfigReader)
        mock_mcp_reader.reload_config = Mock()
        mock_mcp_reader.load_config = Mock()
        mock_mcp_reader.get_mcp_configuration.return_value = None
        mock_mcp_reader_class.return_value = mock_mcp_reader

        # Setup GenAI response
        mock_response = Mock()
        mock_response.text = "Agenda could not be generated."
        mock_schedule_data.genai_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        # Execute
        await send_agenda(mock_context)

        # Verify bot was called with GenAI response and Markdown parse mode
        mock_context.bot.send_message.assert_called_once_with(
            chat_id=123456789, text=mock_response.text, parse_mode="Markdown"
        )

        # Verify error was logged
        mock_schedule_data.settings.logger.error.assert_called()

    @pytest.mark.asyncio
    @patch("plugins.schedule.MCPConfigReader")
    @patch("plugins.schedule.MCPClient")
    async def test_send_agenda_empty_response(
        self, mock_mcp_client_class, mock_mcp_reader_class, mock_context, mock_schedule_data
    ):
        """Test agenda sending with empty MCP responses."""
        mock_context.job.data = mock_schedule_data
        mock_context.job.chat_id = 123456789

        # Setup MCP reader
        mock_mcp_reader = Mock(spec=MCPConfigReader)
        mock_mcp_reader.reload_config = Mock()
        mock_mcp_reader.load_config = Mock()
        mock_mcp_reader_class.return_value = mock_mcp_reader

        # Setup configurations
        mock_calendar_config = Mock(spec=MCPConfiguration)
        mock_calendar_config.name = "calendar_mcp"
        mock_calendar_config.get_server_params = AsyncMock(
            return_value=Mock(spec=StdioServerParameters, command="mock_command", args=[], env={}, cwd=None)
        )

        mock_weather_config = Mock(spec=MCPConfiguration)
        mock_weather_config.name = "weather_mcp"
        mock_weather_config.get_server_params = AsyncMock(
            return_value=Mock(spec=StdioServerParameters, command="mock_command", args=[], env={}, cwd=None)
        )

        mock_mcp_reader.get_mcp_configuration.side_effect = lambda name: {
            "calendar_mcp": mock_calendar_config,
            "weather_mcp": mock_weather_config,
        }.get(name)

        # Setup MCP clients with empty responses
        mock_calendar_client = Mock(spec=MCPClient)
        mock_calendar_client.get_response = AsyncMock(return_value="")

        mock_weather_client = Mock(spec=MCPClient)
        mock_weather_client.get_response = AsyncMock(return_value="")

        mock_mcp_client_class.side_effect = [mock_calendar_client, mock_weather_client]

        # Setup GenAI response
        mock_response = Mock()
        mock_response.text = "Good morning! No events or weather data available."
        mock_schedule_data.genai_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        # Execute
        await send_agenda(mock_context)

        # Verify message was sent with empty data acknowledgment
        mock_context.bot.send_message.assert_called_once_with(
            chat_id=123456789, text="Good morning! No events or weather data available.", parse_mode="Markdown"
        )

    @pytest.mark.asyncio
    @patch("plugins.schedule.MCPConfigReader")
    @patch("plugins.schedule.MCPClient")
    async def test_send_agenda_genai_error(
        self, mock_mcp_client_class, mock_mcp_reader_class, mock_context, mock_schedule_data
    ):
        """Test agenda sending when GenAI fails."""
        import pytest

        mock_context.job.data = mock_schedule_data
        mock_context.job.chat_id = 123456789

        # Setup MCP components
        mock_mcp_reader = Mock(spec=MCPConfigReader)
        mock_mcp_reader.reload_config = Mock()
        mock_mcp_reader.load_config = Mock()
        mock_mcp_reader_class.return_value = mock_mcp_reader

        mock_calendar_config = Mock(spec=MCPConfiguration)
        mock_calendar_config.name = "calendar_mcp"
        mock_calendar_config.get_server_params = AsyncMock(
            return_value=Mock(spec=StdioServerParameters, command="mock_command", args=[], env={}, cwd=None)
        )

        mock_weather_config = Mock(spec=MCPConfiguration)
        mock_weather_config.name = "weather_mcp"
        mock_weather_config.get_server_params = AsyncMock(
            return_value=Mock(spec=StdioServerParameters, command="mock_command", args=[], env={}, cwd=None)
        )

        mock_mcp_reader.get_mcp_configuration.side_effect = lambda name: {
            "calendar_mcp": mock_calendar_config,
            "weather_mcp": mock_weather_config,
        }.get(name)

        mock_calendar_client = Mock(spec=MCPClient)
        mock_calendar_client.get_response = AsyncMock(return_value="Meeting at 10 AM")

        mock_weather_client = Mock(spec=MCPClient)
        mock_weather_client.get_response = AsyncMock(return_value="Sunny, 25°C")

        mock_mcp_client_class.side_effect = [mock_calendar_client, mock_weather_client]

        # Setup GenAI to fail
        mock_schedule_data.genai_client.aio.models.generate_content = AsyncMock(
            side_effect=Exception("GenAI API error")
        )

        # Execute and verify exception
        with pytest.raises(Exception, match="GenAI API error"):
            await send_agenda(mock_context)

    @pytest.mark.asyncio
    @patch("plugins.schedule.MCPConfigReader")
    @patch("plugins.schedule.MCPClient")
    async def test_send_agenda_none_genai_response(
        self, mock_mcp_client_class, mock_mcp_reader_class, mock_context, mock_schedule_data
    ):
        """Test agenda sending when GenAI returns None."""
        import pytest

        mock_context.job.data = mock_schedule_data
        mock_context.job.chat_id = 123456789

        # Setup MCP components
        mock_mcp_reader = Mock(spec=MCPConfigReader)
        mock_mcp_reader.reload_config = Mock()
        mock_mcp_reader.load_config = Mock()
        mock_mcp_reader_class.return_value = mock_mcp_reader

        mock_calendar_config = Mock(spec=MCPConfiguration)
        mock_calendar_config.name = "calendar_mcp"
        mock_calendar_config.get_server_params = AsyncMock(
            return_value=Mock(spec=StdioServerParameters, command="mock_command", args=[], env={}, cwd=None)
        )

        mock_weather_config = Mock(spec=MCPConfiguration)
        mock_weather_config.name = "weather_mcp"
        mock_weather_config.get_server_params = AsyncMock(
            return_value=Mock(spec=StdioServerParameters, command="mock_command", args=[], env={}, cwd=None)
        )

        mock_mcp_reader.get_mcp_configuration.side_effect = lambda name: {
            "calendar_mcp": mock_calendar_config,
            "weather_mcp": mock_weather_config,
        }.get(name)

        mock_calendar_client = Mock(spec=MCPClient)
        mock_calendar_client.get_response = AsyncMock(return_value="Meeting at 10 AM")

        mock_weather_client = Mock(spec=MCPClient)
        mock_weather_client.get_response = AsyncMock(return_value="Sunny, 25°C")

        mock_mcp_client_class.side_effect = [mock_calendar_client, mock_weather_client]

        # Setup GenAI to return None
        mock_response = Mock()
        mock_response.text = None
        mock_schedule_data.genai_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        # Execute and verify exception
        with pytest.raises(ValueError, match="Empty response from AI"):
            await send_agenda(mock_context)


class TestPromptConstants:
    """Test cases for prompt constants."""

    def test_prompt_template_contains_placeholders(self):
        """Test that prompt template contains required placeholders."""
        assert "{weather_data}" in PROMPT_TEMPLATE
        assert "{calendar_data}" in PROMPT_TEMPLATE

    def test_calendar_mcp_prompt_format(self):
        """Test calendar MCP prompt format."""
        assert "calendar" in CALENDAR_MCP_PROMPT.lower()
        assert "timezone" in CALENDAR_MCP_PROMPT.lower() or "Europe/Prague" in CALENDAR_MCP_PROMPT

    def test_weather_mcp_prompt_format(self):
        """Test weather MCP prompt format."""
        assert "weather" in WEATHER_MCP_PROMPT.lower()
        assert "brno" in WEATHER_MCP_PROMPT.lower() or "today" in WEATHER_MCP_PROMPT.lower()
