"""
Stage 2 of the DVC pipeline: embed chunked docs and write them into the
vector store. Logs the build to MLflow so every index version is tied to
the embedding model + chunking params that produced it -- the thing you
need when someone asks "why did retrieval quality change after Tuesday's
deploy?" six weeks from now.
"""
import argparse
import json
from pathlib import Path

from app.config import get_settings
from app.vectorstore import VectorStore, Document
from mlops.tracking import log_index_build


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    settings = get_settings()
    settings.vector_index_path = args.output

    from sentence_transformers import SentenceTransformer

    embedder = SentenceTransformer(settings.embedding_model)
    store = VectorStore(settings)
    store.load()

    chunks_path = Path(args.input) / "chunks.jsonl"
    ids, embeddings, docs = [], [], []
    with open(chunks_path) as f:
        for line in f:
            rec = json.loads(line)
            ids.append(rec["id"])
            embeddings.append(embedder.encode(rec["text"]).tolist())
            docs.append(Document(text=rec["text"], metadata=rec["metadata"]))

    store.upsert(ids, embeddings, docs)

    log_index_build(
        chunk_size=500,
        overlap=50,
        embedding_model=settings.embedding_model,
        num_docs=len(docs),
    )

    print(f"Indexed {len(docs)} chunks into {args.output}")


if __name__ == "__main__":
    main()
