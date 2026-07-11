"""
RAG orchestration: embed query -> retrieve -> build prompt -> generate.

Kept deliberately provider-agnostic for the LLM call (see _call_llm) so this
same pipeline works whether you're hitting OpenAI, Anthropic, or a
self-hosted vLLM endpoint -- only _call_llm changes.
"""
import json
import logging
import time
from pathlib import Path

from app.vectorstore import VectorStore, Document

logger = logging.getLogger("rag-pipeline")


class RAGPipeline:
    def __init__(self, settings):
        self.settings = settings
        self.store = VectorStore(settings)
        self._embedder = None
        self.model_version = f"{settings.llm_model}::{settings.app_version}"
        self._feedback_log = Path("./data/feedback.jsonl")
        self._feedback_log.parent.mkdir(parents=True, exist_ok=True)

    def load(self):
        from sentence_transformers import SentenceTransformer

        self._embedder = SentenceTransformer(self.settings.embedding_model)
        self.store.load()

    def is_ready(self) -> bool:
        return self._embedder is not None and self.store.is_ready()

    def _embed(self, text: str) -> list[float]:
        return self._embedder.encode(text).tolist()

    def retrieve(self, query: str, top_k: int) -> list[Document]:
        query_vec = self._embed(query)
        return self.store.query(query_vec, top_k=top_k)

    def _build_prompt(self, query: str, docs: list[Document]) -> str:
        context = "\n\n".join(
            f"[{i+1}] {d.text}" for i, d in enumerate(docs)
        )
        return (
            "Answer the question using only the context below. "
            "Cite sources as [n]. If the answer isn't in the context, say so.\n\n"
            f"Context:\n{context}\n\nQuestion: {query}\nAnswer:"
        )

    def _call_llm(self, prompt: str) -> tuple[str, dict]:
        """
        Swap this function's internals to change LLM providers.
        Returns (answer_text, usage_dict).
        """
        import os

        if os.getenv("RAG_MOCK_LLM", "false").lower() == "true":
            # Deterministic mock path used in CI/tests -- avoids paying for
            # API calls on every PR and keeps tests fast + offline.
            return (
                "This is a mocked answer for testing purposes. [1]",
                {"prompt_tokens": len(prompt.split()), "completion_tokens": 8},
            )

        from openai import OpenAI

        client = OpenAI()
        resp = client.chat.completions.create(
            model=self.settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
        )
        usage = resp.usage
        return resp.choices[0].message.content, {
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
        }

    def generate(self, query: str, docs: list[Document]) -> tuple[str, dict]:
        prompt = self._build_prompt(query, docs)
        return self._call_llm(prompt)

    def log_feedback(self, query_id: str, rating: int, comment: str | None):
        entry = {
            "query_id": query_id,
            "rating": rating,
            "comment": comment,
            "ts": time.time(),
            "model_version": self.model_version,
        }
        with open(self._feedback_log, "a") as f:
            f.write(json.dumps(entry) + "\n")
