# Production RAG Service

A retrieval-augmented generation service built and operated like a real product:
CI/CD, containerized deployment on Kubernetes, infrastructure as code, observability,
automated quality gating, and load-tested scaling limits — not just a notebook that
answers questions.

**Full design rationale, tradeoffs, and lessons learned:** [`docs/WRITEUP.md`](docs/WRITEUP.md)

## Architecture

```mermaid
flowchart TB
    subgraph Client
        U[User / API Client]
    end

    subgraph "Kubernetes Cluster (EKS)"
        subgraph "Ingress"
            LB[Load Balancer]
        end

        subgraph "rag-service Deployment (HPA: 3-15 pods)"
            P1[Pod: FastAPI + RAG Pipeline]
            P2[Pod: FastAPI + RAG Pipeline]
            P3[Pod: FastAPI + RAG Pipeline]
            CAN[Canary Pod - new version]
        end

        HPA[HorizontalPodAutoscaler]
    end

    subgraph "Data & Model Layer"
        VDB[(Qdrant Vector DB)]
        MLF[(MLflow Tracking)]
        S3[(S3 - DVC data/index versions)]
    end

    subgraph "External"
        LLM[LLM Provider API]
    end

    subgraph "Observability"
        PROM[Prometheus]
        GRAF[Grafana Dashboards]
        ALERT[Alertmanager]
    end

    subgraph "CI/CD - GitHub Actions"
        LINT[Lint] --> TEST[Test - mocked LLM]
        TEST --> BUILD[Build + Push Image to ECR]
        BUILD --> EVAL[Automated Eval Gate]
        EVAL -->|pass| DEPLOY[Deploy Canary]
        EVAL -->|fail| BLOCK[Block Deploy]
        DEPLOY --> SMOKE[Smoke Test]
        SMOKE -->|pass| PROMOTE[Promote to Stable]
    end

    U --> LB --> P1 & P2 & P3
    LB -.10% traffic.-> CAN
    HPA -.scales.-> P1 & P2 & P3

    P1 & P2 & P3 & CAN --> VDB
    P1 & P2 & P3 & CAN --> LLM
    P1 & P2 & P3 & CAN -.logs metrics.-> PROM
    PROM --> GRAF
    PROM --> ALERT

    VDB -.built from.-> S3
    EVAL --> MLF
    BUILD -.pushes.-> DEPLOY

    style CAN fill:#f9d77e
    style BLOCK fill:#e57373
    style PROMOTE fill:#81c784
```

**Request flow:** client → load balancer → FastAPI pod → embed query → retrieve top-k
chunks from Qdrant → build grounded prompt → call LLM → return answer + cited sources.
Every request emits latency/token metrics to Prometheus.

**Deploy flow:** push to `main` → lint/test (offline, mocked LLM) → build & push image →
automated eval scores the new version against a golden dataset → if it doesn't regress,
deploy as a canary receiving a slice of traffic → run smoke tests → promote to stable.
A failing eval blocks the deploy before it ever reaches users.

## Project structure

```
app/            FastAPI service, RAG pipeline, vector store abstraction
tests/          Unit + integration tests (offline via mocked LLM)
eval/           Automated quality eval + golden dataset (deploy gate)
mlops/          MLflow tracking, DVC pipeline for data/index versioning
k8s/            Deployment, canary, HPA, ConfigMap manifests
infra/terraform/ EKS cluster, ECR, S3 (IaC)
monitoring/     Prometheus scrape config + alert rules
load_test/      Locust load test
docs/           Architecture + write-up
```

## Running locally

```bash
docker compose up --build
# service:    http://localhost:8000/docs
# mlflow:     http://localhost:5000
# prometheus: http://localhost:9090
# grafana:    http://localhost:3000  (admin/admin)
```

## Running tests

```bash
pip install -r requirements.txt
RAG_MOCK_LLM=true pytest --cov=app
```

## Load testing

```bash
locust -f load_test/locustfile.py --host=http://localhost:8000
```

## Deploying

```bash
cd infra/terraform && terraform init && terraform apply
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/deployment.yaml
```

In practice, deploys go through the GitHub Actions pipeline in
[`.github/workflows/ci-cd.yml`](.github/workflows/ci-cd.yml), not manual `kubectl apply`.

## Status

This is an active portfolio project — see [`docs/WRITEUP.md`](docs/WRITEUP.md) for
what's implemented vs. planned, and known limitations.
