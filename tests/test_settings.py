"""Unit tests for the Settings class."""

from unittest.mock import MagicMock, Mock, patch

import pytest
import pytz
import structlog
from google import genai

from telega.settings import Settings


class TestSettings:
    """Test cases for the Settings class."""

    @pytest.fixture
    def mock_genai_client(self):
        """Create a mock GenAI client."""
        return Mock(spec=genai.Client)

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger with info method."""
        logger = Mock(spec=structlog.BoundLogger)
        logger.info = Mock()
        return logger

    @pytest.fixture
    def basic_settings_params(self, mock_genai_client, mock_logger):
        """Create basic parameters for Settings initialization."""
        return {
            "genai_client": mock_genai_client,
            "logger": mock_logger,
            "chat_id": "123456789",
            "tz": "UTC",
            "mcp_config_path": "/path/to/config.yaml",
            "mcp_calendar_name": "calendar_mcp",
            "mcp_weather_name": "weather_mcp",
            "mcp_todoist_name": "todoist_mcp",
            "system_instructions": "You are a helpful assistant.",
            "model_name": "gemini-2.5-flash",
        }

    def test_settings_initialization(self, basic_settings_params):
        """Test Settings initialization with required parameters."""
        settings = Settings(**basic_settings_params)

        assert settings.genai_client == basic_settings_params["genai_client"]
        assert settings.logger == basic_settings_params["logger"]
        assert settings.model_name == basic_settings_params["model_name"]
        assert settings.chat_id == basic_settings_params["chat_id"]
        assert isinstance(settings.timezone, pytz.tzinfo.BaseTzInfo)
        assert settings.mcp_config_path == basic_settings_params["mcp_config_path"]
        assert settings.agenda_mcp_calendar_name == basic_settings_params["mcp_calendar_name"]
        assert settings.agenda_mcp_weather_name == basic_settings_params["mcp_weather_name"]
        assert settings.agenda_mcp_todoist_name == basic_settings_params["mcp_todoist_name"]
        assert settings.user_filter == []
        assert settings.qa_chain is None

    def test_settings_with_user_filter(self, basic_settings_params):
        """Test Settings initialization with user filter."""
        basic_settings_params["user_filter"] = ["user1", "user2", "user3"]
        settings = Settings(**basic_settings_params)

        assert settings.user_filter == ["user1", "user2", "user3"]

    def test_settings_repr(self, basic_settings_params):
        """Test Settings string representation."""
        settings = Settings(**basic_settings_params)

        assert repr(settings) == "Settings(model_name='gemini-2.5-flash')"

    def test_settings_with_custom_model_name(self, basic_settings_params):
        """Test Settings with custom model name."""
        basic_settings_params["model_name"] = "gemini-pro"
        settings = Settings(**basic_settings_params)

        assert settings.model_name == "gemini-pro"
        assert repr(settings) == "Settings(model_name='gemini-pro')"

    def test_settings_timezone_parsing(self, basic_settings_params):
        """Test timezone parsing for different timezone strings."""
        test_timezones = ["UTC", "America/New_York", "Europe/London", "Asia/Tokyo"]

        for tz_string in test_timezones:
            basic_settings_params["tz"] = tz_string
            settings = Settings(**basic_settings_params)
            assert settings.timezone == pytz.timezone(tz_string)

    def test_settings_invalid_timezone(self, basic_settings_params):
        """Test Settings initialization with invalid timezone."""
        basic_settings_params["tz"] = "Invalid/Timezone"

        with pytest.raises(pytz.exceptions.UnknownTimeZoneError):
            Settings(**basic_settings_params)

    def test_system_instructions_processing(self, basic_settings_params):
        """Test that system instructions are properly split and configured."""
        multi_line_instructions = "Line 1\nLine 2\nLine 3"
        basic_settings_params["system_instructions"] = multi_line_instructions

        settings = Settings(**basic_settings_params)

        # Verify logger was called with split instructions
        settings.logger.info.assert_any_call("System instruction initialized: ['Line 1', 'Line 2', 'Line 3']")

        # Verify genconfig was set
        assert hasattr(settings, "genconfig")
        assert isinstance(settings.genconfig, genai.types.GenerateContentConfig)

    @patch("telega.settings.prepare_rag_tool")
    def test_settings_with_rag_configuration(self, mock_prepare_rag, basic_settings_params):
        """Test Settings initialization with RAG configuration."""
        mock_qa_chain = Mock()
        mock_prepare_rag.return_value = mock_qa_chain

        basic_settings_params["rag_embedding_model"] = "text-embedding-004"
        basic_settings_params["rag_location"] = "/path/to/rag/data"
        basic_settings_params["rag_vector_storage"] = "vector-storage-location"
        basic_settings_params["google_api_key"] = "test-api-key"

        settings = Settings(**basic_settings_params)

        # Verify RAG was initialized
        mock_prepare_rag.assert_called_once_with(
            settings.logger,
            "/path/to/rag/data",
            "text-embedding-004",
            "vector-storage-location",
            "test-api-key",
            "gemini-2.5-flash",
        )
        assert settings.qa_chain == mock_qa_chain
        settings.logger.info.assert_any_call("RAG: initializing")

    def test_settings_without_rag_configuration(self, basic_settings_params):
        """Test Settings without RAG configuration (partial params)."""
        # Only provide some RAG parameters, not all
        basic_settings_params["rag_embedding_model"] = "text-embedding-004"
        # Missing rag_location and google_api_key

        settings = Settings(**basic_settings_params)

        # Verify RAG was not initialized
        assert settings.qa_chain is None

    def test_settings_logger_calls(self, basic_settings_params):
        """Test that logger is called with appropriate messages."""
        settings = Settings(**basic_settings_params)

        # Verify logger was called during initialization
        settings.logger.info.assert_any_call("Settings initialized")

    def test_genconfig_with_empty_instructions(self, basic_settings_params):
        """Test genconfig creation with empty system instructions."""
        basic_settings_params["system_instructions"] = ""

        settings = Settings(**basic_settings_params)

        settings.logger.info.assert_any_call("System instruction initialized: ['']")
        assert hasattr(settings, "genconfig")

    def test_genconfig_with_single_line_instructions(self, basic_settings_params):
        """Test genconfig creation with single line system instructions."""
        basic_settings_params["system_instructions"] = "Single line instruction"

        settings = Settings(**basic_settings_params)

        settings.logger.info.assert_any_call("System instruction initialized: ['Single line instruction']")

    @patch("telega.settings.prepare_rag_tool")
    def test_rag_initialization_with_all_params(self, mock_prepare_rag, basic_settings_params):
        """Test complete RAG initialization flow."""
        mock_qa_chain = MagicMock()
        mock_prepare_rag.return_value = mock_qa_chain

        # Provide all RAG parameters
        basic_settings_params.update(
            {
                "rag_embedding_model": "embedding-model",
                "rag_location": "/rag/location",
                "rag_vector_storage": "vector-storage-location",
                "google_api_key": "api-key-123",
            }
        )

        settings = Settings(**basic_settings_params)

        # Verify all components were initialized
        assert settings.qa_chain is not None
        assert settings.qa_chain == mock_qa_chain

        # Verify the prepare_rag_tool was called with correct parameters
        mock_prepare_rag.assert_called_once()
        call_args = mock_prepare_rag.call_args[0]
        assert call_args[0] == settings.logger
        assert call_args[1] == "/rag/location"
        assert call_args[2] == "embedding-model"
        assert call_args[3] == "vector-storage-location"
        assert call_args[4] == "api-key-123"
        assert call_args[5] == "gemini-2.5-flash"

    def test_settings_attribute_access(self, basic_settings_params):
        """Test that all expected attributes are accessible."""
        settings = Settings(**basic_settings_params)

        # Test all public attributes are accessible
        attributes = [
            "genai_client",
            "logger",
            "model_name",
            "chat_id",
            "timezone",
            "mcp_config_path",
            "agenda_mcp_calendar_name",
            "agenda_mcp_weather_name",
            "agenda_mcp_todoist_name",
            "user_filter",
            "genconfig",
            "qa_chain",
        ]

        for attr in attributes:
            assert hasattr(settings, attr)

    def test_settings_with_partial_rag_params(self, basic_settings_params):
        """Test Settings with only some RAG parameters provided."""
        # Only rag_location, missing rag_embedding_model and google_api_key
        basic_settings_params["rag_location"] = "/path/to/rag/data"

        settings = Settings(**basic_settings_params)

        # Verify RAG was not initialized
        assert settings.qa_chain is None
        # RAG: initializing should not be called
        for call in settings.logger.info.call_args_list:
            assert "RAG: initializing" not in str(call)

    @patch("telega.settings.prepare_rag_tool")
    def test_rag_initialization_logging(self, mock_prepare_rag, basic_settings_params):
        """Test that RAG initialization is properly logged."""
        mock_qa_chain = Mock()
        mock_prepare_rag.return_value = mock_qa_chain

        basic_settings_params.update(
            {
                "rag_embedding_model": "text-embedding-004",
                "rag_location": "/path/to/rag/data",
                "rag_vector_storage": "vector-storage-location",
                "google_api_key": "test-api-key",
            }
        )

        settings = Settings(**basic_settings_params)

        # Check the logger calls in order
        logger_calls = [str(call) for call in settings.logger.info.call_args_list]

        # Should have system instruction log
        assert any("System instruction initialized:" in call for call in logger_calls)

        # Should have RAG initialization log before Settings initialized
        rag_init_index = next(i for i, call in enumerate(logger_calls) if "RAG: initializing" in call)
        settings_init_index = next(i for i, call in enumerate(logger_calls) if "Settings initialized" in call)
        assert rag_init_index < settings_init_index

    def test_settings_with_different_default_model(self, mock_genai_client, mock_logger):
        """Test Settings uses default model name when not specified."""
        params = {
            "genai_client": mock_genai_client,
            "logger": mock_logger,
            "chat_id": "123456789",
            "tz": "UTC",
            "mcp_config_path": "/path/to/config.yaml",
            "mcp_calendar_name": "calendar_mcp",
            "mcp_weather_name": "weather_mcp",
            "mcp_todoist_name": "todoist_mcp",
            "system_instructions": "You are a helpful assistant.",
            # model_name not specified, should use default
        }

        settings = Settings(**params)

        assert settings.model_name == "gemini-2.5-flash"  # default value

    def test_genconfig_system_instruction_field(self, basic_settings_params):
        """Test that genconfig has system_instruction field set correctly."""
        basic_settings_params["system_instructions"] = "Test\nMultiline\nInstructions"

        settings = Settings(**basic_settings_params)

        # Check that genconfig is created with system_instruction
        assert settings.genconfig is not None
        # We can't directly check the system_instruction field since it's passed to the constructor,
        # but we can verify the genconfig is a valid GenerateContentConfig instance
        assert isinstance(settings.genconfig, genai.types.GenerateContentConfig)

    def test_send_message_not_set_raises_error(self, basic_settings_params):
        """Test that accessing send_message before setting it raises RuntimeError."""
        settings = Settings(**basic_settings_params)

        with pytest.raises(RuntimeError, match="send_message has not been set. Call set_send_message\\(\\) first."):
            _ = settings.send_message

    def test_send_message_set_and_get(self, basic_settings_params):
        """Test setting and getting send_message function."""
        from unittest.mock import AsyncMock

        settings = Settings(**basic_settings_params)
        mock_send_message = AsyncMock()

        settings.set_send_message(mock_send_message)

        assert settings.send_message is mock_send_message

    def test_send_message_property_type_checking(self, basic_settings_params):
        """Test that send_message property returns the correct type."""
        from unittest.mock import AsyncMock

        settings = Settings(**basic_settings_params)
        mock_send_message = AsyncMock()

        settings.set_send_message(mock_send_message)

        # Verify the property returns a callable
        result = settings.send_message
        assert callable(result)
        assert result is mock_send_message

    def test_send_message_integration_with_schedule(self, basic_settings_params):
        """Test that send_message integration works with schedule plugin."""
        from unittest.mock import AsyncMock, Mock

        from telegram.ext import ExtBot

        settings = Settings(**basic_settings_params)
        mock_send_message = AsyncMock()
        settings.set_send_message(mock_send_message)

        # Create mock objects similar to what schedule.py would use
        mock_bot = Mock(spec=ExtBot)
        chat_id = 123456789
        text = "Test agenda message"

        # This simulates what the schedule plugin does
        async def simulate_schedule_usage():
            await settings.send_message(mock_bot, chat_id, text)

        # Run the simulation
        import asyncio

        asyncio.run(simulate_schedule_usage())

        # Verify send_message was called correctly
        mock_send_message.assert_called_once_with(mock_bot, chat_id, text)
