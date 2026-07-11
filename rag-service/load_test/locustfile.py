"""
Load test used to find/document the breaking point (Phase 3 requirement).

Run: locust -f load_test/locustfile.py --host=http://localhost:8000
Then open http://localhost:8089, set users/spawn-rate, and watch p95/p99
latency and failure rate as load climbs. Record the results in
docs/WRITEUP.md -- "at what QPS does p99 exceed 3s" is exactly the kind of
number that makes an interview conversation concrete.
"""
import random
from locust import HttpUser, task, between

SAMPLE_QUERIES = [
    "What is the capital of France?",
    "How does gradient descent work?",
    "Summarize the main causes of the French Revolution.",
    "What are the health benefits of green tea?",
    "Explain the CAP theorem in distributed systems.",
]


class RagServiceUser(HttpUser):
    wait_time = between(0.5, 2.5)

    @task(9)
    def query(self):
        self.client.post(
            "/v1/query",
            json={"query": random.choice(SAMPLE_QUERIES), "top_k": 4},
            name="/v1/query",
        )

    @task(1)
    def feedback(self):
        self.client.post(
            "/v1/feedback",
            json={"query_id": "load-test", "rating": random.randint(1, 5)},
            name="/v1/feedback",
        )

    @task(2)
    def health_check(self):
        self.client.get("/readyz", name="/readyz")
