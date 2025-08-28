from langchain_community.document_loaders import DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_core.vectorstores import InMemoryVectorStore
from langchain.chains import RetrievalQA


def prepare_rag_tool(
    logger, rag_location, rag_embedding_model, google_api_key, rag_llm_model
):
    data = []
    for location in rag_location.split(","):
        loader = DirectoryLoader(location, use_multithreading=True, silent_errors=True)
        chunk = loader.load()
        logger.debug("RAG: loaded documents", location=location, count=len(data))
        data.extend(chunk)

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=1000)
    docs = text_splitter.split_documents(data)

    embeddings = GoogleGenerativeAIEmbeddings(
        model=rag_embedding_model, google_api_key=google_api_key
    )

    # Create vector store and retriever
    vectorstore = InMemoryVectorStore.from_documents(
        documents=docs, embedding=embeddings
    )
    retriever = vectorstore.as_retriever()

    llm = ChatGoogleGenerativeAI(
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
    return RetrievalQA.from_chain_type(
        llm=llm,
        retriever=retriever,
        return_source_documents=True,  # to get source documents with answers
        chain_type="stuff",  # concatenates retrieved docs into prompt
    )
