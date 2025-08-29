from unittest.mock import ANY, MagicMock, Mock, patch

import pytest

from src.plugins.rag import prepare_rag_tool


@pytest.fixture
def mock_logger():
    return Mock()


@pytest.fixture
def mock_documents():
    doc1 = MagicMock()
    doc2 = MagicMock()
    return [doc1, doc2]


@pytest.fixture
def mock_split_documents():
    doc1 = MagicMock()
    doc2 = MagicMock()
    return [doc1, doc2]


@patch("src.plugins.rag.DirectoryLoader")
@patch("src.plugins.rag.RecursiveCharacterTextSplitter")
@patch("src.plugins.rag.GoogleGenerativeAIEmbeddings")
@patch("src.plugins.rag.InMemoryVectorStore")
@patch("src.plugins.rag.ChatGoogleGenerativeAI")
@patch("src.plugins.rag.RetrievalQA")
def test_prepare_rag_tool_success(
    mock_retrievalqa,
    mock_llm,
    mock_vectorstore,
    mock_embeddings,
    mock_textsplitter,
    mock_loader,
    mock_logger,
    mock_documents,
    mock_split_documents,
):
    # Setup mocks
    mock_loader_instance = mock_loader.return_value
    mock_loader_instance.load.return_value = mock_documents

    mock_textsplitter_instance = mock_textsplitter.return_value
    mock_textsplitter_instance.split_documents.return_value = mock_split_documents

    mock_embeddings_instance = mock_embeddings.return_value

    mock_vectorstore_instance = mock_vectorstore.from_documents.return_value
    mock_vectorstore_instance.as_retriever.return_value = "retriever"

    mock_llm_instance = mock_llm.return_value

    mock_rag_chain = MagicMock()
    mock_retrievalqa.from_chain_type.return_value = mock_rag_chain

    # Call function
    result = prepare_rag_tool(
        logger=mock_logger,
        rag_location="dir1,dir2",
        rag_embedding_model="embedding-model",
        google_api_key="api-key",
        rag_llm_model="llm-model",
    )

    # Assertions
    assert result == mock_rag_chain
    mock_loader.assert_any_call("dir1", use_multithreading=True, silent_errors=True)
    mock_loader.assert_any_call("dir2", use_multithreading=True, silent_errors=True)
    assert mock_loader_instance.load.call_count == 2
    mock_textsplitter.assert_called_once_with(chunk_size=1000, chunk_overlap=1000)
    mock_textsplitter_instance.split_documents.assert_called_once()
    mock_embeddings.assert_called_once_with(model="embedding-model", google_api_key=ANY)
    mock_vectorstore.from_documents.assert_called_once_with(
        documents=mock_split_documents, embedding=mock_embeddings_instance
    )
    mock_vectorstore_instance.as_retriever.assert_called_once()
    mock_llm.assert_called_once_with(model="llm-model", temperature=0.0, max_tokens=None, api_key="api-key")
    mock_retrievalqa.from_chain_type.assert_called_once_with(
        llm=mock_llm_instance, retriever="retriever", return_source_documents=True, chain_type="stuff"
    )
    mock_logger.debug.assert_any_call("RAG: loaded documents", location="dir1", count=len(mock_documents))
    mock_logger.debug.assert_any_call("RAG: loaded documents", location="dir2", count=len(mock_documents))
    mock_logger.debug.assert_any_call(
        "RAG: prepared retrieval",
        llm="llm-model",
        location="dir1,dir2",
        count=4,
    )


@patch("src.plugins.rag.DirectoryLoader")
@patch("src.plugins.rag.RecursiveCharacterTextSplitter")
@patch("src.plugins.rag.GoogleGenerativeAIEmbeddings")
@patch("src.plugins.rag.InMemoryVectorStore")
@patch("src.plugins.rag.ChatGoogleGenerativeAI")
@patch("src.plugins.rag.RetrievalQA")
def test_prepare_rag_tool_empty_location(
    mock_retrievalqa,
    mock_llm,
    mock_vectorstore,
    mock_embeddings,
    mock_textsplitter,
    mock_loader,
    mock_logger,
):
    # Setup mocks
    mock_loader_instance = mock_loader.return_value
    mock_loader_instance.load.return_value = []

    mock_textsplitter_instance = mock_textsplitter.return_value
    mock_textsplitter_instance.split_documents.return_value = []

    mock_vectorstore_instance = mock_vectorstore.from_documents.return_value
    mock_vectorstore_instance.as_retriever.return_value = "retriever"

    mock_rag_chain = MagicMock()
    mock_retrievalqa.from_chain_type.return_value = mock_rag_chain

    # Call function with empty location
    result = prepare_rag_tool(
        logger=mock_logger,
        rag_location="",
        rag_embedding_model="embedding-model",
        google_api_key="api-key",
        rag_llm_model="llm-model",
    )

    assert result == mock_rag_chain
    mock_loader.assert_called_once_with("", use_multithreading=True, silent_errors=True)
    mock_loader_instance.load.assert_called_once()
    mock_textsplitter_instance.split_documents.assert_called_once_with([])
    mock_logger.debug.assert_any_call("RAG: loaded documents", location="", count=0)
    mock_logger.debug.assert_any_call(
        "RAG: prepared retrieval",
        llm="llm-model",
        location="",
        count=0,
    )


@patch("src.plugins.rag.DirectoryLoader")
@patch("src.plugins.rag.RecursiveCharacterTextSplitter")
@patch("src.plugins.rag.GoogleGenerativeAIEmbeddings")
@patch("src.plugins.rag.InMemoryVectorStore")
@patch("src.plugins.rag.ChatGoogleGenerativeAI")
@patch("src.plugins.rag.RetrievalQA")
def test_prepare_rag_tool_multiple_locations(
    mock_retrievalqa,
    mock_llm,
    mock_vectorstore,
    mock_embeddings,
    mock_textsplitter,
    mock_loader,
    mock_logger,
):
    # Setup mocks
    mock_loader_instance = mock_loader.return_value
    mock_loader_instance.load.side_effect = [[MagicMock()], [MagicMock(), MagicMock()]]

    mock_textsplitter_instance = mock_textsplitter.return_value
    mock_textsplitter_instance.split_documents.return_value = [MagicMock(), MagicMock(), MagicMock()]

    mock_vectorstore_instance = mock_vectorstore.from_documents.return_value
    mock_vectorstore_instance.as_retriever.return_value = "retriever"

    mock_rag_chain = MagicMock()
    mock_retrievalqa.from_chain_type.return_value = mock_rag_chain

    # Call function with two locations
    result = prepare_rag_tool(
        logger=mock_logger,
        rag_location="loc1,loc2",
        rag_embedding_model="embedding-model",
        google_api_key="api-key",
        rag_llm_model="llm-model",
    )

    assert result == mock_rag_chain
    assert mock_loader.call_count == 2
    assert mock_loader_instance.load.call_count == 2
    mock_textsplitter_instance.split_documents.assert_called_once()
    mock_logger.debug.assert_any_call("RAG: loaded documents", location="loc1", count=1)
    mock_logger.debug.assert_any_call("RAG: loaded documents", location="loc2", count=2)
    mock_logger.debug.assert_any_call(
        "RAG: prepared retrieval",
        llm="llm-model",
        location="loc1,loc2",
        count=3,
    )
