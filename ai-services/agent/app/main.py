from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from graph import build_graph

app   = FastAPI(title="QoS-Buddy Agent Service", version="1.0.0")
graph = build_graph()


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    session_id: str
    response: str
    sources: list[dict] = []


@app.get("/health")
async def health():
    return {"status": "ok", "service": "agent"}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    Send a message to the QoS-Buddy agent.
    The agent retrieves context from RAG then generates an answer with the LLM.
    """
    try:
        result = await graph.ainvoke(
            {"messages": [{"role": "user", "content": req.message}]},
            config={"configurable": {"session_id": req.session_id}},
        )
        return ChatResponse(
            session_id=req.session_id,
            response=result["messages"][-1].content,
            sources=result.get("sources", []),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))