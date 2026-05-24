import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

from app.config import settings
from app.models import IncidentRecord

logger = logging.getLogger(__name__)


class IncidentStore:
    def __init__(self) -> None:
        self._db_path = Path(settings.incident_history_db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS incidents (
                    incident_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    service_name TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    report_markdown TEXT NOT NULL,
                    estimated_loss_usd REAL NOT NULL,
                    direct_revenue_loss_usd REAL NOT NULL,
                    engineering_triage_cost_usd REAL NOT NULL,
                    downtime_minutes REAL NOT NULL,
                    ai_accuracy_score REAL NOT NULL,
                    culprit_commit TEXT,
                    financial_summary TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def save(self, record: IncidentRecord) -> None:
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO incidents (
                        incident_id, title, service_name, severity, timestamp,
                        report_markdown, estimated_loss_usd, direct_revenue_loss_usd,
                        engineering_triage_cost_usd, downtime_minutes, ai_accuracy_score,
                        culprit_commit, financial_summary, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.incident_id,
                        record.title,
                        record.service_name,
                        record.severity,
                        record.timestamp,
                        record.report_markdown,
                        record.estimated_loss_usd,
                        record.direct_revenue_loss_usd,
                        record.engineering_triage_cost_usd,
                        record.downtime_minutes,
                        record.ai_accuracy_score,
                        record.culprit_commit,
                        record.financial_summary,
                        record.created_at,
                    ),
                )
                conn.commit()
            logger.info("Persisted incident %s to history store", record.incident_id)
        except sqlite3.Error as exc:
            logger.error("Failed to persist incident %s: %s", record.incident_id, exc)

    def list_all(self, limit: int = 100) -> list[dict[str, Any]]:
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM incidents
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as exc:
            logger.error("Failed to list incidents: %s", exc)
            return []

    def get_analytics(self) -> dict[str, Any]:
        incidents = self.list_all(limit=500)
        if not incidents:
            return {
                "total_incidents": 0,
                "total_estimated_loss_usd": 0.0,
                "total_revenue_saved_usd": 0.0,
                "average_ai_accuracy": 0.0,
                "by_service": [],
            }

        total_loss = sum(row["estimated_loss_usd"] for row in incidents)
        avg_accuracy = sum(row["ai_accuracy_score"] for row in incidents) / len(incidents)
        revenue_saved = sum(
            row["estimated_loss_usd"] * (row["ai_accuracy_score"] / 100.0)
            for row in incidents
        )

        service_map: dict[str, dict[str, float]] = {}
        for row in incidents:
            svc = row["service_name"]
            if svc not in service_map:
                service_map[svc] = {"service_name": svc, "incident_count": 0, "total_loss_usd": 0.0}
            service_map[svc]["incident_count"] += 1
            service_map[svc]["total_loss_usd"] += row["estimated_loss_usd"]

        return {
            "total_incidents": len(incidents),
            "total_estimated_loss_usd": round(total_loss, 2),
            "total_revenue_saved_usd": round(revenue_saved, 2),
            "average_ai_accuracy": round(avg_accuracy, 1),
            "by_service": list(service_map.values()),
        }

    def export_json(self) -> str:
        return json.dumps(self.list_all(), indent=2)
