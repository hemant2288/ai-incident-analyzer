from dataclasses import dataclass
from datetime import datetime

from app.config import settings
from app.models import AlertPayload, CommitInfo
from app.services.cost_calculator import calculate_financial_loss
from app.services.vector_rag import IncidentRAGService


@dataclass(frozen=True)
class IncidentContext:
    incident_id: str
    title: str
    service_name: str
    severity: str
    timestamp: datetime
    logs: list[str]
    commits: list[CommitInfo]
    k8s_metrics: list[str]
    db_slow_queries: list[str]
    rag_context: str
    financial_impact: dict[str, float | str]
    culprit_commit: str | None


LOCAL_LOG_DATABASE: dict[str, list[str]] = {
    "payment-api": [
        "2026-05-24T14:02:11Z ERROR [payment-api] CRITICAL: DatabaseTimeoutException in connection pool pool_id=primary-pg. Thread limit exceeded.",
        "2026-05-24T14:02:13Z ERROR [payment-api] Connection dropped while handling transaction txn_id=pay_8f3a2c1b.",
        "2026-05-24T14:02:15Z WARN  [payment-api] HikariPool-1 - Connection is not available, request timed out after 2001ms.",
        "2026-05-24T14:02:18Z ERROR [payment-api] Failed to acquire JDBC Connection; nested exception is java.sql.SQLTransientConnectionException.",
        "2026-05-24T14:02:22Z ERROR [payment-api] Circuit breaker OPEN for downstream dependency 'billing-db' after 12 consecutive failures.",
        "2026-05-24T14:02:25Z ERROR [payment-api] HTTP 503 returned for POST /v1/charges — all worker threads blocked on pool exhaustion.",
    ],
    "user-service": [
        "2026-05-24T13:45:01Z ERROR [user-service] CRITICAL: Upstream dependency 'auth-db' unreachable — DNS resolution timeout after 5000ms.",
        "2026-05-24T13:45:04Z ERROR [user-service] Cascade failure: session validation failed for 847 concurrent requests.",
        "2026-05-24T13:45:07Z WARN  [user-service] Circuit breaker OPEN for 'auth-db' — fast-failing all authentication requests.",
        "2026-05-24T13:45:10Z ERROR [user-service] Health check FAILED: readiness probe returning 503 for pod user-service-7d4f9b.",
    ],
    "default": [
        "2026-05-24T12:00:00Z ERROR [generic-service] CRITICAL: Unhandled exception in request handler — NullPointerException at ServiceLayer.process().",
        "2026-05-24T12:00:02Z ERROR [generic-service] Elevated error rate detected: 42% of requests returning HTTP 500.",
        "2026-05-24T12:00:05Z WARN  [generic-service] Memory usage at 91% — GC pause times exceeding 800ms.",
    ],
}

LOCAL_K8S_DATABASE: dict[str, list[str]] = {
    "payment-api": [
        "Pod payment-api-7f8c9d-kl2mx: OOMKilled — container exceeded memory limit (512Mi)",
        "CPU Throttling > 85% sustained for 12 minutes on deployment/payment-api",
        "HPA unable to scale: max replicas (8) reached, pending pods stuck in ContainerCreating",
        "Liveness probe failures: 14 restarts in last 20 minutes",
        "Event: FailedScheduling — insufficient memory on node pool worker-3",
    ],
    "user-service": [
        "Pod user-service-7d4f9b-x9k2p: CrashLoopBackOff — exit code 137 (SIGKILL)",
        "CPU Throttling > 72% on deployment/user-service",
        "Readiness probe returning 503 — 3/5 pods not ready",
        "NetworkPolicy drop rate elevated: 2.4% packet loss to auth-db subnet",
    ],
    "default": [
        "Pod generic-service-abc12: Warning — high ephemeral storage usage (89%)",
        "CPU Throttling > 60% on deployment/generic-service",
    ],
}

LOCAL_DB_METRICS_DATABASE: dict[str, list[str]] = {
    "payment-api": [
        "Slow Query: SELECT * FROM orders WHERE status='pending' (Took 8.4s) — 1,240 executions/min",
        "Connection pool utilization: 100% (50/50 connections active)",
        "Lock wait timeout on table transactions — avg wait 4.2s",
        "Replication lag on read-replica billing-db-2: 38 seconds behind primary",
        "Deadlock detected: txn_id=pay_8f3a2c1b waiting on row lock in orders_pkey",
    ],
    "user-service": [
        "Slow Query: SELECT u.*, s.token FROM users u JOIN sessions s ON u.id=s.user_id (Took 6.1s)",
        "Connection pool utilization: 94% (47/50 connections active)",
        "Index scan on sessions table — seq scan detected, missing index on expires_at",
    ],
    "default": [
        "Slow Query: SELECT COUNT(*) FROM audit_log WHERE created_at > NOW() - INTERVAL '1 day' (Took 5.2s)",
    ],
}

LOCAL_COMMIT_DATABASE: dict[str, list[CommitInfo]] = {
    "payment-api": [
        CommitInfo(
            commit="a1b2c3d",
            author="Sarah (Dev)",
            message=(
                "Performance tweak: aggressive downscaling of database pool "
                "max_connections timeout parameter from 30s to 2s for extreme efficiency."
            ),
            timestamp="2026-05-24T13:50:00Z",
        ),
        CommitInfo(
            commit="f4e5d6c",
            author="Mike (DevOps)",
            message="Reduce HikariCP maximumPoolSize from 50 to 10 to cut cloud DB costs.",
            timestamp="2026-05-24T11:30:00Z",
        ),
        CommitInfo(
            commit="b7c8d9e",
            author="Alex (Backend)",
            message="Add retry logic for transient DB connection failures with 3x backoff.",
            timestamp="2026-05-24T09:15:00Z",
        ),
    ],
    "user-service": [
        CommitInfo(
            commit="c3d4e5f",
            author="Jordan (Platform)",
            message="Switch auth-db connection string to new read-replica endpoint in us-east-2.",
            timestamp="2026-05-24T13:20:00Z",
        ),
        CommitInfo(
            commit="1a2b3c4",
            author="Taylor (SRE)",
            message="Tighten session TTL from 24h to 15m for security compliance.",
            timestamp="2026-05-24T10:00:00Z",
        ),
    ],
    "default": [
        CommitInfo(
            commit="deadbeef",
            author="Unknown Developer",
            message="Refactor service initialization order — moved config load after network bind.",
            timestamp="2026-05-24T08:00:00Z",
        ),
    ],
}


class ContextFetcher:
    def __init__(self) -> None:
        self._rag = IncidentRAGService()

    def get_logs(
        self,
        service_name: str,
        custom_logs: list[str] | None = None,
    ) -> list[str]:
        if custom_logs is not None:
            return custom_logs
        return LOCAL_LOG_DATABASE.get(service_name, LOCAL_LOG_DATABASE["default"])

    def get_commits(
        self,
        service_name: str,
        custom_commits: list[CommitInfo] | None = None,
    ) -> list[CommitInfo]:
        if custom_commits is not None:
            return custom_commits
        return LOCAL_COMMIT_DATABASE.get(
            service_name,
            LOCAL_COMMIT_DATABASE["default"],
        )

    def get_k8s_metrics(
        self,
        service_name: str,
        custom_k8s: list[str] | None = None,
    ) -> list[str]:
        if custom_k8s is not None:
            return custom_k8s
        return LOCAL_K8S_DATABASE.get(service_name, LOCAL_K8S_DATABASE["default"])

    def get_db_metrics(
        self,
        service_name: str,
        custom_db: list[str] | None = None,
    ) -> list[str]:
        if custom_db is not None:
            return custom_db
        return LOCAL_DB_METRICS_DATABASE.get(
            service_name,
            LOCAL_DB_METRICS_DATABASE["default"],
        )

    def get_context(self, alert: AlertPayload) -> IncidentContext:
        logs = self.get_logs(alert.service_name, alert.custom_logs)
        commits = self.get_commits(alert.service_name, alert.custom_commits)
        k8s_metrics = self.get_k8s_metrics(alert.service_name, alert.k8s_metrics)
        db_slow_queries = self.get_db_metrics(alert.service_name, alert.db_slow_queries)

        error_signature = " ".join(logs[:3]) if logs else alert.title
        rag_context = self._rag.search_past_incidents(error_signature)

        hourly_revenue = (
            alert.company_hourly_revenue
            if alert.company_hourly_revenue is not None
            else settings.company_hourly_revenue
        )
        downtime_minutes = (
            alert.downtime_minutes
            if alert.downtime_minutes is not None
            else settings.default_downtime_minutes
        )
        financial_impact = calculate_financial_loss(
            service_name=alert.service_name,
            downtime_minutes=downtime_minutes,
            company_hourly_revenue=hourly_revenue,
        )

        culprit_commit = commits[0].commit if commits else None

        return IncidentContext(
            incident_id=alert.incident_id,
            title=alert.title,
            service_name=alert.service_name,
            severity=alert.severity,
            timestamp=alert.timestamp,
            logs=logs,
            commits=commits,
            k8s_metrics=k8s_metrics,
            db_slow_queries=db_slow_queries,
            rag_context=rag_context,
            financial_impact=financial_impact,
            culprit_commit=culprit_commit,
        )
