#!/usr/bin/env python3
"""Fire a realistic test incident payload at the local analyzer webhook."""

import json
import sys
from datetime import datetime, timezone

import httpx

WEBHOOK_URL = "http://localhost:8000/webhook/incident"

TEST_PAYLOAD = {
    "incident_id": "INC-2026-0524-001",
    "title": "Payment API — Database Connection Pool Exhaustion",
    "service_name": "payment-api",
    "severity": "critical",
    "timestamp": datetime.now(timezone.utc).isoformat(),
}


def main() -> int:
    print(f"Sending test incident to {WEBHOOK_URL}")
    print(f"Payload:\n{json.dumps(TEST_PAYLOAD, indent=2)}\n")

    try:
        response = httpx.post(
            WEBHOOK_URL,
            json=TEST_PAYLOAD,
            timeout=10.0,
        )
    except httpx.ConnectError:
        print(
            "ERROR: Could not connect to the server. "
            "Start it first with: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000",
            file=sys.stderr,
        )
        return 1
    except httpx.HTTPError as exc:
        print(f"ERROR: Request failed — {exc}", file=sys.stderr)
        return 1

    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")

    if response.status_code == 202:
        print(
            "\nIncident queued successfully. "
            "Watch the server console for the AI-generated RCA report."
        )
        return 0

    print(
        f"\nUnexpected status code {response.status_code}. Expected 202.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
