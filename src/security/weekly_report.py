"""
Weekly Security Report Generator

Generates comprehensive weekly security reports and sends them to Slack.
"""

import json
import logging
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

from src.security.config import ALERT_HISTORY_FILE, STATE_DIR
from src.security.slack_client import SlackNotifier
from src.security.monitors import SSHMonitor, APICostMonitor, ServiceMonitor

logger = logging.getLogger("security.weekly_report")


class WeeklySecurityReport:
    """Generate and send weekly security reports."""

    def __init__(self, webhook_url: Optional[str] = None):
        self.notifier = SlackNotifier(webhook_url)
        self.ssh_monitor = SSHMonitor(self.notifier)
        self.cost_monitor = APICostMonitor(self.notifier)
        self.service_monitor = ServiceMonitor(self.notifier)

    def _load_alert_history(self) -> List[Dict[str, Any]]:
        """Load alert history from file."""
        if ALERT_HISTORY_FILE.exists():
            try:
                with open(ALERT_HISTORY_FILE, "r") as file:
                    data = json.load(file)
                    return data.get("alerts", [])
            except (json.JSONDecodeError, IOError):
                pass
        return []

    def _get_alerts_in_period(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get alerts from the past N days."""
        alerts = self._load_alert_history()
        cutoff = datetime.now() - timedelta(days=days)

        return [
            alert for alert in alerts
            if datetime.fromisoformat(alert["timestamp"]) > cutoff
        ]

    def _count_alerts_by_type(self, alerts: List[Dict[str, Any]]) -> Dict[str, int]:
        """Count alerts by type."""
        counts = {}
        for alert in alerts:
            alert_type = alert.get("type", "unknown")
            counts[alert_type] = counts.get(alert_type, 0) + 1
        return counts

    def _run_security_scans(self) -> Dict[str, Any]:
        """Run security scans and return results."""
        results = {
            "bandit": {"status": "not_run", "issues": []},
            "pip_audit": {"status": "not_run", "vulnerabilities": []},
            "system_updates": {"status": "not_run", "updates_available": 0},
        }

        # Check for available system updates
        try:
            result = subprocess.run(
                ["apt", "list", "--upgradable"],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                # Count lines (excluding header)
                lines = [line for line in result.stdout.strip().split("\n") if line and "Listing" not in line]
                results["system_updates"] = {
                    "status": "success",
                    "updates_available": len(lines),
                    "packages": lines[:5],  # First 5 packages
                }
        except Exception as error:
            results["system_updates"]["error"] = str(error)

        # Run pip-audit if available
        try:
            result = subprocess.run(
                ["pip-audit", "--format", "json"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=Path(__file__).parent.parent.parent
            )
            if result.returncode == 0:
                vulnerabilities = json.loads(result.stdout) if result.stdout else []
                results["pip_audit"] = {
                    "status": "success",
                    "vulnerabilities": vulnerabilities,
                    "count": len(vulnerabilities),
                }
            else:
                results["pip_audit"]["status"] = "issues_found"
                results["pip_audit"]["output"] = result.stderr[:500]
        except FileNotFoundError:
            results["pip_audit"]["status"] = "not_installed"
        except Exception as error:
            results["pip_audit"]["error"] = str(error)

        return results

    def _generate_recommendations(
        self,
        alerts: List[Dict[str, Any]],
        scans: Dict[str, Any],
        services: Dict[str, str]
    ) -> List[str]:
        """Generate security recommendations based on data."""
        recommendations = []

        # Alert-based recommendations
        alert_counts = self._count_alerts_by_type(alerts)

        if alert_counts.get("ssh_failed", 0) > 5:
            recommendations.append("Consider adding fail2ban rules or geo-blocking for SSH")

        if alert_counts.get("api_cost", 0) > 3:
            recommendations.append("Review API usage patterns - costs exceeded threshold multiple times")

        if alert_counts.get("service_down", 0) > 0:
            recommendations.append("Review service stability - services went down this week")

        # Scan-based recommendations
        if scans.get("system_updates", {}).get("updates_available", 0) > 0:
            count = scans["system_updates"]["updates_available"]
            recommendations.append(f"Install {count} pending system updates")

        if scans.get("pip_audit", {}).get("count", 0) > 0:
            count = scans["pip_audit"]["count"]
            recommendations.append(f"Address {count} Python dependency vulnerabilities")

        # Service-based recommendations
        for service, status in services.items():
            if status not in ("active", "running"):
                recommendations.append(f"Investigate {service} service status: {status}")

        # Default recommendation if nothing else
        if not recommendations:
            recommendations.append("No immediate security concerns identified")

        return recommendations

    def generate_report(self, days: int = 7) -> Dict[str, Any]:
        """
        Generate a comprehensive weekly security report.

        Args:
            days: Number of days to include in report

        Returns:
            Report data dictionary
        """
        logger.info(f"Generating security report for past {days} days")

        # Collect data
        alerts = self._get_alerts_in_period(days)
        alert_counts = self._count_alerts_by_type(alerts)
        ssh_stats = self.ssh_monitor.get_stats(days)
        cost_stats = self.cost_monitor.get_stats(days)
        services = self.service_monitor.get_status()
        scans = self._run_security_scans()

        # Calculate summary
        total_api_cost = cost_stats.get("total_cost", 0)
        total_alerts = len(alerts)
        critical_alerts = alert_counts.get("ssh_failed", 0) + alert_counts.get("service_down", 0)

        # Generate recommendations
        recommendations = self._generate_recommendations(alerts, scans, services)

        # Build report
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        report = {
            "period": f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_alerts": total_alerts,
                "critical_alerts": critical_alerts,
                "total_api_cost": total_api_cost,
                "failed_ssh_attempts": ssh_stats.get("recent_failed_attempts", 0) + ssh_stats.get("historical_alerts", 0),
            },
            "alerts_by_type": alert_counts,
            "services": services,
            "scans": scans,
            "recommendations": recommendations,
            "details": {
                "ssh_stats": ssh_stats,
                "cost_stats": cost_stats,
            }
        }

        # Save report to file
        report_file = STATE_DIR / f"weekly_report_{end_date.strftime('%Y-%m-%d')}.json"
        with open(report_file, "w") as file:
            json.dump(report, file, indent=2)
        logger.info(f"Report saved to {report_file}")

        return report

    def send_report(self, days: int = 7) -> bool:
        """
        Generate and send weekly security report to Slack.

        Args:
            days: Number of days to include

        Returns:
            True if report was sent successfully
        """
        report = self.generate_report(days)
        return self.notifier.send_weekly_report(report)


def main():
    """CLI entry point for generating weekly reports."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate and send weekly security report")
    parser.add_argument("--days", type=int, default=7, help="Number of days to include")
    parser.add_argument("--dry-run", action="store_true", help="Generate report without sending")
    parser.add_argument("--webhook", type=str, help="Override Slack webhook URL")
    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )

    reporter = WeeklySecurityReport(webhook_url=args.webhook)

    if args.dry_run:
        report = reporter.generate_report(args.days)
        print(json.dumps(report, indent=2))
    else:
        success = reporter.send_report(args.days)
        if success:
            print("Weekly report sent successfully")
        else:
            print("Failed to send weekly report (check if SLACK_SECURITY_WEBHOOK is set)")
            exit(1)


if __name__ == "__main__":
    main()
