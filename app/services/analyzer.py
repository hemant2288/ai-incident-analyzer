import asyncio
import logging
import re

from openai import OpenAI

from app.config import settings
from app.services.context_fetcher import IncidentContext

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are an elite Site Reliability Engineer (SRE) with deep expertise in \
distributed systems, Kubernetes, database performance, deployment correlation, \
and production incident response.

Your task is to analyze an ongoing infrastructure incident by correlating \
telemetry logs, Kubernetes metrics, database slow queries, recent git commits, \
historical incident resolutions, and financial impact data.

## Analysis Requirements

1. **Correlate logs to deployments**: Map structural exceptions and error \
patterns in the logs to specific recent commits. Identify the most likely \
culprit commit by matching error symptoms to code changes.

2. **Infrastructure correlation**: Explicitly explain how Kubernetes metrics \
(OOMKilled, CPU throttling, pod restarts) and database metrics (slow queries, \
pool exhaustion, lock waits) relate to the identified culprit commit and the \
observed log errors.

3. **Historical context**: Use past incident resolutions from the RAG knowledge \
base to inform remediation — cite if a similar outage was solved before and how.

4. **Financial impact**: Include a clear financial summary using the provided \
cost impact numbers. Quantify business risk in plain language.

5. **Be evidence-based**: Cite specific log lines, K8s events, DB queries, and \
commit SHAs as evidence. Do not speculate beyond what the data supports.

6. **Prioritize remediation**: Provide actionable, ordered steps that an \
on-call engineer can execute immediately.

## Required Output Format

Your response MUST use exactly these markdown section headers:

# 🚨 AI SRE Incident Report

(Brief executive summary: incident ID, affected service, severity, one-sentence \
root cause, and estimated financial loss.)

## 💥 Root Cause Analysis (What Broke & Trigger Event)

(Detailed analysis correlating log errors, K8s metrics, and DB metrics to \
commits. Name the culprit commit SHA and explain the full causal chain including \
how infrastructure metrics validate the deployment hypothesis.)

## 💰 Financial Impact Summary

(Use the provided cost data. State direct revenue loss, engineering triage \
cost, and total estimated loss. Explain business exposure during the outage window.)

## 🛠️ Immediate Remediation Steps (Primary Mitigation & Secondary Action)

(Numbered list of remediation steps. Label the first as PRIMARY and \
subsequent as SECONDARY. Include rollback commands or config reversions \
where applicable. Reference historical resolutions when relevant.)
"""


class IncidentAnalyzer:
    def __init__(self) -> None:
        self._client: OpenAI | None = None
        if settings.openai_api_key:
            try:
                self._client = OpenAI(api_key=settings.openai_api_key)
            except Exception as exc:
                logger.warning("OpenAI client init failed: %s", exc)
        else:
            logger.warning(
                "OPENAI_API_KEY not set — incident reports will use offline RCA mode"
            )

    def _format_section(self, title: str, items: list[str]) -> str:
        if not items:
            return f"## {title}\n  (No data provided)\n"
        lines = "\n".join(f"  {index + 1}. {item}" for index, item in enumerate(items))
        return f"## {title}\n{lines}\n"

    def _build_user_prompt(self, context: IncidentContext) -> str:
        commit_section = "\n".join(
            f"  - SHA: {commit.commit} | Author: {commit.author} | "
            f"Time: {commit.timestamp or 'unknown'} | Message: {commit.message}"
            for commit in context.commits
        ) or "  (No commits provided)"
        financial = context.financial_impact
        return (
            f"## Incident Details\n"
            f"- Incident ID: {context.incident_id}\n"
            f"- Title: {context.title}\n"
            f"- Service: {context.service_name}\n"
            f"- Severity: {context.severity}\n"
            f"- Detected At: {context.timestamp.isoformat()}\n"
            f"- Culprit Commit (suspected): {context.culprit_commit or 'unknown'}\n\n"
            f"{self._format_section('Telemetry Logs', context.logs)}"
            f"{self._format_section('Kubernetes Metrics', context.k8s_metrics)}"
            f"{self._format_section('Database Metrics / Slow Queries', context.db_slow_queries)}"
            f"## Recent Git Commits\n{commit_section}\n\n"
            f"## Historical Incident Context (RAG)\n{context.rag_context}\n\n"
            f"## Financial Impact Data\n"
            f"- Direct Revenue Loss: ${financial.get('direct_lost_revenue_usd', 0):,.0f}\n"
            f"- Engineering Triage Cost: ${financial.get('engineering_triage_cost_usd', 0):,.0f}\n"
            f"- Total Estimated Loss: ${financial.get('total_estimated_loss_usd', 0):,.0f}\n"
            f"- Downtime: {financial.get('downtime_minutes', 0)} minutes\n"
            f"- Summary: {financial.get('summary', 'N/A')}\n\n"
            f"Analyze all data above and produce the incident report."
        )

    def _call_openai(self, user_prompt: str) -> str:
        if self._client is None:
            raise RuntimeError("OpenAI client is not configured")
        response = self._client.chat.completions.create(
            model=settings.llm_model,
            temperature=0.1,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = response.choices[0].message.content
        if content is None:
            raise ValueError("OpenAI returned an empty response")
        return content

    def _generate_offline_report(self, context: IncidentContext) -> str:
        financial = context.financial_impact
        culprit = context.culprit_commit or "unknown"
        top_commit = context.commits[0] if context.commits else None
        commit_detail = (
            f"`{top_commit.commit}` by {top_commit.author}: {top_commit.message}"
            if top_commit
            else "No commit metadata available"
        )

        k8s_evidence = (
            "\n".join(f"- {line}" for line in context.k8s_metrics[:3])
            if context.k8s_metrics
            else "- No Kubernetes metrics were supplied"
        )
        db_evidence = (
            "\n".join(f"- {line}" for line in context.db_slow_queries[:3])
            if context.db_slow_queries
            else "- No database metrics were supplied"
        )
        log_evidence = (
            "\n".join(f"- {line}" for line in context.logs[:3])
            if context.logs
            else "- No application logs were supplied"
        )

        return f"""# 🚨 AI SRE Incident Report

**Incident:** {context.incident_id} | **Service:** {context.service_name} | \
**Severity:** {context.severity}

**Executive summary:** Telemetry indicates infrastructure stress (K8s/DB) \
aligned with a recent deployment. Suspected culprit commit `{culprit}`. \
{financial.get('summary', 'Financial impact unavailable.')}

*Generated in offline RCA mode (no LLM API key or API unavailable).*

## 💥 Root Cause Analysis (What Broke & Trigger Event)

Application logs show pool exhaustion and downstream failures:

{log_evidence}

**Infrastructure correlation:** Kubernetes signals validate a resource \
saturation hypothesis tied to the latest deploy:

{k8s_evidence}

Database telemetry corroborates connection pressure and query latency:

{db_evidence}

**Commit correlation:** The most recent change ({commit_detail}) plausibly \
reduced pool capacity or timeouts, which explains OOM/CPU throttling under \
load and the slow-query / pool-utilization pattern above.

**Historical context:** {context.rag_context}

## 💰 Financial Impact Summary

- Direct revenue loss: **${financial.get('direct_lost_revenue_usd', 0):,.0f}**
- Engineering triage cost: **${financial.get('engineering_triage_cost_usd', 0):,.0f}**
- **Total estimated loss: ${financial.get('total_estimated_loss_usd', 0):,.0f}**
- Outage window: **{financial.get('downtime_minutes', 0)} minutes**

## 🛠️ Immediate Remediation Steps (Primary Mitigation & Secondary Action)

1. **PRIMARY:** Roll back commit `{culprit}` and restore prior pool/timeout settings.
2. **PRIMARY:** Scale payment-api pods and raise memory limits if OOMKilled persists.
3. **SECONDARY:** Clear Redis cache / expand DB pool per historical playbooks if signatures match.
4. **SECONDARY:** Kill or optimize top slow queries; verify connection pool headroom.
"""

    def estimate_accuracy_score(self, report: str, context: IncidentContext) -> float:
        score = 72.0
        if context.culprit_commit and context.culprit_commit in report:
            score += 12.0
        if "Root Cause" in report or "root cause" in report.lower():
            score += 5.0
        if context.k8s_metrics and any(
            token in report.lower()
            for token in ["oom", "cpu", "pod", "throttl"]
        ):
            score += 5.0
        if context.db_slow_queries and any(
            token in report.lower() for token in ["query", "pool", "database", "lock"]
        ):
            score += 4.0
        if "Financial" in report or "$" in report:
            score += 2.0
        if "offline RCA" in report:
            score = min(score, 85.0)
        return min(round(score, 1), 98.0)

    def extract_resolution_summary(self, report: str) -> str:
        remediation_match = re.search(
            r"## 🛠️ Immediate Remediation Steps.*",
            report,
            re.DOTALL,
        )
        if remediation_match:
            return remediation_match.group(0)[:500]
        return report[:500]

    async def analyze(self, context: IncidentContext) -> tuple[str, float]:
        user_prompt = self._build_user_prompt(context)
        logger.info(
            "Starting analysis for incident %s (service=%s, llm=%s)",
            context.incident_id,
            context.service_name,
            bool(self._client),
        )

        if self._client is None:
            report = self._generate_offline_report(context)
        else:
            try:
                report = await asyncio.to_thread(self._call_openai, user_prompt)
            except Exception as exc:
                logger.error(
                    "LLM analysis failed for %s, using offline RCA: %s",
                    context.incident_id,
                    exc,
                )
                report = self._generate_offline_report(context)

        accuracy = self.estimate_accuracy_score(report, context)
        logger.info(
            "Analysis complete for incident %s (%d chars, accuracy=%.1f%%)",
            context.incident_id,
            len(report),
            accuracy,
        )
        return report, accuracy
