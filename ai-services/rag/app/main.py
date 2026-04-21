<<<<<<< HEAD
import os
import sys
import asyncio
import gc
import time
from typing import Optional
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from embeddings import get_embedder
from vector_store import VectorStoreClient
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

models = {}
warmup_state = {
    "status": "idle",
    "last_error": None,
}
warmup_lock = asyncio.Lock()
model_loaded = False
reranker = None
last_activity_time = time.time()
IDLE_TIMEOUT_SECONDS = int(os.getenv("MODEL_IDLE_TIMEOUT", "300"))  # 5 minutes default


def _warmup_response():
    return {
        "status": warmup_state["status"],
        "last_error": warmup_state["last_error"],
    }


async def _run_warmup():
    if "embedder" not in models or "vs" not in models:
        return

    async with warmup_lock:
        if warmup_state["status"] == "ready":
            return

        warmup_state["status"] = "warming"
        warmup_state["last_error"] = None

        try:
            models["embedder"].encode(["qosentry warmup"])
            models["vs"].total_chunks()
            _update_activity_time()
            warmup_state["status"] = "ready"
        except Exception as e:
            warmup_state["status"] = "error"
            warmup_state["last_error"] = str(e)


def _ensure_models_loaded():
    """Lazy-load models if they've been unloaded."""
    global model_loaded
    if not model_loaded:
        print("Loading AI models and connecting to DB...")
        models["embedder"] = get_embedder()
        models["vs"] = VectorStoreClient(embedder=models["embedder"])
        warmup_state["status"] = "idle"
        warmup_state["last_error"] = None
        asyncio.create_task(_run_warmup())
        model_loaded = True


def _init_reranker():
    """Initialize the cross-encoder reranker on CPU."""
    global reranker
    if reranker is None:
        try:
            from sentence_transformers import CrossEncoder
            import os
            
            # Check if model is cached
            hf_cache = os.path.expanduser("~/.cache/huggingface/hub")
            model_dir = os.path.join(hf_cache, "models--Qwen--Qwen3-Reranker-0.6B")
            model_path = None
            
            if os.path.exists(model_dir):
                # Find the snapshot directory
                snapshots_dir = os.path.join(model_dir, "snapshots")
                if os.path.exists(snapshots_dir):
                    snapshots = os.listdir(snapshots_dir)
                    if snapshots:
                        model_path = os.path.join(snapshots_dir, snapshots[0])
                        print(f"Found cached reranker model at: {model_path}", flush=True)
            
            print("Loading reranker model to CPU...", flush=True)
            sys.stdout.flush()
            
            if model_path:
                print(f"Loading from cached path: {model_path}", flush=True)
                reranker = CrossEncoder(model_path)
            else:
                print("Loading from model name (may download)...", flush=True)
                reranker = CrossEncoder('Qwen/Qwen3-Reranker-0.6B')
            
            print("Reranker loaded successfully on CPU.", flush=True)
            sys.stdout.flush()
        except Exception as e:
            import traceback
            print(f"Warning: Could not load reranker: {e}", flush=True)
            traceback.print_exc()
            reranker = None


def _unload_models():
    """Unload all models to free RAM."""
    global model_loaded, reranker
    if "embedder" in models:
        print("Unloading embedding model...")
        del models["embedder"]
        del models["vs"]
        model_loaded = False
    
    if reranker is not None:
        print("Unloading reranker model...")
        del reranker
        reranker = None
    
    gc.collect()
    print("All models unloaded. RAM freed.")


def _check_idle_timeout():
    """Check if models should be unloaded due to idle timeout."""
    global last_activity_time
    if time.time() - last_activity_time > IDLE_TIMEOUT_SECONDS:
        print(f"Idle timeout reached ({IDLE_TIMEOUT_SECONDS}s). Unloading models...")
        _unload_models()
        return True
    return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Loading AI models and connecting to DB...", flush=True)
    try:
        models["embedder"] = get_embedder()
        print("Embedding model loaded successfully", flush=True)
        
        models["vs"] = VectorStoreClient(embedder=models["embedder"])
        print("Vector store connected", flush=True)
        
        _init_reranker()
        
        warmup_state["status"] = "idle"
        warmup_state["last_error"] = None
        
        async def _run_warmup_with_timeout():
            try:
                await asyncio.wait_for(_run_warmup(), timeout=30.0)
            except asyncio.TimeoutError:
                print("Warning: Warmup timed out, continuing anyway", flush=True)
            except Exception as e:
                print(f"Warning: Warmup failed: {e}", flush=True)
        
        asyncio.create_task(_run_warmup_with_timeout())
        print("System Ready.", flush=True)
    except Exception as e:
        print(f"Startup error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        raise
    yield
    _unload_models()


app = FastAPI(title="QoS-Buddy RAG Service", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class IngestTextRequest(BaseModel):
    text: str
    metadata: Optional[dict] = {}


class IngestBatchRequest(BaseModel):
    documents: list[dict]


class RetrieveRequest(BaseModel):
    query: str
    top_k: int = int(os.getenv("TOP_K", 10))
    search_type: str = "hybrid"  # Options: "hybrid", "semantic", "keyword"
    tenant_id: Optional[str] = None
    data_category: Optional[str] = None
    access_levels: Optional[list[str]] = None
    content_type: Optional[str] = None
    vendor: Optional[str] = None
    min_quality_score: Optional[int] = None
    rrf_dense_weight: Optional[float] = 0.8  # For hybrid: 0.0-1.0 (dense weight)
    min_relevance_score: Optional[float] = 0.4  # Minimum threshold (0.0-1.0)
    rerank: bool = True  # Enable cross-encoder reranking
    rerank_top_n: int = 50  # Number of docs to rerank


def _require_ready():
    if "embedder" not in models or "vs" not in models:
        raise HTTPException(status_code=503, detail="Models still loading")


def _update_activity_time():
    """Update the last activity timestamp."""
    global last_activity_time
    last_activity_time = time.time()


@app.get("/health")
async def health():
    if "embedder" not in models:
        return {"status": "starting", "service": "rag", "warmup": _warmup_response()}
    return {"status": "ok", "service": "rag", "warmup": _warmup_response()}


@app.post("/warmup")
async def warmup():
    _require_ready()

    if warmup_state["status"] != "warming" and warmup_state["status"] != "ready":
        asyncio.create_task(_run_warmup())

    return _warmup_response()


@app.post("/unload")
async def unload():
    """Manually unload all models to free RAM. Models will reload on next request."""
    _unload_models()
    return {"status": "unloaded", "message": "All models unloaded"}


@app.get("/status")
async def get_status():
    """Get current model status."""
    return {
        "embedder_loaded": "embedder" in models,
        "reranker_loaded": reranker is not None,
        "idle_seconds": int(time.time() - last_activity_time),
        "idle_timeout_seconds": IDLE_TIMEOUT_SECONDS,
        "device": "cpu",
    }


@app.post("/ingest/text")
async def ingest_text(req: IngestTextRequest):
    _require_ready()
    try:
        ids = models["vs"].ingest_text(req.text, req.metadata, models["embedder"])
        return {"ingested_chunks": len(ids), "ids": ids}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest/file")
async def ingest_file(file: UploadFile = File(...)):
    _require_ready()
    try:
        content = await file.read()
        filename = file.filename or "unknown"
        text = (
            models["vs"].extract_pdf_text(content)
            if filename.endswith(".pdf")
            else content.decode("utf-8")
        )
        ids = models["vs"].ingest_text(text, {"source": filename}, models["embedder"])
        return {"filename": filename, "ingested_chunks": len(ids), "ids": ids}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest/batch")
async def ingest_batch(req: IngestBatchRequest):
    _require_ready()
    try:
        total_docs = len(req.documents)
        total_chunks = 0
        sources: dict[str, int] = {}
        errors: list[dict] = []

        for i, doc in enumerate(req.documents):
            text = doc.get("text", "")
            if not text or not text.strip():
                errors.append({"index": i, "error": "empty text"})
                continue

            metadata = doc.get("metadata", {})
            source = metadata.get("source", f"doc_{i}")
            try:
                ids = models["vs"].ingest_text(text, metadata, models["embedder"])
                total_chunks += len(ids)
                sources[source] = sources.get(source, 0) + len(ids)
            except Exception as e:
                errors.append({"index": i, "source": source, "error": str(e)})

        return {
            "total_documents": total_docs,
            "ingested_documents": total_docs - len(errors),
            "total_chunks": total_chunks,
            "sources": sources,
            "errors": errors,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/retrieve")
async def retrieve(req: RetrieveRequest):
    _ensure_models_loaded()
    _require_ready()
    _update_activity_time()
    
    # Check idle timeout before processing
    _check_idle_timeout()
    _require_ready()
    
    try:
        # Perform initial search with embedding model
        if req.search_type == "hybrid":
            chunks = models["vs"].hybrid_search(
                query=req.query,
                embedder=models["embedder"],
                top_k=req.rerank_top_n if req.rerank else req.top_k,
                tenant_id=req.tenant_id,
                data_category=req.data_category,
                access_levels=req.access_levels,
                content_type=req.content_type,
                vendor=req.vendor,
                min_quality_score=req.min_quality_score,
                dense_weight=req.rrf_dense_weight,
                min_score=req.min_relevance_score,
            )
        elif req.search_type == "semantic":
            vec = models["embedder"].encode([req.query]).tolist()[0]
            chunks = models["vs"].search(
                vec, top_k=req.rerank_top_n if req.rerank else req.top_k,
                tenant_id=req.tenant_id, data_category=req.data_category,
                access_levels=req.access_levels, content_type=req.content_type,
                vendor=req.vendor, min_quality_score=req.min_quality_score,
                min_score=req.min_relevance_score,
            )
        elif req.search_type == "keyword":
            chunks = models["vs"].keyword_search(
                query=req.query,
                embedder=models["embedder"],
                top_k=req.rerank_top_n if req.rerank else req.top_k,
                tenant_id=req.tenant_id,
                data_category=req.data_category,
                access_levels=req.access_levels,
                content_type=req.content_type,
                vendor=req.vendor,
                min_quality_score=req.min_quality_score,
                min_score=req.min_relevance_score,
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid search_type: {req.search_type}",
            )
        
        # Cross-encoder reranking (both models already on CPU)
        was_reranked = False
        if req.rerank and reranker and len(chunks) > 1:
            rerank_limit = min(req.rerank_top_n, len(chunks))
            pairs = [(req.query, c["text"]) for c in chunks[:rerank_limit]]
            
            try:
                scores = reranker.predict(pairs, batch_size=32)
                for i, chunk in enumerate(chunks[:rerank_limit]):
                    chunk["rerank_score"] = float(scores[i])
                chunks[:rerank_limit] = sorted(
                    chunks[:rerank_limit],
                    key=lambda x: x["rerank_score"],
                    reverse=True
                )
                chunks = chunks[:req.top_k]
                was_reranked = True
            except Exception as e:
                print(f"Warning: Reranking failed: {e}. Using original scores.")
        
        if not req.rerank or not reranker:
            chunks = chunks[:req.top_k]
        
        # Ensure consistent payload shape for all chunks
        for chunk in chunks:
            if not was_reranked:
                chunk["rerank_score"] = None
                chunk["is_reranked"] = False
            else:
                chunk["is_reranked"] = True
        
        return {"chunks": chunks, "query": req.query, "search_type": req.search_type}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents")
async def list_documents(limit: int = 500):
    _require_ready()
    try:
        rows = models["vs"].list_documents(limit=limit)
        total_chunks = models["vs"].total_chunks()
        return {
            "data": rows,
            "total_documents": len(rows),
            "total_chunks": total_chunks,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/documents/{source}")
async def delete_document(source: str):
    _require_ready()
    try:
        deleted_chunks = models["vs"].delete_document(source)
        if deleted_chunks == 0:
            raise HTTPException(status_code=404, detail="Document not found")
        return {
            "source": source,
            "deleted_chunks": deleted_chunks,
            "status": "deleted",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/collection")
async def reset_collection():
    _require_ready()
    try:
        models["vs"].reset_collection()
        return {"status": "collection reset"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
=======
import os
import asyncio
from typing import Optional
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from embeddings import get_embedder
from vector_store import VectorStoreClient
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

models = {}
warmup_state = {
    "status": "idle",
    "last_error": None,
}
warmup_lock = asyncio.Lock()

init_state = {
    "status": "idle",  # idle | loading | ready | error
    "last_error": None,
}
init_lock = asyncio.Lock()


def _warmup_response():
    return {
        "status": warmup_state["status"],
        "last_error": warmup_state["last_error"],
    }


async def _run_warmup():
    if "embedder" not in models or "vs" not in models:
        return

    async with warmup_lock:
        if warmup_state["status"] == "ready":
            return

        warmup_state["status"] = "warming"
        warmup_state["last_error"] = None

        try:
            warmup_vec = models["embedder"].encode(["qosentry warmup"])
            _ = warmup_vec["dense_vecs"]
            await asyncio.to_thread(models["vs"].total_chunks)
            warmup_state["status"] = "ready"
        except Exception as e:
            warmup_state["status"] = "error"
            warmup_state["last_error"] = str(e)


async def _init_models():
    async with init_lock:
        if init_state["status"] in ("loading", "ready"):
            return

        init_state["status"] = "loading"
        init_state["last_error"] = None

        try:
            embedder = await asyncio.to_thread(get_embedder)
            models["embedder"] = embedder
        except Exception as e:
            init_state["status"] = "error"
            init_state["last_error"] = f"Embedder init failed: {e}"
            return

        max_retries = int(os.getenv("QDRANT_INIT_MAX_RETRIES", "30"))
        retry_delay = float(os.getenv("QDRANT_INIT_RETRY_DELAY_SEC", "2"))
        last_error: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:
                models["vs"] = VectorStoreClient(embedder=models["embedder"])
                last_error = None
                break
            except Exception as e:
                last_error = e
                if attempt == max_retries:
                    break
                print(
                    f"Qdrant not ready yet (attempt {attempt}/{max_retries}): {e}. "
                    f"Retrying in {retry_delay}s..."
                )
                await asyncio.sleep(retry_delay)

        if last_error is not None:
            init_state["status"] = "error"
            init_state["last_error"] = f"Vector store init failed: {last_error}"
            return

        init_state["status"] = "ready"
        init_state["last_error"] = None

        warmup_state["status"] = "idle"
        warmup_state["last_error"] = None
        asyncio.create_task(_run_warmup())


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Loading AI models and connecting to DB...")
    models.clear()
    warmup_state["status"] = "idle"
    warmup_state["last_error"] = None
    init_state["status"] = "idle"
    init_state["last_error"] = None

    asyncio.create_task(_init_models())
    print("System starting (background init).")
    yield
    models.clear()
    warmup_state["status"] = "idle"
    warmup_state["last_error"] = None
    init_state["status"] = "idle"
    init_state["last_error"] = None


app = FastAPI(title="QoS-Buddy RAG Service", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class IngestTextRequest(BaseModel):
    text: str
    metadata: Optional[dict] = {}


class RetrieveRequest(BaseModel):
    query: str
    top_k: int = int(os.getenv("TOP_K", 5))
    search_type: str = "hybrid"  # Options: "hybrid", "semantic", "keyword"
    tenant_id: Optional[str] = None
    data_category: Optional[str] = None
    access_levels: Optional[list[str]] = None
    rrf_dense_weight: Optional[float] = 0.7  # For hybrid: 0.0-1.0 (dense weight)
    min_relevance_score: Optional[float] = 0.5  # Minimum threshold (0.0-1.0)


def _require_ready():
    if init_state["status"] == "error":
        raise HTTPException(
            status_code=503,
            detail=init_state["last_error"] or "RAG service failed to initialize",
        )
    if "embedder" not in models or "vs" not in models:
        raise HTTPException(status_code=503, detail="Models still loading")


@app.get("/health")
async def health():
    payload = {
        "service": "rag",
        "status": "starting",
        "init": {
            "status": init_state["status"],
            "last_error": init_state["last_error"],
        },
        "warmup": _warmup_response(),
    }

    if init_state["status"] == "error":
        payload["status"] = "degraded"
        return payload

    if "embedder" in models and "vs" in models:
        payload["status"] = "ok"
    return payload


@app.post("/warmup")
async def warmup():
    if init_state["status"] != "ready":
        asyncio.create_task(_init_models())

    _require_ready()

    if warmup_state["status"] != "warming" and warmup_state["status"] != "ready":
        asyncio.create_task(_run_warmup())

    return _warmup_response()


@app.post("/ingest/text")
async def ingest_text(req: IngestTextRequest):
    _require_ready()
    try:
        ids = models["vs"].ingest_text(req.text, req.metadata, models["embedder"])
        return {"ingested_chunks": len(ids), "ids": ids}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest/file")
async def ingest_file(file: UploadFile = File(...)):
    _require_ready()
    try:
        content = await file.read()
        filename = file.filename or "unknown"
        text = (
            models["vs"].extract_pdf_text(content)
            if filename.endswith(".pdf")
            else content.decode("utf-8")
        )
        ids = models["vs"].ingest_text(text, {"source": filename}, models["embedder"])
        return {"filename": filename, "ingested_chunks": len(ids), "ids": ids}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/retrieve")
async def retrieve(req: RetrieveRequest):
    _require_ready()
    try:
        if req.search_type == "hybrid":
            chunks = models["vs"].hybrid_search(
                query=req.query,
                embedder=models["embedder"],
                top_k=req.top_k,
                tenant_id=req.tenant_id,
                data_category=req.data_category,
                access_levels=req.access_levels,
                dense_weight=req.rrf_dense_weight,
                min_score=req.min_relevance_score,
            )
        elif req.search_type == "semantic":
            semantic_result = models["embedder"].encode([req.query], return_dense=True, return_sparse=False, return_colbert_vecs=False)
            vec = semantic_result["dense_vecs"].tolist()[0]
            chunks = models["vs"].search(vec, top_k=req.top_k)
        elif req.search_type == "keyword":
            # Keyword-only search using sparse vectors
            chunks = models["vs"].keyword_search(
                query=req.query,
                embedder=models["embedder"],
                top_k=req.top_k,
                tenant_id=req.tenant_id,
                data_category=req.data_category,
                access_levels=req.access_levels,
                min_score=req.min_relevance_score,
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid search_type: {req.search_type}",
            )
        return {"chunks": chunks, "query": req.query, "search_type": req.search_type}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents")
async def list_documents(limit: int = 500):
    _require_ready()
    try:
        rows = models["vs"].list_documents(limit=limit)
        total_chunks = models["vs"].total_chunks()
        return {
            "data": rows,
            "total_documents": len(rows),
            "total_chunks": total_chunks,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/documents/{source}")
async def delete_document(source: str):
    _require_ready()
    try:
        deleted_chunks = models["vs"].delete_document(source)
        if deleted_chunks == 0:
            raise HTTPException(status_code=404, detail="Document not found")
        return {
            "source": source,
            "deleted_chunks": deleted_chunks,
            "status": "deleted",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/collection")
async def reset_collection():
    _require_ready()
    try:
        models["vs"].reset_collection()
        return {"status": "collection reset"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
>>>>>>> kousay
