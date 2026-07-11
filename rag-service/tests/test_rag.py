import os

os.environ["RAG_MOCK_LLM"] = "true"

from app.config import Settings
from app.rag import RAGPipeline
from app.vectorstore import Document


def test_build_prompt_includes_citations_and_context():
    settings = Settings()
    pipeline = RAGPipeline(settings)
    docs = [
        Document(text="Paris is the capital of France.", metadata={"source": "wiki"}),
        Document(text="France is in Western Europe.", metadata={"source": "wiki2"}),
    ]
    prompt = pipeline._build_prompt("What is the capital of France?", docs)
    assert "[1]" in prompt and "[2]" in prompt
    assert "Paris is the capital of France." in prompt
    assert "What is the capital of France?" in prompt


def test_mock_llm_path_returns_usage_dict():
    settings = Settings()
    pipeline = RAGPipeline(settings)
    answer, usage = pipeline._call_llm("some prompt")
    assert isinstance(answer, str)
    assert "prompt_tokens" in usage and "completion_tokens" in usage


def test_feedback_written_to_jsonl(tmp_path, monkeypatch):
    settings = Settings()
    pipeline = RAGPipeline(settings)
    pipeline._feedback_log = tmp_path / "feedback.jsonl"
    pipeline.log_feedback("q1", 5, "great answer")
    content = pipeline._feedback_log.read_text()
    assert "q1" in content and '"rating": 5' in content
