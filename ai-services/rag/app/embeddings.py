import os
import sys
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

_embedder = None


def get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        model_name = os.getenv("EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-0.6B")
        print(f"Loading embedding model on CPU...", flush=True)
        sys.stdout.flush()
        _embedder = SentenceTransformer(model_name, trust_remote_code=True, device="cpu")
        print(f"Embedding model loaded on CPU", flush=True)
        sys.stdout.flush()
    return _embedder
