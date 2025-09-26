"""Pytest configuration and shared fixtures for all tests."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
import structlog
from google import genai

# Add src directory to Python path for imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


@pytest.fixture
def mock_logger():
    """Create a mock logger for testing."""
    logger = Mock(spec=structlog.BoundLogger)
    logger.info = Mock()
    logger.error = Mock()
    logger.debug = Mock()
    logger.warning = Mock()
    return logger


@pytest.fixture
def mock_genai_client():
    """Create a mock GenAI client for testing."""
    client = Mock(spec=genai.Client)
    client.aio = Mock()
    client.aio.models = Mock()
    client.aio.models.generate_content = AsyncMock()
    return client


@pytest.fixture
def sample_system_instructions():
    """Provide sample system instructions for testing."""
    return """You are a helpful assistant.
    Be concise and clear.
    Always be polite."""


@pytest.fixture
def sample_config():
    """Provide sample configuration values for testing."""
    return {
        "chat_id": "123456789",
        "tz": "UTC",
        "mcp_config_path": "/path/to/mcp/config.yaml",
        "mcp_calendar_name": "calendar",
        "mcp_weather_name": "weather",
        "model_name": "gemini-2.5-flash",
        "user_filter": ["user1", "user2"],
    }


@pytest.fixture
def mock_telegram_update():
    """Create a mock Telegram update object."""
    from telegram import Chat, Message, Update, User

    update = Mock(spec=Update)
    update.update_id = 12345
    update.message = Mock(spec=Message)
    update.message.message_id = 999
    update.message.text = "Test message"
    update.message.reply_text = AsyncMock()
    update.effective_user = Mock(spec=User)
    update.effective_user.username = "testuser"
    update.effective_chat = Mock(spec=Chat)
    update.effective_chat.id = 123456789

    return update


@pytest.fixture
def mock_telegram_context():
    """Create a mock Telegram context object."""
    from telegram.ext import ContextTypes

    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot = AsyncMock()
    context.args = []

    return context


@pytest.fixture(autouse=True)
def reset_mocks():
    """Reset all mocks before each test."""
    yield
    # Cleanup after each test if needed


@pytest.fixture
def async_mock():
    """Helper fixture to create async mocks."""
    return AsyncMock


# Configure pytest-asyncio
pytest_plugins = ("pytest_asyncio",)
