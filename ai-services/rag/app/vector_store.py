import os
import uuid
import io
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

COLLECTION    = os.getenv("QDRANT_COLLECTION", "qos_buddy")
VECTOR_SIZE   = 384   # dimension all-MiniLM-L6-v2
CHUNK_SIZE    = int(os.getenv("CHUNK_SIZE", 512))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 64))


class VectorStoreClient:
    def __init__(self):
        self.client = QdrantClient(
            host=os.getenv("QDRANT_HOST", "qdrant"),
            port=int(os.getenv("QDRANT_PORT", 6333)),
        )
        self._ensure_collection()

    def _ensure_collection(self):
        names = [c.name for c in self.client.get_collections().collections]
        if COLLECTION not in names:
            self.client.create_collection(
                collection_name=COLLECTION,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            )

    def reset_collection(self):
        self.client.delete_collection(COLLECTION)
        self._ensure_collection()

    def ingest_text(self, text: str, metadata: dict, embedder) -> list[str]:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
        )
        chunks  = splitter.split_text(text)
        vectors = embedder.encode(chunks).tolist()

        points, ids = [], []
        for chunk, vec in zip(chunks, vectors):
            pid = str(uuid.uuid4())
            ids.append(pid)
            points.append(
                PointStruct(id=pid, vector=vec, payload={"text": chunk, **metadata})
            )
        self.client.upsert(collection_name=COLLECTION, points=points)
        return ids

    def search(self, query_vector: list[float], top_k: int = 5) -> list[dict]:
        hits = self.client.search(
            collection_name=COLLECTION,
            query_vector=query_vector,
            limit=top_k,
            with_payload=True,
        )
        return [
            {"text": r.payload.get("text", ""), "score": r.score, "metadata": r.payload}
            for r in hits
        ]

    @staticmethod
    def extract_pdf_text(content: bytes) -> str:
        reader = PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)