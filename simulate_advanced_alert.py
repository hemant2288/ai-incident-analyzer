#!/usr/bin/env python3
"""Send a rich enterprise incident payload with K8s, DB metrics, and revenue data."""

import argparse
import json
import sys
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx

DEFAULT_BASE = "http://localhost:8000"
WEBHOOK_PATH = "/webhook/incident"
SLACK_ACTIONS_PATH = "/webhook/slack-actions"

ADVANCED_PAYLOAD = {
    "incident_id": "INC-2026-ADV-001",
    "title": "Payment API — Critical: Pool Exhaustion + OOM Cascade",
    "service_name": "payment-api",
    "severity": "critical",
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "company_hourly_revenue": 150_000.0,
    "downtime_minutes": 52.0,
    "k8s_metrics": [
        "Pod payment-api-7f8c9d-kl2mx: OOMKilled — container exceeded memory limit (512Mi)",
        "CPU Throttling > 85% sustained for 12 minutes on deployment/payment-api",
        "HPA unable to scale: max replicas (8) reached, pending pods stuck in ContainerCreating",
        "Liveness probe failures: 14 restarts in last 20 minutes",
    ],
    "db_slow_queries": [
        "Slow Query: SELECT * FROM orders WHERE status='pending' (Took 8.4s) — 1,240 executions/min",
        "Connection pool utilization: 100% (50/50 connections active)",
        "Lock wait timeout on table transactions — avg wait 4.2s",
        "Deadlock detected: txn_id=pay_8f3a2c1b waiting on row lock in orders_pkey",
    ],
    "custom_logs": [
        "2026-05-24T14:02:11Z ERROR [payment-api] CRITICAL: DatabaseTimeoutException in connection pool pool_id=primary-pg. Thread limit exceeded.",
        "2026-05-24T14:02:15Z WARN  [payment-api] HikariPool-1 - Connection is not available, request timed out after 2001ms.",
        "2026-05-24T14:02:25Z ERROR [payment-api] HTTP 503 returned for POST /v1/charges — all worker threads blocked on pool exhaustion.",
    ],
    "custom_commits": [
        {
            "commit": "a1b2c3d",
            "author": "Sarah (Dev)",
            "message": (
                "Performance tweak: aggressive downscaling of database pool "
                "max_connections timeout from 30s to 2s for extreme efficiency."
            ),
            "timestamp": "2026-05-24T13:50:00Z",
        },
        {
            "commit": "f4e5d6c",
            "author": "Mike (DevOps)",
            "message": "Reduce HikariCP maximumPoolSize from 50 to 10 to cut cloud DB costs.",
            "timestamp": "2026-05-24T11:30:00Z",
        },
    ],
}


def simulate_slack_rollback(base_url: str, commit_id: str = "a1b2c3d") -> int:
    """Simulate an engineer clicking Approve Rollback in Slack."""
    slack_payload = {
        "type": "block_actions",
        "user": {"username": "oncall-sre"},
        "actions": [
            {
                "action_id": "approve_rollback",
                "value": f"action_rollback_{commit_id}",
            }
        ],
    }
    url = f"{base_url.rstrip('/')}{SLACK_ACTIONS_PATH}"
    body = urlencode({"payload": json.dumps(slack_payload)})

    print(f"\nSimulating Slack Approve Rollback → {url}")
    try:
        response = httpx.post(
            url,
            content=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10.0,
        )
    except httpx.ConnectError:
        print("ERROR: Could not connect to slack-actions endpoint.", file=sys.stderr)
        return 1

    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    return 0 if response.status_code == 200 else 1


def send_incident(base_url: str) -> int:
    url = f"{base_url.rstrip('/')}{WEBHOOK_PATH}"
    print(f"Sending advanced incident to {url}")
    print(f"Payload:\n{json.dumps(ADVANCED_PAYLOAD, indent=2)}\n")

    try:
        response = httpx.post(
            url,
            json=ADVANCED_PAYLOAD,
            timeout=15.0,
        )
    except httpx.ConnectError:
        print(
            "ERROR: Could not connect. Start server with:\n"
            "  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000",
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
            "\nAdvanced incident queued. Check server logs for:\n"
            "  - RAG historical context injection\n"
            "  - Financial cost impact calculation\n"
            "  - Slack Block Kit with interactive buttons\n"
            "  - Streamlit dashboard: streamlit run dashboard.py"
        )
        return 0

    print(f"Unexpected status {response.status_code}", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Enterprise incident simulation runner")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE,
        help="API base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--slack-rollback",
        action="store_true",
        help="Also POST a simulated Slack Approve Rollback button click",
    )
    parser.add_argument(
        "--rollback-only",
        action="store_true",
        help="Only simulate Slack rollback (skip incident webhook)",
    )
    parser.add_argument(
        "--commit",
        default="a1b2c3d",
        help="Commit SHA for rollback simulation",
    )
    args = parser.parse_args()

    exit_code = 0
    if not args.rollback_only:
        exit_code = send_incident(args.base_url)
    if args.slack_rollback or args.rollback_only:
        slack_code = simulate_slack_rollback(args.base_url, args.commit)
        exit_code = exit_code or slack_code
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
