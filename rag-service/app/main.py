"""
Main API entrypoint. See docs/WRITEUP.md for the longer rationale on some
of these choices if I forget why later.

healthz vs readyz: learned this one the hard way -- if you only have one
health check, k8s starts sending traffic to a pod before the embedding
model is even loaded and everything 503s for the first ~10s.
"""
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from app.schemas import QueryRequest, QueryResponse, FeedbackRequest
from app.rag import RAGPipeline
from app.config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rag-service")

settings = get_settings()

REQUEST_COUNT = Counter(
    "rag_requests_total", "Total requests", ["endpoint", "status"]
)
REQUEST_LATENCY = Histogram(
    "rag_request_latency_seconds", "Request latency", ["endpoint"]
)
RETRIEVAL_LATENCY = Histogram("rag_retrieval_latency_seconds", "Retrieval-only latency")
GENERATION_LATENCY = Histogram("rag_generation_latency_seconds", "Generation-only latency")
TOKENS_USED = Counter("rag_tokens_total", "Tokens consumed", ["type"])

pipeline: RAGPipeline | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global pipeline
    logger.info("Loading RAG pipeline (index=%s)", settings.vector_index_path)
    pipeline = RAGPipeline(settings)
    pipeline.load()
    logger.info("Pipeline ready.")
    yield
    logger.info("Shutting down pipeline.")


app = FastAPI(
    title="Production RAG Service",
    version=settings.app_version,
    lifespan=lifespan,
)


@app.get("/healthz")
def liveness():
    return {"status": "alive"}


@app.get("/readyz")
def readiness():
    if pipeline is None or not pipeline.is_ready():
        raise HTTPException(status_code=503, detail="pipeline not ready")
    return {"status": "ready"}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/v1/query", response_model=QueryResponse)
def query(req: QueryRequest):
    start = time.time()
    try:
        with RETRIEVAL_LATENCY.time():
            docs = pipeline.retrieve(req.query, top_k=req.top_k)
        with GENERATION_LATENCY.time():
            answer, usage = pipeline.generate(req.query, docs)

        TOKENS_USED.labels(type="prompt").inc(usage["prompt_tokens"])
        TOKENS_USED.labels(type="completion").inc(usage["completion_tokens"])
        REQUEST_COUNT.labels(endpoint="query", status="success").inc()
        REQUEST_LATENCY.labels(endpoint="query").observe(time.time() - start)

        return QueryResponse(
            answer=answer,
            sources=[d.metadata.get("source", "unknown") for d in docs],
            latency_ms=round((time.time() - start) * 1000, 2),
            model_version=pipeline.model_version,
        )
    except Exception as e:
        REQUEST_COUNT.labels(endpoint="query", status="error").inc()
        REQUEST_LATENCY.labels(endpoint="query").observe(time.time() - start)
        logger.exception("query failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/feedback")
def feedback(req: FeedbackRequest):
    """Logs human feedback for later use in the eval/fine-tune loop (Phase 4)."""
    pipeline.log_feedback(req.query_id, req.rating, req.comment)
    return {"status": "logged"}


@app.middleware("http")
async def add_latency_header(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    response.headers["X-Process-Time-Ms"] = str(round((time.time() - start) * 1000, 2))
    return response
