from unittest.mock import ANY, MagicMock, Mock, patch

import pytest

from plugins.rag import prepare_rag_tool


@pytest.fixture
def mock_logger():
    return Mock()


@pytest.fixture
def mock_documents():
    """Create mock documents for testing."""
    doc1 = Mock()
    doc1.page_content = "Content 1"
    doc1.metadata = {"source": "doc1.txt"}

    doc2 = Mock()
    doc2.page_content = "Content 2"
    doc2.metadata = {"source": "doc2.txt"}

    return [doc1, doc2]


@patch("plugins.rag.RunnablePassthrough")
@patch("plugins.rag.RunnableLambda")
@patch("plugins.rag.StrOutputParser")
@patch("plugins.rag.ChatPromptTemplate")
@patch("plugins.rag.DirectoryLoader")
@patch("plugins.rag.RecursiveCharacterTextSplitter")
@patch("plugins.rag.GoogleGenerativeAIEmbeddings")
@patch("plugins.rag.Chroma")
@patch("plugins.rag.ChatGoogleGenerativeAI")
def test_prepare_rag_tool_success(
    mock_llm,
    mock_chroma,
    mock_embeddings,
    mock_textsplitter,
    mock_loader,
    mock_prompt_template,
    mock_output_parser,
    mock_runnable_lambda,
    mock_runnable_passthrough,
    mock_logger,
    mock_documents,
):
    # Setup mocks
    mock_loader_instance = Mock()
    mock_loader.return_value = mock_loader_instance
    mock_loader_instance.load_and_split.return_value = mock_documents

    mock_embeddings_instance = Mock()
    mock_embeddings.return_value = mock_embeddings_instance

    mock_chroma_instance = Mock()
    mock_chroma.return_value = mock_chroma_instance

    # Create a mock retriever that supports pipe operator
    mock_retriever = MagicMock()
    mock_retriever.__or__ = Mock(return_value=MagicMock())
    mock_chroma_instance.as_retriever.return_value = mock_retriever

    # Mock LLM
    mock_llm_instance = MagicMock()
    mock_llm_instance.__or__ = Mock(return_value=MagicMock())
    mock_llm.return_value = mock_llm_instance

    # Mock prompt
    mock_prompt = MagicMock()
    mock_prompt.__or__ = Mock(return_value=MagicMock())
    mock_prompt_template.from_template.return_value = mock_prompt

    # Mock output parser
    mock_parser_instance = MagicMock()
    mock_output_parser.return_value = mock_parser_instance

    # Mock RunnableLambda to return something that supports pipe
    mock_lambda_instance = MagicMock()
    mock_runnable_lambda.return_value = mock_lambda_instance

    # Mock RunnablePassthrough
    mock_passthrough_instance = MagicMock()
    mock_runnable_passthrough.return_value = mock_passthrough_instance

    # Call function
    result = prepare_rag_tool(
        logger=mock_logger,
        rag_location="dir1,dir2",
        rag_embedding_model="models/embedding-001",
        rag_vector_storage="/path/to/storage",
        google_api_key="test-key",
        rag_llm_model="gemini-pro",
    )

    # Verify basic calls
    assert mock_loader.call_count == 2
    mock_loader.assert_any_call("dir1", use_multithreading=True, silent_errors=True)
    mock_loader.assert_any_call("dir2", use_multithreading=True, silent_errors=True)

    mock_embeddings.assert_called_once_with(
        model="models/embedding-001",
        google_api_key=ANY,
    )

    mock_chroma.assert_called_once_with(
        embedding_function=mock_embeddings_instance,
        persist_directory="/path/to/storage",
        collection_metadata={"hnsw:space": "cosine"},
    )

    mock_llm.assert_called_once_with(
        model="gemini-pro",
        temperature=0.0,
        max_tokens=None,
        api_key="test-key",
    )

    # Verify the result has invoke method (it's our custom class)
    assert result is not None
    assert hasattr(result, "invoke")

    # Verify logger calls
    mock_logger.debug.assert_any_call("RAG: loaded chunks", location="dir1", count=2)
    mock_logger.debug.assert_any_call("RAG: loaded chunks", location="dir2", count=2)
    mock_logger.debug.assert_any_call("RAG: document scan complete")
    mock_logger.debug.assert_any_call("RAG: retriever prepared")
    mock_logger.debug.assert_any_call("RAG: prepared llm", llm="gemini-pro", location="dir1,dir2")
    mock_logger.debug.assert_any_call("RAG: retrieval chain ready")


@patch("plugins.rag.RunnablePassthrough")
@patch("plugins.rag.RunnableLambda")
@patch("plugins.rag.StrOutputParser")
@patch("plugins.rag.ChatPromptTemplate")
@patch("plugins.rag.DirectoryLoader")
@patch("plugins.rag.RecursiveCharacterTextSplitter")
@patch("plugins.rag.GoogleGenerativeAIEmbeddings")
@patch("plugins.rag.Chroma")
@patch("plugins.rag.ChatGoogleGenerativeAI")
def test_prepare_rag_tool_empty_location(
    mock_llm,
    mock_chroma,
    mock_embeddings,
    mock_textsplitter,
    mock_loader,
    mock_prompt_template,
    mock_output_parser,
    mock_runnable_lambda,
    mock_runnable_passthrough,
    mock_logger,
):
    # Setup mocks
    mock_loader_instance = Mock()
    mock_loader.return_value = mock_loader_instance
    mock_loader_instance.load_and_split.return_value = []

    mock_embeddings_instance = Mock()
    mock_embeddings.return_value = mock_embeddings_instance

    mock_chroma_instance = Mock()
    mock_chroma.return_value = mock_chroma_instance

    # Create a mock retriever that supports pipe operator
    mock_retriever = MagicMock()
    mock_retriever.__or__ = Mock(return_value=MagicMock())
    mock_chroma_instance.as_retriever.return_value = mock_retriever

    # Mock LLM
    mock_llm_instance = MagicMock()
    mock_llm_instance.__or__ = Mock(return_value=MagicMock())
    mock_llm.return_value = mock_llm_instance

    # Mock prompt
    mock_prompt = MagicMock()
    mock_prompt.__or__ = Mock(return_value=MagicMock())
    mock_prompt_template.from_template.return_value = mock_prompt

    # Mock output parser
    mock_parser_instance = MagicMock()
    mock_output_parser.return_value = mock_parser_instance

    # Mock RunnableLambda
    mock_lambda_instance = MagicMock()
    mock_runnable_lambda.return_value = mock_lambda_instance

    # Mock RunnablePassthrough
    mock_passthrough_instance = MagicMock()
    mock_runnable_passthrough.return_value = mock_passthrough_instance

    # Call function with empty location
    result = prepare_rag_tool(
        logger=mock_logger,
        rag_location="",
        rag_embedding_model="models/embedding-001",
        rag_vector_storage="/path/to/storage",
        google_api_key="test-key",
        rag_llm_model="gemini-pro",
    )

    # Empty string creates one empty location
    assert mock_loader.call_count == 1
    mock_loader.assert_called_with("", use_multithreading=True, silent_errors=True)

    # Verify result structure
    assert result is not None
    assert hasattr(result, "invoke")


@patch("plugins.rag.RunnablePassthrough")
@patch("plugins.rag.RunnableLambda")
@patch("plugins.rag.StrOutputParser")
@patch("plugins.rag.ChatPromptTemplate")
@patch("plugins.rag.DirectoryLoader")
@patch("plugins.rag.RecursiveCharacterTextSplitter")
@patch("plugins.rag.GoogleGenerativeAIEmbeddings")
@patch("plugins.rag.Chroma")
@patch("plugins.rag.ChatGoogleGenerativeAI")
def test_prepare_rag_tool_multiple_locations(
    mock_llm,
    mock_chroma,
    mock_embeddings,
    mock_textsplitter,
    mock_loader,
    mock_prompt_template,
    mock_output_parser,
    mock_runnable_lambda,
    mock_runnable_passthrough,
    mock_logger,
):
    # Setup mocks
    mock_loader_instance = Mock()
    mock_loader.return_value = mock_loader_instance
    mock_loader_instance.load_and_split.return_value = [Mock(), Mock()]

    mock_embeddings_instance = Mock()
    mock_embeddings.return_value = mock_embeddings_instance

    mock_chroma_instance = Mock()
    mock_chroma.return_value = mock_chroma_instance

    # Create a mock retriever that supports pipe operator
    mock_retriever = MagicMock()
    mock_retriever.__or__ = Mock(return_value=MagicMock())
    mock_chroma_instance.as_retriever.return_value = mock_retriever

    # Mock LLM
    mock_llm_instance = MagicMock()
    mock_llm_instance.__or__ = Mock(return_value=MagicMock())
    mock_llm.return_value = mock_llm_instance

    # Mock prompt
    mock_prompt = MagicMock()
    mock_prompt.__or__ = Mock(return_value=MagicMock())
    mock_prompt_template.from_template.return_value = mock_prompt

    # Mock output parser
    mock_parser_instance = MagicMock()
    mock_output_parser.return_value = mock_parser_instance

    # Mock RunnableLambda
    mock_lambda_instance = MagicMock()
    mock_runnable_lambda.return_value = mock_lambda_instance

    # Mock RunnablePassthrough
    mock_passthrough_instance = MagicMock()
    mock_runnable_passthrough.return_value = mock_passthrough_instance

    # Call function with two locations
    result = prepare_rag_tool(
        logger=mock_logger,
        rag_location="loc1,loc2",
        rag_embedding_model="models/embedding-001",
        rag_vector_storage="/path/to/storage",
        google_api_key="test-key",
        rag_llm_model="gemini-pro",
    )

    # Verify both locations were processed
    assert mock_loader.call_count == 2
    mock_loader.assert_any_call("loc1", use_multithreading=True, silent_errors=True)
    mock_loader.assert_any_call("loc2", use_multithreading=True, silent_errors=True)

    # Verify documents were added for each location
    assert mock_chroma_instance.add_documents.call_count == 2

    # Verify result structure
    assert result is not None
    assert hasattr(result, "invoke")


@patch("plugins.rag.gc.collect")
def test_garbage_collection_called(mock_gc_collect):
    """Test that garbage collection is called after processing each location."""
    with (
        patch("plugins.rag.DirectoryLoader") as mock_loader,
        patch("plugins.rag.RecursiveCharacterTextSplitter"),
        patch("plugins.rag.GoogleGenerativeAIEmbeddings"),
        patch("plugins.rag.Chroma") as mock_chroma,
        patch("plugins.rag.ChatGoogleGenerativeAI") as mock_llm,
        patch("plugins.rag.ChatPromptTemplate") as mock_prompt_template,
        patch("plugins.rag.StrOutputParser"),
        patch("plugins.rag.RunnableLambda"),
        patch("plugins.rag.RunnablePassthrough"),
    ):
        mock_loader_instance = Mock()
        mock_loader.return_value = mock_loader_instance
        mock_loader_instance.load_and_split.return_value = []

        mock_chroma_instance = Mock()
        mock_chroma.return_value = mock_chroma_instance
        mock_retriever = MagicMock()
        mock_retriever.__or__ = Mock(return_value=MagicMock())
        mock_chroma_instance.as_retriever.return_value = mock_retriever

        # Mock LLM to support pipe operator
        mock_llm_instance = MagicMock()
        mock_llm_instance.__or__ = Mock(return_value=MagicMock())
        mock_llm.return_value = mock_llm_instance

        # Mock prompt to support pipe operator
        mock_prompt = MagicMock()
        mock_prompt.__or__ = Mock(return_value=MagicMock())
        mock_prompt_template.from_template.return_value = mock_prompt

        logger = Mock()

        prepare_rag_tool(
            logger=logger,
            rag_location="loc1,loc2,loc3",
            rag_embedding_model="models/embedding-001",
            rag_vector_storage="/path/to/storage",
            google_api_key="test-key",
            rag_llm_model="gemini-pro",
        )

        # gc.collect should be called once for each location
        assert mock_gc_collect.call_count == 3
