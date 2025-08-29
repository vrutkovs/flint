"""Settings module for Telega bot configuration."""

from collections.abc import Sequence
from typing import Any, cast

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
        rag_vector_storage: str | None = None,
        google_api_key: str | None = None,
        user_filter: list[str] | None = None,
        model_name: str = "gemini-2.5-flash",
    ) -> None:
        """
        Initialize Settings with required configuration.

        Args:
            genai_client: Google GenAI client for text generation
            logger: Structured logger instance
            chat_id: Telegram chat ID
            tz: Timezone string
            mcp_config_path: Path to MCP configuration file
            summary_mcp_calendar_name: Name of calendar MCP for summaries
            summary_mcp_weather_name: Name of weather MCP for summaries
            system_instructions: System instructions for AI model
            rag_embedding_model: Optional RAG embedding model name
            rag_location: Optional RAG data location
            rag_vector_storage: Optional RAG vector storage location
            google_api_key: Optional Google API key
            user_filter: List of allowed usernames
            model_name: Name of the AI model to use for generation
        """
        self.genai_client: genai.Client = genai_client
        self.logger: structlog.BoundLogger = logger
        self.model_name: str = model_name
        self.chat_id: str = chat_id
        self.timezone: pytz.tzinfo.BaseTzInfo = pytz.timezone(tz)
        self.mcp_config_path: str = mcp_config_path
        self.agenda_mcp_calendar_name: str = summary_mcp_calendar_name
        self.agenda_mcp_weather_name: str = summary_mcp_weather_name
        self.user_filter: list[str] = user_filter or []
        self.genconfig: genai.types.GenerateContentConfig
        self.qa_chain: Any | None = None

        self.__set_genconfig__(system_instructions)
        self.__set_qa_chain(rag_embedding_model, rag_location, rag_vector_storage, google_api_key, model_name)

        logger.info("Settings initialized")

    def __repr__(self) -> str:
        """Return string representation of Settings."""
        return f"Settings(model_name='{self.model_name}')"

    def __set_genconfig__(self, system_instructions: str) -> None:
        """
        Set generation configuration with system instructions.

        Args:
            system_instructions: System instructions for the AI model
        """

        system_instruction_split: Sequence[str] = list(system_instructions.split("\n"))
        self.logger.info(f"System instruction initialized: {system_instruction_split}")

        self.genconfig = genai.types.GenerateContentConfig(
            system_instruction=cast(list[Any], system_instruction_split)  # pyright: ignore
        )

    def __set_qa_chain(
        self,
        rag_embedding_model: str | None,
        rag_location: str | None,
        rag_vector_storage: str | None,
        google_api_key: str | None,
        model_name: str,
    ) -> None:
        """
        Initialize RAG QA chain if configuration is provided.

        Args:
            rag_embedding_model: RAG embedding model name
            rag_location: RAG data location
            rag_vector_storage: RAG vector storage location
            google_api_key: Google API key
            model_name: Model name for RAG
        """
        if rag_embedding_model and rag_location and rag_vector_storage and google_api_key:
            self.logger.info("RAG: initializing")
            self.qa_chain = prepare_rag_tool(
                self.logger,
                rag_location,
                rag_embedding_model,
                rag_vector_storage,
                google_api_key,
                model_name,
            )
