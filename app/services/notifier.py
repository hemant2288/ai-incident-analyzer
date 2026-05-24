import logging
import sys
from typing import Any

import httpx

from app.config import settings
from app.services.context_fetcher import IncidentContext

logger = logging.getLogger(__name__)

CONSOLE_BORDER = "=" * 72


class Notifier:
    def build_slack_blocks(
        self,
        report_markdown: str,
        context: IncidentContext,
    ) -> list[dict[str, Any]]:
        financial = context.financial_impact
        rollback_value = f"action_rollback_{context.culprit_commit or 'unknown'}"

        return [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🚨 Incident: {context.incident_id}",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Service:*\n{context.service_name}"},
                    {"type": "mrkdwn", "text": f"*Severity:*\n{context.severity}"},
                    {
                        "type": "mrkdwn",
                        "text": f"*Est. Loss:*\n${financial.get('total_estimated_loss_usd', 0):,.0f}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Culprit Commit:*\n`{context.culprit_commit or 'TBD'}`",
                    },
                ],
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": report_markdown[:2900],
                },
            },
            {"type": "divider"},
            {
                "type": "actions",
                "block_id": "incident_actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "🔴 Approve Rollback",
                            "emoji": True,
                        },
                        "style": "danger",
                        "action_id": "approve_rollback",
                        "value": rollback_value,
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "🟢 Mute Alert",
                            "emoji": True,
                        },
                        "action_id": "mute_alert",
                        "value": f"action_mute_{context.incident_id}",
                    },
                ],
            },
        ]

    async def send_report(
        self,
        report_markdown: str,
        context: IncidentContext,
    ) -> None:
        if settings.slack_webhook_url:
            await self._send_to_slack(report_markdown, context)
        else:
            self._print_to_console(report_markdown, context)

    async def _send_to_slack(
        self,
        report_markdown: str,
        context: IncidentContext,
    ) -> None:
        blocks = self.build_slack_blocks(report_markdown, context)
        payload: dict[str, Any] = {
            "text": f"AI SRE Incident Report — {context.incident_id}",
            "blocks": blocks,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    settings.slack_webhook_url,
                    json=payload,
                )
                response.raise_for_status()
            logger.info(
                "Incident report delivered to Slack (Block Kit) for %s",
                context.incident_id,
            )
        except httpx.HTTPError as exc:
            logger.error("Slack Block Kit delivery failed, falling back to text: %s", exc)
            fallback_payload = {"text": report_markdown}
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        settings.slack_webhook_url,
                        json=fallback_payload,
                    )
                    response.raise_for_status()
                logger.info("Incident report delivered via Slack text fallback")
            except httpx.HTTPError as fallback_exc:
                logger.error("Slack text fallback also failed: %s", fallback_exc)
                self._print_to_console(report_markdown, context)

    def _print_to_console(
        self,
        report_markdown: str,
        context: IncidentContext,
    ) -> None:
        financial = context.financial_impact
        output = (
            f"\n{CONSOLE_BORDER}\n"
            f"  [INCIDENT REPORT] — Slack webhook not configured\n"
            f"  Incident: {context.incident_id} | Service: {context.service_name}\n"
            f"  Est. Loss: ${financial.get('total_estimated_loss_usd', 0):,.0f}\n"
            f"  [Actions] 🔴 Approve Rollback ({context.culprit_commit})"
            f" | 🟢 Mute Alert\n"
            f"{CONSOLE_BORDER}\n\n"
            f"{report_markdown}\n\n"
            f"{CONSOLE_BORDER}\n"
        )
        sys.stdout.write(output)
        sys.stdout.flush()
        logger.info("Incident report printed to console (no Slack webhook configured)")
