"""Settings module for Telega bot configuration."""
import pytz
import structlog
from google import genai


class Settings:
    """Settings class for configuring Telega bot with genai client, logger, and model."""

    def __init__(
        self,
        genai_client: genai.Client,
        logger: structlog.BoundLogger,
        chat_id: str,
        tz: str,
        ha_url: str,
        ha_token: str,
        ha_weather_entity_id: str,
        mcp_config_path: str,
        summary_mcp_calendar_name: str,
        model_name: str = "gemini-2.5-flash"
    ):
        """
        Initialize Settings with required configuration.

        Args:
            genai_client: Google GenAI client for text generation
            logger: Structured logger instance
            model_name: Name of the AI model to use for generation
        """
        self.genai_client = genai_client
        self.logger = logger
        self.model_name = model_name
        self.chat_id = chat_id
        self.timezone = pytz.timezone(tz)
        self.ha_url = ha_url
        self.ha_token = ha_token
        self.ha_weather_entity_id = ha_weather_entity_id
        self.mcp_config_path = mcp_config_path
        self.SUMMARY_MCP_CALENDAR_NAME = summary_mcp_calendar_name

    def __repr__(self) -> str:
        """Return string representation of Settings."""
        return f"Settings(model_name='{self.model_name}')"
