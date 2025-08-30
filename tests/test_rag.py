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


@patch("src.plugins.rag.DirectoryLoader")
@patch("src.plugins.rag.RecursiveCharacterTextSplitter")
@patch("src.plugins.rag.GoogleGenerativeAIEmbeddings")
@patch("src.plugins.rag.Chroma")
@patch("src.plugins.rag.ChatGoogleGenerativeAI")
@patch("src.plugins.rag.RetrievalQA")
def test_prepare_rag_tool_success(
    mock_retrievalqa,
    mock_llm,
    mock_chroma,
    mock_embeddings,
    mock_textsplitter,
    mock_loader,
    mock_logger,
    mock_documents,
):
    # Setup mocks
    mock_loader_instance = mock_loader.return_value
    mock_loader_instance.load_and_split.return_value = mock_documents

    mock_textsplitter_instance = mock_textsplitter.return_value

    mock_embeddings_instance = mock_embeddings.return_value

    mock_chroma_instance = mock_chroma.return_value
    mock_chroma_instance.as_retriever.return_value = "retriever"

    mock_llm_instance = mock_llm.return_value

    mock_rag_chain = MagicMock()
    mock_retrievalqa.from_chain_type.return_value = mock_rag_chain

    # Call function
    result = prepare_rag_tool(
        logger=mock_logger,
        rag_location="dir1,dir2",
        rag_embedding_model="embedding-model",
        rag_vector_storage="vector-storage-location",
        google_api_key="api-key",
        rag_llm_model="llm-model",
    )

    # Assertions
    assert result == mock_rag_chain
    mock_loader.assert_any_call("dir1", use_multithreading=True, silent_errors=True)
    mock_loader.assert_any_call("dir2", use_multithreading=True, silent_errors=True)
    assert mock_loader_instance.load_and_split.call_count == 2
    mock_textsplitter.assert_called_once_with(chunk_size=1000, chunk_overlap=1000)
    mock_loader_instance.load_and_split.assert_any_call(mock_textsplitter_instance)
    mock_embeddings.assert_called_once_with(model="embedding-model", google_api_key=ANY)
    mock_chroma.assert_called_once_with(
        embedding_function=mock_embeddings_instance,
        persist_directory="vector-storage-location",
        collection_metadata={"hnsw:space": "cosine"},
    )
    mock_chroma_instance.add_documents.assert_any_call(documents=mock_documents)
    assert mock_chroma_instance.add_documents.call_count == 2
    mock_chroma_instance.as_retriever.assert_called_once()
    mock_llm.assert_called_once_with(model="llm-model", temperature=0.0, max_tokens=None, api_key="api-key")
    mock_retrievalqa.from_chain_type.assert_called_once_with(
        llm=mock_llm_instance, retriever="retriever", return_source_documents=True, chain_type="stuff"
    )
    mock_logger.debug.assert_any_call("RAG: loaded chunks", location="dir1", count=len(mock_documents))
    mock_logger.debug.assert_any_call("RAG: loaded chunks", location="dir2", count=len(mock_documents))


@patch("src.plugins.rag.DirectoryLoader")
@patch("src.plugins.rag.RecursiveCharacterTextSplitter")
@patch("src.plugins.rag.GoogleGenerativeAIEmbeddings")
@patch("src.plugins.rag.Chroma")
@patch("src.plugins.rag.ChatGoogleGenerativeAI")
@patch("src.plugins.rag.RetrievalQA")
def test_prepare_rag_tool_empty_location(
    mock_retrievalqa,
    mock_llm,
    mock_chroma,
    mock_embeddings,
    mock_textsplitter,
    mock_loader,
    mock_logger,
):
    # Setup mocks
    mock_loader_instance = mock_loader.return_value
    mock_loader_instance.load_and_split.return_value = []

    mock_textsplitter_instance = mock_textsplitter.return_value

    mock_chroma_instance = mock_chroma.return_value
    mock_chroma_instance.as_retriever.return_value = "retriever"

    mock_rag_chain = MagicMock()
    mock_retrievalqa.from_chain_type.return_value = mock_rag_chain

    # Call function with empty location
    result = prepare_rag_tool(
        logger=mock_logger,
        rag_location="",
        rag_embedding_model="embedding-model",
        rag_vector_storage="vector-storage-location",
        google_api_key="api-key",
        rag_llm_model="llm-model",
    )

    assert result == mock_rag_chain
    mock_loader.assert_called_once_with("", use_multithreading=True, silent_errors=True)
    mock_loader_instance.load_and_split.assert_called_once_with(mock_textsplitter_instance)
    mock_chroma_instance.add_documents.assert_called_once_with(documents=[])
    mock_logger.debug.assert_any_call("RAG: loaded chunks", location="", count=0)


@patch("src.plugins.rag.DirectoryLoader")
@patch("src.plugins.rag.RecursiveCharacterTextSplitter")
@patch("src.plugins.rag.GoogleGenerativeAIEmbeddings")
@patch("src.plugins.rag.Chroma")
@patch("src.plugins.rag.ChatGoogleGenerativeAI")
@patch("src.plugins.rag.RetrievalQA")
def test_prepare_rag_tool_multiple_locations(
    mock_retrievalqa,
    mock_llm,
    mock_chroma,
    mock_embeddings,
    mock_textsplitter,
    mock_loader,
    mock_logger,
):
    # Setup mocks
    mock_loader_instance = mock_loader.return_value
    side_effect_docs = [[MagicMock()], [MagicMock(), MagicMock()]]
    mock_loader_instance.load_and_split.side_effect = side_effect_docs

    mock_textsplitter_instance = mock_textsplitter.return_value

    mock_chroma_instance = mock_chroma.return_value
    mock_chroma_instance.as_retriever.return_value = "retriever"

    mock_rag_chain = MagicMock()
    mock_retrievalqa.from_chain_type.return_value = mock_rag_chain

    # Call function with two locations
    result = prepare_rag_tool(
        logger=mock_logger,
        rag_location="loc1,loc2",
        rag_embedding_model="embedding-model",
        rag_vector_storage="vector-storage-location",
        google_api_key="api-key",
        rag_llm_model="llm-model",
    )

    assert result == mock_rag_chain
    assert mock_loader.call_count == 2
    assert mock_loader_instance.load_and_split.call_count == 2
    mock_loader_instance.load_and_split.assert_any_call(mock_textsplitter_instance)
    assert mock_chroma_instance.add_documents.call_count == 2
    mock_chroma_instance.add_documents.assert_any_call(documents=side_effect_docs[0])
    mock_chroma_instance.add_documents.assert_any_call(documents=side_effect_docs[1])
    mock_logger.debug.assert_any_call("RAG: loaded chunks", location="loc1", count=1)
    mock_logger.debug.assert_any_call("RAG: loaded chunks", location="loc2", count=2)
