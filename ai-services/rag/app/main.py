import os
from typing import Optional
from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
from embeddings import get_embedder
from vector_store import VectorStoreClient
from contextlib import asynccontextmanager

models = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Loading AI models and connecting to DB...")
    models["embedder"] = get_embedder()
    models["vs"] = VectorStoreClient()
    print("System Ready.")
    yield
    models.clear()

app      = FastAPI(title="QoS-Buddy RAG Service", version="1.0.0", lifespan=lifespan)


class IngestTextRequest(BaseModel):
    text: str
    metadata: Optional[dict] = {}


class RetrieveRequest(BaseModel):
    query: str
    top_k: int = int(os.getenv("TOP_K", 5))


@app.get("/health")
async def health():
    if "embedder" not in models:
        return {"status": "starting", "service": "rag"}
    return {"status": "ok", "service": "rag"}


@app.post("/ingest/text")
async def ingest_text(req: IngestTextRequest):
    if "embedder" not in models:
        raise HTTPException(status_code=503, detail="Models still loading")
    try:
        ids = models["vs"].ingest_text(req.text, req.metadata, models["embedder"])
        return {"ingested_chunks": len(ids), "ids": ids}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest/file")
async def ingest_file(file: UploadFile = File(...)):
    try:
        content  = await file.read()
        filename = file.filename or "unknown"
        text     = models["vs"].extract_pdf_text(content) if filename.endswith(".pdf") else content.decode("utf-8")
        ids      = models["vs"].ingest_text(text, {"source": filename}, models["embedder"])
        return {"filename": filename, "ingested_chunks": len(ids), "ids": ids}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/retrieve")
async def retrieve(req: RetrieveRequest):
    try:
        vec    = models["embedder"].encode(req.query).tolist()
        chunks = models["vs"].search(vec, top_k=req.top_k)
        return {"chunks": chunks, "query": req.query}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/collection")
async def reset_collection():
    try:
        models["vs"].reset_collection()
        return {"status": "collection reset"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))