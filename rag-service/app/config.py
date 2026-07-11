"""
All config comes from env vars, nothing hardcoded here. Same image should
work for dev/staging/prod, just point it at different env vars.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_version: str = "0.1.0"
    environment: str = "dev"

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    llm_model: str = "gpt-4o-mini"  # swap-able; kept provider-agnostic in rag.py
    vector_index_path: str = "./data/index"
    top_k_default: int = 4

    vector_db_backend: str = "chroma"  # chroma | qdrant | pgvector
    vector_db_url: str = "http://localhost:6333"

    mlflow_tracking_uri: str = "http://localhost:5000"

    max_context_tokens: int = 3000
    request_timeout_s: int = 30

    class Config:
        env_file = ".env"
        env_prefix = "RAG_"


@lru_cache
def get_settings() -> Settings:
    return Settings()
