"""
Wraps MLflow so every index build and eval run is logged with the params
and metrics needed to answer "why did retrieval quality change last week?"
without archaeology through Slack threads.
"""
import mlflow
from app.config import get_settings


def start_run(run_name: str):
    settings = get_settings()
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment("rag-service")
    return mlflow.start_run(run_name=run_name)


def log_index_build(chunk_size: int, overlap: int, embedding_model: str, num_docs: int):
    with start_run("index-build"):
        mlflow.log_params(
            {
                "chunk_size": chunk_size,
                "overlap": overlap,
                "embedding_model": embedding_model,
            }
        )
        mlflow.log_metric("num_docs_indexed", num_docs)


def log_eval_run(results: dict, model_version: str):
    with start_run("eval"):
        mlflow.log_param("model_version", model_version)
        mlflow.log_metrics(
            {
                "faithfulness": results["faithfulness"],
                "answer_relevance": results["answer_relevance"],
                "context_precision": results["context_precision"],
                "avg_latency_ms": results["avg_latency_ms"],
            }
        )
