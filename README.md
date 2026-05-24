# AI Incident Root Cause Analyzer Agent

Enterprise-grade FastAPI service that accepts infrastructure incident webhooks, correlates telemetry logs with recent git commits using OpenAI, and delivers structured root cause analysis reports to Slack or the console.

---

## Overview

When a monitoring system detects an outage, it POSTs an incident payload to this agent. The agent immediately returns `202 Accepted` so upstream webhooks never time out, then runs the full analysis pipeline in the background:

1. **Context Fetch** — Pulls error logs and recent commits (from a local simulation database or webhook overrides).
2. **LLM Analysis** — Sends structured context to OpenAI with a low-temperature SRE system prompt.
3. **Notification** — Delivers the markdown RCA to a Slack incoming webhook or prints it to the console.

```
Monitoring Tool ──POST──▶ /webhook/incident ──202──▶ Upstream (no timeout)
                                │
                                └── BackgroundTasks
                                      ├── ContextFetcher
                                      ├── IncidentAnalyzer (OpenAI)
                                      └── Notifier (Slack / Console)
```

---

## Prerequisites

| Requirement | Version |
|-------------|---------|
| Python | 3.10+ |
| OpenAI API Key | Optional (offline RCA if omitted) |
| Slack Incoming Webhook | Optional |

---

## Quick Start

### 1. Create and activate a virtual environment

**Windows (PowerShell):**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Copy the example file and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env`:

```env
OPENAI_API_KEY=sk-your-real-openai-api-key
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T000/B000/XXXXXXXX
LLM_MODEL=gpt-4o
```

`SLACK_WEBHOOK_URL` is optional. When omitted, reports are printed to the server console.

### 4. Start the server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Interactive API docs are available at [http://localhost:8000/docs](http://localhost:8000/docs).

### 5. Run the simulation script

In a second terminal (with the venv activated):

```bash
python simulate_alert.py
```

Expected output:

```
Status: 202
Response: {"status":"queued","message":"Incident INC-2026-0524-001 has been queued for AI root cause analysis and notification.","incident_id":"INC-2026-0524-001"}
```

Watch the **server terminal** for the full AI-generated incident report.

---

## Run & Test

Use **Python 3.10–3.13** (3.14 may fail on some dependencies). From the project root with the venv activated:

### Start the API

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Verify: [http://localhost:8000/](http://localhost:8000/) · [http://localhost:8000/docs](http://localhost:8000/docs) · [http://localhost:8000/api/health/detail](http://localhost:8000/api/health/detail)

### Test scripts (second terminal)

| Command | What it tests |
|---------|----------------|
| `python simulate_alert.py` | Basic incident webhook (`202` + console/Slack report) |
| `python simulate_advanced_alert.py` | Full payload: K8s metrics, DB slow queries, revenue/cost |
| `python simulate_advanced_alert.py --slack-rollback` | Simulated Slack **Approve Rollback** button |
| `python simulate_advanced_alert.py --rollback-only` | Rollback webhook only |

After a simulate run, check the **server terminal** for the RCA report. With `--slack-rollback`, expect a log like: `[EXECUTION] Successfully triggered automated GitHub Git Revert Action for commit ...`

### API smoke checks

```bash
curl http://localhost:8000/api/incidents
curl http://localhost:8000/api/analytics
```

Incident history is stored under `data/incidents.db` (and Chroma under `data/chroma/`).

### Streamlit dashboard (third terminal)

```bash
streamlit run dashboard.py
```

Open the URL shown (usually [http://localhost:8501](http://localhost:8501)). Run at least one simulate script first if the dashboard shows no incidents.

### Quick checklist

| Step | Success signal |
|------|----------------|
| Server starts | `GET /` returns `"status": "healthy"` |
| `simulate_alert.py` | HTTP **202**, processing logs in server terminal |
| `simulate_advanced_alert.py` | Report includes financial impact and infra correlation |
| `GET /api/incidents` | Returns saved incident rows |
| `streamlit run dashboard.py` | KPIs and charts after incidents exist |

### Troubleshooting

| Issue | Fix |
|-------|-----|
| `ModuleNotFoundError` | Activate venv; `pip install -r requirements.txt` |
| Simulate script cannot connect | Start uvicorn on port 8000 first |
| Offline RCA / no LLM | Set `OPENAI_API_KEY` in `.env` (optional; offline mode works without it) |
| No Slack message | Set `SLACK_WEBHOOK_URL`, or read the report in the server console |
| Broken venv / wrong Python | `py -3.12 -m venv .venv` then reinstall dependencies |

---

## API Reference

### `GET /` — Health Check

```bash
curl http://localhost:8000/
```

Response:

```json
{
  "status": "healthy",
  "service": "ai-incident-analyzer",
  "version": "1.0.0"
}
```

### `POST /webhook/incident` — Queue Incident Analysis

Accepts an incident payload and returns immediately with HTTP `202`.

**Request body:**

```json
{
  "incident_id": "INC-2026-0524-001",
  "title": "Payment API — Database Connection Pool Exhaustion",
  "service_name": "payment-api",
  "severity": "critical",
  "timestamp": "2026-05-24T14:02:00Z",
  "custom_logs": ["optional override log line 1"],
  "custom_commits": [
    {
      "commit": "a1b2c3d",
      "author": "Sarah (Dev)",
      "message": "Performance tweak: pool timeout 30s to 2s",
      "timestamp": "2026-05-24T13:50:00Z"
    }
  ]
}
```

`custom_logs` and `custom_commits` are optional. When omitted, the agent reads from its built-in simulation database keyed by `service_name`.

**Response (202):**

```json
{
  "status": "queued",
  "message": "Incident INC-2026-0524-001 has been queued for AI root cause analysis and notification.",
  "incident_id": "INC-2026-0524-001"
}
```

**Example with curl:**

```bash
curl -X POST http://localhost:8000/webhook/incident \
  -H "Content-Type: application/json" \
  -d '{
    "incident_id": "INC-TEST-001",
    "title": "Payment API outage",
    "service_name": "payment-api",
    "severity": "critical",
    "timestamp": "2026-05-24T14:02:00Z"
  }'
```

---

## Project Structure

```
project/
├── .env.example              # Environment variable template
├── requirements.txt          # Pinned Python dependencies
├── README.md                 # This file
├── simulate_alert.py         # Local integration test script
└── app/
    ├── __init__.py
    ├── config.py             # Pydantic Settings (env var management)
    ├── main.py               # FastAPI entrypoint and routes
    ├── models.py             # Pydantic V2 request/response schemas
    └── services/
        ├── __init__.py
        ├── analyzer.py       # OpenAI LLM reasoning engine
        ├── context_fetcher.py # Mock log/git telemetry extraction
        └── notifier.py       # Slack webhook / console delivery
```

---

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | No | — | OpenAI API key for LLM analysis (offline RCA if omitted) |
| `SLACK_WEBHOOK_URL` | No | `None` | Slack incoming webhook URL for report delivery |
| `LLM_MODEL` | No | `gpt-4o` | OpenAI model identifier |

---

## Built-in Simulation Data

The context fetcher includes hardcoded telemetry for these services:

| Service | Scenario |
|---------|----------|
| `payment-api` | Database pool timeout, connection drops, thread limit exceeded |
| `user-service` | Auth DB unreachable, cascade failures, circuit breaker open |
| `default` | Generic fallback for unknown service names |

Each service also has correlated git commits, including a known culprit commit (`a1b2c3d` by Sarah) that aggressively reduced pool timeout from 30s to 2s.

---

## Real-Time Execution Tracking

When an incident is processed, the server logs follow this sequence:

```
INFO  | Received incident webhook: id=INC-... service=payment-api severity=critical
INFO  | Processing incident INC-... in background
INFO  | Starting LLM analysis for incident INC-... (service=payment-api)
INFO  | LLM analysis complete for incident INC-... (XXXX chars)
INFO  | Incident report printed to console (no Slack webhook configured)
INFO  | Incident INC-... processing complete
```

If `SLACK_WEBHOOK_URL` is set, the notifier log line reads `Incident report delivered to Slack successfully` instead.

---

## Production Deployment Notes

- **Workers**: Run with multiple workers for throughput: `uvicorn app.main:app --workers 4 --host 0.0.0.0 --port 8000`
- **Secrets**: Inject `OPENAI_API_KEY` and `SLACK_WEBHOOK_URL` via your platform's secret manager (Kubernetes Secrets, AWS SSM, etc.). Never commit `.env` to version control.
- **Reverse proxy**: Place nginx or a cloud load balancer in front for TLS termination.
- **Monitoring**: The `GET /` health endpoint is suitable for liveness/readiness probes.
- **Rate limiting**: Consider adding rate limiting at the proxy layer if exposed to external webhook sources.

---

## Push to GitHub (public repo)

**Prerequisites:** [Git for Windows](https://git-scm.com/download/win) (`winget install Git.Git`)

From the project root (`project\project`):

```powershell
# Option A — helper script (replace YOUR_GITHUB_USERNAME)
.\scripts\push-to-github.ps1 -GitHubUsername YOUR_GITHUB_USERNAME

# Option B — manual commands
git init
git branch -M main
git add -A
git commit -m "Initial commit: enterprise AI incident root cause analyzer"
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/ai-incident-analyzer.git
git push -u origin main
```

Before pushing, create an **empty public** repository on GitHub (no README/license). `.env` and `data/` are gitignored.

Sign in when prompted (browser), or install [GitHub CLI](https://cli.github.com/) and run `gh auth login`.

---

## License

Internal use — enterprise incident response tooling.
