from typing import Any

import structlog
from langchain.chains import RetrievalQA
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import DirectoryLoader
from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings


def prepare_rag_tool(
    logger: structlog.BoundLogger,
    rag_location: str,
    rag_embedding_model: str,
    google_api_key: str,
    rag_llm_model: str,
) -> RetrievalQA:
    """
    Prepare a RAG (Retrieval-Augmented Generation) tool for question answering.

    Args:
        logger: Structured logger instance
        rag_location: Comma-separated list of directory paths containing documents
        rag_embedding_model: Name of the Google embedding model to use
        google_api_key: Google API key for authentication
        rag_llm_model: Name of the Google Generative AI model to use for generation

    Returns:
        RetrievalQA chain configured with the specified models and documents
    """
    data: list[Document] = []
    locations: list[str] = rag_location.split(",")

    for location in locations:
        loader: DirectoryLoader = DirectoryLoader(location, use_multithreading=True, silent_errors=True)
        chunk: list[Document] = loader.load()
        logger.debug("RAG: loaded documents", location=location, count=len(chunk))
        data.extend(chunk)

    text_splitter: RecursiveCharacterTextSplitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=1000)
    docs: list[Document] = text_splitter.split_documents(data)

    embeddings: GoogleGenerativeAIEmbeddings = GoogleGenerativeAIEmbeddings(
        model=rag_embedding_model,
        google_api_key=google_api_key,  # pyright: ignore
    )

    # Create vector store and retriever
    vectorstore: InMemoryVectorStore = InMemoryVectorStore.from_documents(documents=docs, embedding=embeddings)
    retriever: Any = vectorstore.as_retriever()

    llm: ChatGoogleGenerativeAI = ChatGoogleGenerativeAI(
        model=rag_llm_model,
        temperature=0.0,
        max_tokens=None,
        api_key=google_api_key,
    )
    logger.debug(
        "RAG: prepared retrieval",
        llm=rag_llm_model,
        location=rag_location,
        count=len(data),
    )

    rag_chain: RetrievalQA = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=retriever,
        return_source_documents=True,  # to get source documents with answers
        chain_type="stuff",  # concatenates retrieved docs into prompt
    )

    return rag_chain
