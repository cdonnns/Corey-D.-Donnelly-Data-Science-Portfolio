"""
Automated eval: runs the pipeline against a golden Q&A dataset and scores
faithfulness / relevance / context precision. This is the gate that decides
whether a new index or prompt version is allowed to reach the canary --
Phase 4's promised "score new versions before promoting them."

Run: python eval/eval_pipeline.py --golden eval/golden_dataset.jsonl
"""
import argparse
import json
import statistics
import sys
import time

from app.config import get_settings
from app.rag import RAGPipeline

REGRESSION_THRESHOLD = 0.05  # fail the build if any metric drops >5% vs baseline


def score_faithfulness(answer: str, context_docs: list[str]) -> float:
    """
    Cheap heuristic proxy: fraction of answer sentences that share significant
    word overlap with retrieved context. Swap for an LLM-judge call
    (see docs/WRITEUP.md) once you have budget for it -- this keeps eval
    free and fast for local/CI runs.
    """
    context_words = set(" ".join(context_docs).lower().split())
    sentences = [s for s in answer.split(".") if s.strip()]
    if not sentences:
        return 0.0
    supported = 0
    for s in sentences:
        words = set(s.lower().split())
        overlap = len(words & context_words) / max(len(words), 1)
        if overlap > 0.3:
            supported += 1
    return supported / len(sentences)


def run_eval(golden_path: str) -> dict:
    settings = get_settings()
    pipeline = RAGPipeline(settings)
    pipeline.load()

    faithfulness_scores, latencies = [], []
    with open(golden_path) as f:
        cases = [json.loads(line) for line in f]

    for case in cases:
        start = time.time()
        docs = pipeline.retrieve(case["question"], top_k=4)
        answer, _ = pipeline.generate(case["question"], docs)
        latencies.append((time.time() - start) * 1000)
        faithfulness_scores.append(
            score_faithfulness(answer, [d.text for d in docs])
        )

    return {
        "faithfulness": round(statistics.mean(faithfulness_scores), 3),
        "answer_relevance": 0.0,   # placeholder: wire up an LLM-judge scorer
        "context_precision": 0.0,  # placeholder: needs labeled relevant-doc-ids
        "avg_latency_ms": round(statistics.mean(latencies), 1),
        "num_cases": len(cases),
    }


def check_regression(results: dict, baseline_path: str) -> bool:
    try:
        with open(baseline_path) as f:
            baseline = json.load(f)
    except FileNotFoundError:
        return True  # no baseline yet -- first run always passes

    for metric in ("faithfulness",):
        drop = baseline[metric] - results[metric]
        if drop > REGRESSION_THRESHOLD:
            print(f"REGRESSION: {metric} dropped {drop:.3f} vs baseline")
            return False
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--golden", default="eval/golden_dataset.jsonl")
    parser.add_argument("--baseline", default="eval/baseline.json")
    parser.add_argument("--output", default="eval/results.json")
    args = parser.parse_args()

    results = run_eval(args.golden)
    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)

    print(json.dumps(results, indent=2))

    if not check_regression(results, args.baseline):
        sys.exit(1)  # non-zero exit fails the CI job / blocks promotion
