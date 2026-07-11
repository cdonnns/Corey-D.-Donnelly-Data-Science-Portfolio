"""
Stage 1 of the DVC pipeline: chunk raw documents into overlapping windows
ready for embedding. Kept separate from build_index.py so re-chunking
(e.g. testing a new chunk_size) doesn't require re-touching raw source docs,
and re-embedding doesn't require re-chunking -- each stage only reruns when
its own inputs change, which is the point of a DVC DAG over a single script.
"""
import argparse
import json
from pathlib import Path


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunks.append(" ".join(words[start:end]))
        start += chunk_size - overlap
    return chunks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--chunk-size", type=int, default=500)
    parser.add_argument("--overlap", type=int, default=50)
    args = parser.parse_args()

    in_dir = Path(args.input)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    records = []
    for path in sorted(in_dir.glob("*.txt")):
        text = path.read_text()
        for i, chunk in enumerate(chunk_text(text, args.chunk_size, args.overlap)):
            records.append(
                {
                    "id": f"{path.stem}_{i}",
                    "text": chunk,
                    "metadata": {"source": path.name, "chunk_index": i},
                }
            )

    out_path = out_dir / "chunks.jsonl"
    with open(out_path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    print(f"Wrote {len(records)} chunks from {len(list(in_dir.glob('*.txt')))} docs to {out_path}")


if __name__ == "__main__":
    main()
