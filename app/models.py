from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class CommitInfo(BaseModel):
    commit: str = Field(..., description="Short SHA of the git commit")
    author: str = Field(..., description="Author who authored the commit")
    message: str = Field(..., description="Commit message summary")
    timestamp: str | None = Field(
        default=None,
        description="ISO-8601 timestamp of when the commit was created",
    )


class AlertPayload(BaseModel):
    incident_id: str = Field(..., description="Unique identifier for the incident")
    title: str = Field(..., description="Human-readable incident title")
    service_name: str = Field(..., description="Name of the affected service")
    severity: str = Field(..., description="Incident severity level (e.g. critical, high)")
    timestamp: datetime = Field(..., description="When the incident was detected")
    custom_logs: list[str] | None = Field(
        default=None,
        description="Optional override: raw log lines to use instead of the local database",
    )
    custom_commits: list[CommitInfo] | None = Field(
        default=None,
        description="Optional override: recent commits to use instead of the local database",
    )
    k8s_metrics: list[str] | None = Field(
        default=None,
        description="Kubernetes telemetry (pod events, CPU throttling, OOM, etc.)",
    )
    db_slow_queries: list[str] | None = Field(
        default=None,
        description="Database slow-query telemetry lines",
    )
    company_hourly_revenue: float | None = Field(
        default=None,
        description="Average company revenue per hour (USD) for cost impact modeling",
    )
    downtime_minutes: float | None = Field(
        default=None,
        description="Estimated or observed outage duration in minutes",
    )


class QueuedResponse(BaseModel):
    status: Literal["queued"] = Field(..., description="Processing status")
    message: str = Field(..., description="Human-readable status message")
    incident_id: str = Field(..., description="Echo of the incident identifier")


class HealthResponse(BaseModel):
    status: Literal["healthy"] = Field(..., description="Service health status")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")


class SlackActionResponse(BaseModel):
    response_type: str = "in_channel"
    text: str
    replace_original: bool = False


class IncidentRecord(BaseModel):
    incident_id: str
    title: str
    service_name: str
    severity: str
    timestamp: str
    report_markdown: str
    estimated_loss_usd: float
    direct_revenue_loss_usd: float
    engineering_triage_cost_usd: float
    downtime_minutes: float
    ai_accuracy_score: float
    culprit_commit: str | None = None
    financial_summary: str = ""
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class IncidentHistoryResponse(BaseModel):
    total: int
    incidents: list[dict[str, Any]]
