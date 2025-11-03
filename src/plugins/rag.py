import gc
from typing import Any

import structlog
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma.vectorstores import Chroma
from langchain_community.document_loaders import DirectoryLoader
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from pydantic import SecretStr


def prepare_rag_tool(
    logger: structlog.BoundLogger,
    rag_location: str,
    rag_embedding_model: str,
    rag_vector_storage: str,
    google_api_key: str,
    rag_llm_model: str,
) -> Any:
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
        LCEL chain configured with the specified models and documents
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

    text_splitter: RecursiveCharacterTextSplitter = RecursiveCharacterTextSplitter()

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

    # Create the RAG prompt template
    template = """Answer the following question based on the provided context.
If you don't know the answer based on the context, say so.
Use the information from the context to provide a comprehensive answer.

Context:
{context}

Question: {question}

Answer:"""

    prompt = ChatPromptTemplate.from_template(template)

    # Format the retrieved documents
    def format_docs(docs: list[Document]) -> str:
        return "\n\n".join(doc.page_content for doc in docs)

    # Create the LCEL chain
    # Build the chain step by step to avoid issues with mocking
    context_retriever = retriever | RunnableLambda(format_docs)
    input_dict = {
        "context": context_retriever,
        "question": RunnablePassthrough(),
    }

    # Chain the components together
    rag_chain = input_dict | prompt | llm | StrOutputParser()

    # Wrap to return both answer and source documents (similar to RetrievalQA behavior)
    # Make the wrapper callable to handle invocations properly
    class RAGChainWithSources:
        def __init__(self, chain, retriever):
            self.chain = chain
            self.retriever = retriever

        def invoke(self, question: str) -> dict[str, Any]:
            answer = self.chain.invoke(question)
            source_documents = self.retriever.invoke(question)
            return {
                "answer": answer,
                "source_documents": source_documents,
            }

    rag_chain_with_sources = RAGChainWithSources(rag_chain, retriever)

    logger.debug(
        "RAG: retrieval chain ready",
    )

    return rag_chain_with_sources
