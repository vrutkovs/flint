"""Settings module for Telega bot configuration."""

import pytz
import structlog
from google import genai

from plugins.rag import prepare_rag_tool


class Settings:
    """Settings class for configuring Telega bot with genai client, logger, and model."""

    def __init__(
        self,
        genai_client: genai.Client,
        logger: structlog.BoundLogger,
        chat_id: str,
        tz: str,
        mcp_config_path: str,
        summary_mcp_calendar_name: str,
        summary_mcp_weather_name: str,
        system_instructions: str,
        rag_embedding_model: str | None = None,
        rag_location: str | None = None,
        google_api_key: str | None = None,
        user_filter: list = [],
        model_name: str = "gemini-2.5-flash",
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
        self.mcp_config_path = mcp_config_path
        self.agenda_mcp_calendar_name = summary_mcp_calendar_name
        self.agenda_mcp_weather_name = summary_mcp_weather_name
        self.user_filter = user_filter

        self.__set_genconfig__(system_instructions)
        self.__set_qa_chain(
            rag_embedding_model, rag_location, google_api_key, model_name
        )

        logger.info("Settings initialized")

    def __repr__(self) -> str:
        """Return string representation of Settings."""
        return f"Settings(model_name='{self.model_name}')"

    def __set_genconfig__(self, system_instructions):
        system_instruction_split = list(system_instructions.split("\n"))
        self.logger.info(f"System instruction initialized: {system_instruction_split}")

        self.genconfig = genai.types.GenerateContentConfig(
            system_instruction=system_instruction_split
        )

    def __set_qa_chain(
        self, rag_embedding_model, rag_location, google_api_key, model_name
    ):
        if rag_embedding_model and rag_location:
            self.logger.info("RAG: initializing")
            self.qa_chain = prepare_rag_tool(
                self.logger,
                rag_location,
                rag_embedding_model,
                google_api_key,
                model_name,
            )
