"""Settings module for Telega bot configuration."""


import structlog
from google import genai


class Settings:
    """Settings class for configuring Telega bot with genai client, logger, and model."""

    def __init__(
        self,
        genai_client: genai.Client,
        logger: structlog.BoundLogger,
        chat_id: str,
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

    @property
    def client(self) -> genai.Client:
        """Get the genai client."""
        return self.genai_client

    @property
    def log(self) -> structlog.BoundLogger:
        """Get the logger instance."""
        return self.logger

    @property
    def model(self) -> str:
        """Get the model name."""
        return self.model_name

    def __repr__(self) -> str:
        """Return string representation of Settings."""
        return f"Settings(model_name='{self.model_name}')"
