"""
Thin abstraction over the vector DB so the backend can be swapped
(Chroma for local dev -> Qdrant/pgvector in prod) without touching rag.py.
This is the kind of seam interviewers ask about: "what if you had to
change vector DBs in prod?" -- answer: you change one file.
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Document:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0


class VectorStore:
    def __init__(self, settings):
        self.settings = settings
        self._backend = None

    def load(self):
        if self.settings.vector_db_backend == "chroma":
            import chromadb

            client = chromadb.PersistentClient(path=self.settings.vector_index_path)
            self._backend = client.get_or_create_collection("documents")
        elif self.settings.vector_db_backend == "qdrant":
            from qdrant_client import QdrantClient

            self._backend = QdrantClient(url=self.settings.vector_db_url)
        else:
            raise ValueError(f"Unsupported backend: {self.settings.vector_db_backend}")

    def upsert(self, ids: list[str], embeddings: list[list[float]], docs: list[Document]):
        if self.settings.vector_db_backend == "chroma":
            self._backend.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=[d.text for d in docs],
                metadatas=[d.metadata for d in docs],
            )
        else:
            raise NotImplementedError("Add backend-specific upsert logic here")

    def query(self, embedding: list[float], top_k: int) -> list[Document]:
        if self.settings.vector_db_backend == "chroma":
            res = self._backend.query(query_embeddings=[embedding], n_results=top_k)
            docs = []
            for text, meta, dist in zip(
                res["documents"][0], res["metadatas"][0], res["distances"][0]
            ):
                docs.append(Document(text=text, metadata=meta, score=1 - dist))
            return docs
        raise NotImplementedError("Add backend-specific query logic here")

    def is_ready(self) -> bool:
        return self._backend is not None
