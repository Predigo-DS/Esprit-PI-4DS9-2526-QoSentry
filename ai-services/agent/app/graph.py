import os
from typing import TypedDict, Annotated, NotRequired
import httpx
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from dotenv import load_dotenv

load_dotenv()

RAG_URL = os.getenv("RAG_SERVICE_URL", "http://rag:8001")


# ── Custom LangChain Retriever wrapping the RAG microservice ──────────────────
class QoSRetriever(BaseRetriever):
    rag_url: str = RAG_URL
    top_k: int = 5
    search_type: str = "hybrid"
    rrf_dense_weight: float = 0.7

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> list[Document]:
        with httpx.Client() as client:
            resp = client.post(
                f"{self.rag_url}/retrieve",
                json={
                    "query": query,
                    "top_k": self.top_k,
                    "search_type": self.search_type,
                    "rrf_dense_weight": self.rrf_dense_weight,
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
        return [
            Document(page_content=c["text"], metadata=c.get("metadata", {}))
            for c in data.get("chunks", [])
        ]

    async def _aget_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> list[Document]:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.rag_url}/retrieve",
                json={
                    "query": query,
                    "top_k": self.top_k,
                    "search_type": self.search_type,
                    "rrf_dense_weight": self.rrf_dense_weight,
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
        return [
            Document(page_content=c["text"], metadata=c.get("metadata", {}))
            for c in data.get("chunks", [])
        ]


# ── LLM : OpenAI-compatible providers via LangChain ──────────────────────────
def get_llm(
    model_name: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> ChatOpenAI:
    temperature = 1.0 if model_name and "gpt-oss-120b" in model_name else 0.2
    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
    )


# ── LangGraph State ───────────────────────────────────────────────────────────
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    sources: list[dict]
    context: str
    model: NotRequired[str]
    base_url: NotRequired[str]


# ── Node 1 : retrieve via LangChain Retriever ─────────────────────────────────
async def retrieve_node(state: AgentState, config: RunnableConfig) -> AgentState:
    last_human = next(
        (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None
    )
    query = last_human.content if last_human else ""

    cfg = (config or {}).get("configurable", {}) if config else {}
    search_type = cfg.get("search_type", "hybrid")
    rrf_dense_weight = cfg.get("rrf_dense_weight", 0.7)

    retriever = QoSRetriever(
        rag_url=RAG_URL,
        top_k=5,
        search_type=search_type,
        rrf_dense_weight=rrf_dense_weight,
    )
    docs = await retriever.ainvoke(query)

    context = "\n\n".join(doc.page_content for doc in docs)
    sources = [{"text": doc.page_content, "metadata": doc.metadata} for doc in docs]
    return {"context": context, "sources": sources}


# ── Node 2 : generate with via LangChain ─────────────────────────────────
async def generate_node(state: AgentState, config: RunnableConfig) -> AgentState:
    cfg = (config or {}).get("configurable", {}) if config else {}
    model_name = cfg.get("model") or state.get("model")
    base_url = cfg.get("base_url") or state.get("base_url")
    api_key = cfg.get("api_key")
    llm = get_llm(model_name=model_name, base_url=base_url, api_key=api_key)

    system = SystemMessage(
        content=(
            "You are QoSentry, an expert assistant on Quality of Service in networks. "
            "Use the retrieved context below to answer accurately. "
            "If the context is insufficient, say so clearly.\n\n"
            f"Context:\n{state.get('context', 'No context available.')}"
        )
    )

    response = await llm.ainvoke([system] + list(state["messages"]))
    return {"messages": [AIMessage(content=response.content)]}


# ── Graph definition ──────────────────────────────────────────────────────────
def build_graph(checkpointer=None):
    builder = StateGraph(AgentState)
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("generate", generate_node)
    builder.set_entry_point("retrieve")
    builder.add_edge("retrieve", "generate")
    builder.add_edge("generate", END)
    if checkpointer is not None:
        return builder.compile(checkpointer=checkpointer)
    return builder.compile()
