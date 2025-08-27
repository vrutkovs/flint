"""Settings module for Telega bot configuration."""

from typing import Sequence

import pytz
import structlog
from google import genai

import vertexai
from vertexai import rag
from vertexai.generative_models import Tool


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
        rag_google_project_id: str | None = None,
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

        self.genconfig = genai.types.GenerateContentConfig(
            system_instruction=list(system_instructions.split("\n"))
        )

        self.__set_genconfig__(
            system_instructions,
            rag_embedding_model,
            rag_location,
            rag_google_project_id,
        )

        logger.info("Settings initialized")

    def __repr__(self) -> str:
        """Return string representation of Settings."""
        return f"Settings(model_name='{self.model_name}')"

    def __set_genconfig__(self, system_instructions, rag_embedding_model, rag_location, rag_google_project_id):
        tools = list()

        if rag_embedding_model and rag_location:
            self.logger.info("RAG: initializing")

            rag_google_location = "europe-west3"
            vertexai.init(project=rag_google_project_id, location=rag_google_location)

            embedding_model_config = rag.RagEmbeddingModelConfig(
                vertex_prediction_endpoint=rag.VertexPredictionEndpoint(
                    publisher_model=rag_embedding_model
                )
            )

            rag_corpus_id = "my-codebase-corpus"
            rag_corpus = rag.create_corpus(
                display_name=rag_corpus_id,
                backend_config=rag.RagVectorDbConfig(
                    rag_embedding_model_config=embedding_model_config
                ),
            )

            rag.import_files(rag_corpus.name, rag_location) #pyright: ignore

            rag_retrieval_config = rag.RagRetrievalConfig()

            rag_retrieval_tool = Tool.from_retrieval(
                retrieval=rag.Retrieval(
                    source=rag.VertexRagStore(
                        rag_resources=[
                            rag.RagResource(
                                rag_corpus="{rag_corpus.name}",
                            )
                        ],
                        rag_retrieval_config=rag_retrieval_config,
                    ),
                )
            )
            tools.append(rag_retrieval_tool)

        system_instruction_split = list(system_instructions.split("\n"))
        self.logger.info(f"System instruction initialized: {system_instruction_split}")

        self.genconfig = genai.types.GenerateContentConfig(
            tools=tools,
            system_instruction=system_instruction_split
        )
