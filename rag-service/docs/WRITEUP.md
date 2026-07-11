# Design Write-up: Production RAG Service

## Why this project

Most ML portfolios stop at "I trained a model" or "I built a notebook that answers
questions." The gap between that and an MLE/MLOps job is everything that happens
after the model works: serving it reliably, deploying it safely, knowing when it's
degrading, and controlling its cost. This project exists to demonstrate that half —
the RAG pipeline itself is intentionally simple so the engineering around it can be
the focus.

## Key design decisions

**FastAPI over Flask.** Retrieval and generation are both I/O-bound (network calls
to the vector DB and LLM provider). Async support means one pod can hold many
concurrent in-flight requests instead of blocking a worker thread per request —
this directly affects how many pods you need under load, which shows up in the
Terraform node group sizing and the HPA thresholds.

**Split liveness/readiness probes.** A pod process can be running (alive) before
the embedding model and vector index are loaded (not ready). Using one health
check for both means Kubernetes routes traffic to a pod that will 503 every
request during startup. This is a small detail that's easy to get wrong and a
good thing to be able to explain in an interview.

**Vector store behind an interface (`app/vectorstore.py`).** Started with Chroma
for local dev (zero external dependencies), designed the interface so swapping to
Qdrant or pgvector in production is a config change, not a rewrite. The tradeoff:
extra abstraction layer for a project that only strictly needs one backend right
now. Justified here because "what happens when you need to change vector DBs" is
a realistic question this answers concretely.

**Mocked LLM path for tests and CI (`RAG_MOCK_LLM=true`).** Tests hit the real
FastAPI app and real code paths, but never call the LLM API. This keeps CI fast,
free, deterministic, and runnable with zero API keys — meaning anyone cloning the
repo can run the test suite immediately. The tradeoff is that CI doesn't catch
LLM-provider-specific failures (rate limits, schema changes); that's a known gap,
not an oversight.

**Automated eval as a deploy gate, not just a dashboard.** `eval/eval_pipeline.py`
runs a golden Q&A set through the live pipeline and fails the CI job if
faithfulness regresses more than 5% versus baseline. This is what makes "canary
deployment" meaningful rather than decorative — a bad prompt or index change is
blocked before a human ever notices in production.

**Spot instances for the EKS node group.** ~70% cheaper than on-demand. Acceptable
tradeoff because the service is stateless (no in-memory session state, health
checks handle pod churn) — spot interruptions just look like normal pod
rescheduling. This wouldn't be an acceptable tradeoff for a stateful service.

## Known limitations / what's mocked vs. real

Being direct about this matters more than pretending everything is finished:

- **`answer_relevance` and `context_precision`** in the eval pipeline are
  placeholders (return 0.0). A real implementation needs either an LLM-as-judge
  call (costs money per eval run) or a hand-labeled relevant-docs set per golden
  question. `faithfulness` is implemented as a lightweight word-overlap heuristic,
  not a judge model — cheap and fast, but a weaker signal.
- **The Terraform module isn't applied to real AWS infrastructure** in this
  repo's current state — it's a correct, reviewable IaC definition, not a running
  cluster. Standing it up costs real money to keep alive, so it's written to be
  `terraform apply`-ready rather than kept always-on.
- **No real fine-tuning or feedback-loop training** — feedback is logged
  (`/v1/feedback` → `data/feedback.jsonl`) but nothing consumes it yet. That's the
  natural Phase 5.

## What I'd do differently with more time

- Replace the word-overlap faithfulness heuristic with a proper LLM-judge scorer,
  gated behind a budget (e.g., only run on merge to main, not every commit).
- Add a feature store if this grew multiple models sharing features, which isn't
  justified yet at this scale.
- Multi-region deployment — currently single-region, which is a real limitation
  for latency-sensitive global traffic.

## Load test results

*(Fill in after running `locust -f load_test/locustfile.py` against your own
deployment — this is the one section that needs real numbers from your
environment, not template text. Report: max sustainable QPS before p99 latency
crosses your target, and what actually became the bottleneck — CPU, vector DB
query time, or LLM provider rate limits.)*

| Metric | Value |
|---|---|
| Sustainable QPS (p99 < 3s) | TBD |
| Bottleneck identified | TBD |
| Pods at peak (per HPA) | TBD |
