"""
Runs against a freshly deployed canary before it's allowed to receive real
traffic. Called from the CI/CD pipeline's deploy-canary job.
"""
import argparse
import sys
import time
import urllib.request
import json

CANARY_URL = "http://rag-service-canary/v1/query"
STABLE_URL = "http://rag-service/v1/query"


def hit(url: str, payload: dict) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=["canary", "stable"], default="canary")
    args = parser.parse_args()

    url = CANARY_URL if args.target == "canary" else STABLE_URL
    test_queries = ["What is the capital of France?", "Explain the CAP theorem."]

    for q in test_queries:
        start = time.time()
        try:
            resp = hit(url, {"query": q, "top_k": 4})
        except Exception as e:
            print(f"FAIL: request errored: {e}")
            sys.exit(1)

        latency = (time.time() - start) * 1000
        if not resp.get("answer"):
            print(f"FAIL: empty answer for query: {q}")
            sys.exit(1)
        if latency > 5000:
            print(f"FAIL: latency {latency:.0f}ms exceeds 5000ms budget")
            sys.exit(1)

        print(f"OK  [{latency:.0f}ms]  {q}")

    print("Smoke tests passed.")


if __name__ == "__main__":
    main()
