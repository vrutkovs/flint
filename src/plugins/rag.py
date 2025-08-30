import gc
from typing import Any

import structlog
from langchain.chains import RetrievalQA
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma.vectorstores import Chroma
from langchain_community.document_loaders import DirectoryLoader
from langchain_core.documents import Document
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from pydantic import SecretStr


def prepare_rag_tool(
    logger: structlog.BoundLogger,
    rag_location: str,
    rag_embedding_model: str,
    rag_vector_storage: str,
    google_api_key: str,
    rag_llm_model: str,
) -> RetrievalQA:
    """
    Prepare a RAG (Retrieval-Augmented Generation) tool for question answering.

    Args:
        logger: Structured logger instance
        rag_location: Comma-separated list of directory paths containing documents
        rag_embedding_model: Name of the Google embedding model to use
        rag_vector_storage: Location of the vector storage to use
        google_api_key: Google API key for authentication
        rag_llm_model: Name of the Google Generative AI model to use for generation

    Returns:
        RetrievalQA chain configured with the specified models and documents
    """
    locations: list[str] = rag_location.split(",")

    # Create vector store
    embeddings: GoogleGenerativeAIEmbeddings = GoogleGenerativeAIEmbeddings(
        model=rag_embedding_model,
        google_api_key=SecretStr(google_api_key),
    )
    vector_store: Chroma = Chroma(
        embedding_function=embeddings,
        persist_directory=rag_vector_storage,
        collection_metadata={"hnsw:space": "cosine"},
    )

    text_splitter: RecursiveCharacterTextSplitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=1000)

    for location in locations:
        loader: DirectoryLoader = DirectoryLoader(location, use_multithreading=True, silent_errors=True)
        chunk: list[Document] = loader.load_and_split(text_splitter)
        logger.debug("RAG: loaded chunks", location=location, count=len(chunk))
        vector_store.add_documents(documents=chunk)
        del loader, chunk
        gc.collect()

    logger.debug(
        "RAG: document scan complete",
    )

    # Create retriever
    retriever: Any = vector_store.as_retriever()
    logger.debug(
        "RAG: retriever prepared",
    )

    llm: ChatGoogleGenerativeAI = ChatGoogleGenerativeAI(
        model=rag_llm_model,
        temperature=0.0,
        max_tokens=None,
        api_key=google_api_key,
    )
    logger.debug(
        "RAG: prepared llm",
        llm=rag_llm_model,
        location=rag_location,
    )

    rag_chain: RetrievalQA = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=retriever,
        return_source_documents=True,  # to get source documents with answers
        chain_type="stuff",  # concatenates retrieved docs into prompt
    )

    logger.debug(
        "RAG: retrieval QA chain ready",
    )

    return rag_chain
