import os
from typing import TypedDict, Annotated

import httpx
from langchain_groq import ChatGroq
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

RAG_URL   = os.getenv("RAG_SERVICE_URL", "http://rag:8001")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3-8b-8192")
GROQ_KEY  = os.getenv("GROQ_API_KEY")


# ── Custom LangChain Retriever wrapping the RAG microservice ──────────────────
class QoSRetriever(BaseRetriever):
    rag_url: str = RAG_URL
    top_k: int = 5

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> list[Document]:
        with httpx.Client() as client:
            resp = client.post(
                f"{self.rag_url}/retrieve",
                json={"query": query, "top_k": self.top_k},
                timeout=10.0,
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
                json={"query": query, "top_k": self.top_k},
                timeout=10.0,
            )
            resp.raise_for_status()
            data = resp.json()
        return [
            Document(page_content=c["text"], metadata=c.get("metadata", {}))
            for c in data.get("chunks", [])
        ]


# ── LLM : Groq via LangChain ──────────────────────────────────────────────────
def get_llm() -> ChatGroq:
    return ChatGroq(
        model=LLM_MODEL,
        groq_api_key=GROQ_KEY,
        temperature=0.2,
    )


# ── LangGraph State ───────────────────────────────────────────────────────────
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    sources:  list[dict]
    context:  str


# ── Node 1 : retrieve via LangChain Retriever ─────────────────────────────────
async def retrieve_node(state: AgentState) -> AgentState:
    last_human = next(
        (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), None
    )
    query = last_human.content if last_human else ""

    retriever = QoSRetriever(rag_url=RAG_URL, top_k=5)
    docs = await retriever.ainvoke(query)

    context = "\n\n".join(doc.page_content for doc in docs)
    sources = [{"text": doc.page_content, "metadata": doc.metadata} for doc in docs]
    return {"context": context, "sources": sources}


# ── Node 2 : generate with Groq via LangChain ─────────────────────────────────
async def generate_node(state: AgentState) -> AgentState:
    llm = get_llm()

    system = SystemMessage(content=(
        "You are QoS-Buddy, an expert assistant on Quality of Service in networks. "
        "Use the retrieved context below to answer accurately. "
        "If the context is insufficient, say so clearly.\n\n"
        f"Context:\n{state.get('context', 'No context available.')}"
    ))

    response = await llm.ainvoke([system] + list(state["messages"]))
    return {"messages": [AIMessage(content=response.content)]}


# ── Graph definition ──────────────────────────────────────────────────────────
def build_graph():
    builder = StateGraph(AgentState)
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("generate", generate_node)
    builder.set_entry_point("retrieve")
    builder.add_edge("retrieve", "generate")
    builder.add_edge("generate", END)
    return builder.compile()