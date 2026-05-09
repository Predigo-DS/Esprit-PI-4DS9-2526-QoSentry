import os
import sys
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

try:
    import torch
except Exception:
    torch = None

# --- Monkeypatch huggingface_hub for download progress tracking ---
from tqdm.auto import tqdm
import huggingface_hub.utils

download_progress = {
    "total_bytes": 0,
    "downloaded_bytes": 0,
    "percentage": 0.0
}

class TrackingTqdm(tqdm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, 'total') and self.total is not None:
            download_progress["total_bytes"] += self.total

    def update(self, n=1):
        super().update(n)
        download_progress["downloaded_bytes"] += n
        if download_progress["total_bytes"] > 0:
            download_progress["percentage"] = min(
                100.0, 
                round((download_progress["downloaded_bytes"] / download_progress["total_bytes"]) * 100, 2)
            )

# Apply the monkeypatch to huggingface_hub internals safely
if hasattr(huggingface_hub.utils, '_tqdm'):
    huggingface_hub.utils._tqdm.tqdm = TrackingTqdm
if hasattr(huggingface_hub.utils, '_progress'):
    huggingface_hub.utils._progress.tqdm = TrackingTqdm
if hasattr(huggingface_hub.utils, 'tqdm'):
    huggingface_hub.utils.tqdm = TrackingTqdm
# -------------------------------------------------------------------

load_dotenv()

_embedder_cache: dict[str, SentenceTransformer] = {}


def _normalize_device(device: str | None) -> str:
    requested = (device or "cpu").strip().lower()
    if requested == "gpu" or requested.startswith("cuda"):
        if torch is not None and torch.cuda.is_available():
            return "cuda" if requested == "gpu" else requested
        print("GPU embedding requested but CUDA is unavailable; falling back to CPU.", flush=True)
        sys.stdout.flush()
        return "cpu"
    return "cpu"


def get_embedder(device: str | None = None) -> SentenceTransformer:
    normalized_device = _normalize_device(device)
    if normalized_device not in _embedder_cache:
        model_name = os.getenv("EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-0.6B")
        print(f"Loading embedding model on {normalized_device.upper()}...", flush=True)
        sys.stdout.flush()
        _embedder_cache[normalized_device] = SentenceTransformer(
            model_name,
            trust_remote_code=True,
            device=normalized_device,
        )
        print(f"Embedding model loaded on {normalized_device.upper()}", flush=True)
        sys.stdout.flush()
    return _embedder_cache[normalized_device]


def get_inference_embedder() -> SentenceTransformer:
    return get_embedder(os.getenv("EMBEDDING_INFERENCE_DEVICE", "cpu"))


def get_ingest_embedder() -> SentenceTransformer:
    return get_embedder(os.getenv("EMBEDDING_INGEST_DEVICE", "cuda"))
