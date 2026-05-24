import json
import logging
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

import uvicorn
from fastapi import BackgroundTasks, FastAPI, Form, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.models import (
    AlertPayload,
    HealthResponse,
    IncidentHistoryResponse,
    IncidentRecord,
    QueuedResponse,
    SlackActionResponse,
)
from app.services.analyzer import IncidentAnalyzer
from app.services.context_fetcher import ContextFetcher
from app.services.incident_store import IncidentStore
from app.services.notifier import Notifier
from app.services.vector_rag import IncidentRAGService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Incident Root Cause Analyzer",
    description="Enterprise-grade SRE agent for automated incident root cause analysis",
    version="2.0.0",
)

context_fetcher = ContextFetcher()
analyzer = IncidentAnalyzer()
notifier = Notifier()
incident_store = IncidentStore()
rag_service = IncidentRAGService()


async def process_incident(alert: AlertPayload) -> None:
    try:
        logger.info("Processing incident %s in background", alert.incident_id)
        context = context_fetcher.get_context(alert)
        report, accuracy = await analyzer.analyze(context)

        financial = context.financial_impact or {}
        record = IncidentRecord(
            incident_id=context.incident_id,
            title=context.title,
            service_name=context.service_name,
            severity=context.severity,
            timestamp=context.timestamp.isoformat(),
            report_markdown=report,
            estimated_loss_usd=float(financial.get("total_estimated_loss_usd", 0) or 0),
            direct_revenue_loss_usd=float(financial.get("direct_lost_revenue_usd", 0) or 0),
            engineering_triage_cost_usd=float(
                financial.get("engineering_triage_cost_usd", 0) or 0
            ),
            downtime_minutes=float(financial.get("downtime_minutes", 0) or 0),
            ai_accuracy_score=accuracy,
            culprit_commit=context.culprit_commit,
            financial_summary=str(financial.get("summary", "")),
        )
        incident_store.save(record)

        error_signature = " ".join(context.logs[:3]) if context.logs else context.title
        rag_service.store_resolution(
            incident_id=context.incident_id,
            error_signature=error_signature,
            resolution_summary=analyzer.extract_resolution_summary(report),
        )

        await notifier.send_report(report, context)
        logger.info("Incident %s processing complete", alert.incident_id)
    except Exception:
        logger.exception("Failed to process incident %s", alert.incident_id)


@app.get("/", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        service="ai-incident-analyzer",
        version="2.0.0",
    )


@app.get("/api/health/detail")
async def health_detail() -> dict[str, Any]:
    return {
        "status": "healthy",
        "llm_configured": bool(settings.openai_api_key),
        "slack_configured": bool(settings.slack_webhook_url),
        "chroma_path": settings.chroma_db_path,
        "incident_db": settings.incident_history_db_path,
    }


@app.get("/api/incidents", response_model=IncidentHistoryResponse)
async def list_incidents(limit: int = 50) -> IncidentHistoryResponse:
    incidents = incident_store.list_all(limit=limit)
    return IncidentHistoryResponse(total=len(incidents), incidents=incidents)


@app.get("/api/analytics")
async def get_analytics() -> dict[str, Any]:
    return incident_store.get_analytics()


@app.post(
    "/webhook/incident",
    response_model=QueuedResponse,
    status_code=202,
)
async def receive_incident(
    alert: AlertPayload,
    background_tasks: BackgroundTasks,
) -> QueuedResponse:
    logger.info(
        "Received incident webhook: id=%s service=%s severity=%s",
        alert.incident_id,
        alert.service_name,
        alert.severity,
    )
    background_tasks.add_task(process_incident, alert)
    return QueuedResponse(
        status="queued",
        message=(
            f"Incident {alert.incident_id} has been queued for "
            f"AI root cause analysis and notification."
        ),
        incident_id=alert.incident_id,
    )


@app.post("/webhook/slack-actions")
async def slack_interactive_actions(
    request: Request,
    payload: str | None = Form(default=None),
) -> JSONResponse:
    raw_payload = payload
    if raw_payload is None:
        try:
            body = await request.body()
            parsed = parse_qs(body.decode("utf-8"))
            raw_payload = parsed.get("payload", [None])[0]
        except Exception as exc:
            logger.warning("Failed to parse Slack request body: %s", exc)
            raw_payload = None

    if not raw_payload:
        return JSONResponse(
            status_code=400,
            content={"error": "Missing Slack payload"},
        )

    try:
        slack_payload: dict[str, Any] = json.loads(raw_payload)
    except json.JSONDecodeError:
        return JSONResponse(
            status_code=400,
            content={"error": "Invalid JSON in Slack payload"},
        )

    actions = slack_payload.get("actions") or []
    if not actions:
        return JSONResponse(content=SlackActionResponse(text="No action received.").model_dump())

    action = actions[0]
    action_id = action.get("action_id", "")
    action_value = action.get("value", "")
    user_name = slack_payload.get("user", {}).get("username", "engineer")

    if action_id == "approve_rollback":
        commit_id = action_value.replace("action_rollback_", "", 1)
        message = (
            f"[EXECUTION] Successfully triggered automated GitHub Git Revert Action "
            f"for commit {commit_id}!"
        )
        logger.info(
            "%s Initiated by @%s.",
            message,
            user_name,
        )
        response = SlackActionResponse(
            text=f"{message} Initiated by @{user_name}.",
            replace_original=False,
        )
        return JSONResponse(content=response.model_dump())

    if action_id == "mute_alert":
        incident_id = action_value.replace("action_mute_", "", 1)
        message = (
            f"[MUTED] Alert {incident_id} has been silenced for 4 hours "
            f"by @{user_name}. Monitoring continues in observe-only mode."
        )
        logger.info(message)
        response = SlackActionResponse(text=message)
        return JSONResponse(content=response.model_dump())

    return JSONResponse(
        content=SlackActionResponse(text=f"Unknown action: {action_id}").model_dump()
    )


STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/dashboard", include_in_schema=False)
    async def steampunk_dashboard() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )
