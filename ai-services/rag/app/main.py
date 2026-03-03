import os
from typing import Optional
from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
from embeddings import get_embedder
from vector_store import VectorStoreClient

app      = FastAPI(title="QoS-Buddy RAG Service", version="1.0.0")
embedder = get_embedder()
vs       = VectorStoreClient()


class IngestTextRequest(BaseModel):
    text: str
    metadata: Optional[dict] = {}


class RetrieveRequest(BaseModel):
    query: str
    top_k: int = int(os.getenv("TOP_K", 5))


@app.get("/health")
async def health():
    return {"status": "ok", "service": "rag"}


@app.post("/ingest/text")
async def ingest_text(req: IngestTextRequest):
    try:
        ids = vs.ingest_text(req.text, req.metadata, embedder)
        return {"ingested_chunks": len(ids), "ids": ids}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest/file")
async def ingest_file(file: UploadFile = File(...)):
    try:
        content  = await file.read()
        filename = file.filename or "unknown"
        text     = vs.extract_pdf_text(content) if filename.endswith(".pdf") else content.decode("utf-8")
        ids      = vs.ingest_text(text, {"source": filename}, embedder)
        return {"filename": filename, "ingested_chunks": len(ids), "ids": ids}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/retrieve")
async def retrieve(req: RetrieveRequest):
    try:
        vec    = embedder.encode(req.query).tolist()
        chunks = vs.search(vec, top_k=req.top_k)
        return {"chunks": chunks, "query": req.query}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/collection")
async def reset_collection():
    try:
        vs.reset_collection()
        return {"status": "collection reset"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))