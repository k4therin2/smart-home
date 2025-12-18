"""
Slack Webhook Client for Security Alerts

Simple, no-dependency Slack integration using webhooks.
"""

import json
import logging
import urllib.request
import urllib.error
from datetime import datetime
from typing import Optional, Dict, Any, List

from src.security.config import SLACK_WEBHOOK_URL

logger = logging.getLogger("security.slack")


class SlackNotifier:
    """Send security alerts and reports to Slack via webhook."""

    def __init__(self, webhook_url: Optional[str] = None):
        """
        Initialize Slack notifier.

        Args:
            webhook_url: Slack webhook URL (defaults to env var)
        """
        self.webhook_url = webhook_url or SLACK_WEBHOOK_URL
        if not self.webhook_url:
            logger.warning("SLACK_SECURITY_WEBHOOK not configured - alerts will only be logged")

    def _send(self, payload: Dict[str, Any]) -> bool:
        """
        Send payload to Slack webhook.

        Args:
            payload: Slack message payload

        Returns:
            True if successful, False otherwise
        """
        if not self.webhook_url:
            logger.info(f"[DRY RUN] Would send to Slack: {json.dumps(payload, indent=2)}")
            return False

        try:
            data = json.dumps(payload).encode("utf-8")
            request = urllib.request.Request(
                self.webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                if response.status == 200:
                    logger.debug("Slack notification sent successfully")
                    return True
                else:
                    logger.error(f"Slack returned status {response.status}")
                    return False
        except urllib.error.URLError as error:
            logger.error(f"Failed to send Slack notification: {error}")
            return False
        except Exception as error:
            logger.error(f"Unexpected error sending to Slack: {error}")
            return False

    def send_alert(
        self,
        title: str,
        message: str,
        severity: str = "warning",
        fields: Optional[List[Dict[str, str]]] = None
    ) -> bool:
        """
        Send a security alert to Slack.

        Args:
            title: Alert title
            message: Alert message
            severity: One of "critical", "warning", "info"
            fields: Optional list of field dicts with "title" and "value"

        Returns:
            True if sent successfully
        """
        # Color based on severity
        colors = {
            "critical": "#dc3545",  # Red
            "warning": "#ffc107",   # Yellow
            "info": "#17a2b8",      # Blue
        }
        color = colors.get(severity, colors["info"])

        # Emoji based on severity
        emojis = {
            "critical": ":rotating_light:",
            "warning": ":warning:",
            "info": ":information_source:",
        }
        emoji = emojis.get(severity, ":bell:")

        # Build attachment
        attachment = {
            "color": color,
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"{emoji} {title}",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": message
                    }
                }
            ]
        }

        # Add fields if provided
        if fields:
            field_elements = []
            for field in fields:
                field_elements.append({
                    "type": "mrkdwn",
                    "text": f"*{field['title']}*\n{field['value']}"
                })
            attachment["blocks"].append({
                "type": "section",
                "fields": field_elements
            })

        # Add timestamp footer
        attachment["blocks"].append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"🏠 Smarthome Security | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                }
            ]
        })

        payload = {"attachments": [attachment]}

        # Log the alert regardless of Slack status
        logger.log(
            logging.CRITICAL if severity == "critical" else logging.WARNING,
            f"Security Alert [{severity.upper()}]: {title} - {message}"
        )

        return self._send(payload)

    def send_weekly_report(self, report_data: Dict[str, Any]) -> bool:
        """
        Send weekly security report to Slack.

        Args:
            report_data: Dictionary containing report sections

        Returns:
            True if sent successfully
        """
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "📊 Weekly Security Report",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Report Period:* {report_data.get('period', 'Last 7 days')}"
                }
            },
            {"type": "divider"}
        ]

        # Summary section
        summary = report_data.get("summary", {})
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*📈 Summary*"
            }
        })
        blocks.append({
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Total Alerts:*\n{summary.get('total_alerts', 0)}"},
                {"type": "mrkdwn", "text": f"*Critical:*\n{summary.get('critical_alerts', 0)}"},
                {"type": "mrkdwn", "text": f"*API Cost:*\n${summary.get('total_api_cost', 0):.2f}"},
                {"type": "mrkdwn", "text": f"*Failed SSH:*\n{summary.get('failed_ssh_attempts', 0)}"},
            ]
        })

        blocks.append({"type": "divider"})

        # Services section
        services = report_data.get("services", {})
        service_status = []
        for service, status in services.items():
            icon = "✅" if status == "running" else "❌"
            service_status.append(f"{icon} {service}: {status}")

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*🔧 Service Status*\n" + "\n".join(service_status) if service_status else "*🔧 Service Status*\nNo services monitored"
            }
        })

        blocks.append({"type": "divider"})

        # Recommendations section
        recommendations = report_data.get("recommendations", [])
        if recommendations:
            rec_text = "\n".join([f"• {rec}" for rec in recommendations])
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*💡 Recommendations*\n{rec_text}"
                }
            })

        # Footer
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"🏠 Smarthome Security | Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                }
            ]
        })

        payload = {"blocks": blocks}

        logger.info("Sending weekly security report to Slack")
        return self._send(payload)

    def test_connection(self) -> bool:
        """
        Test Slack webhook connectivity.

        Returns:
            True if webhook is working
        """
        return self.send_alert(
            title="Connection Test",
            message="Security monitoring is connected and working!",
            severity="info"
        )
