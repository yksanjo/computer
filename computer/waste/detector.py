"""
Waste Detector - Find inefficiencies in GPU usage.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from computer.connect.base import GPUInstance
from computer.see.aggregator import SpendAggregator
from computer.waste.rules import (
    DEFAULT_RULES,
    WasteAlert,
    WasteRule,
    WasteType,
    Severity,
)


@dataclass
class WasteReport:
    """Complete waste analysis report."""
    generated_at: datetime
    total_instances_analyzed: int
    alerts: list[WasteAlert] = field(default_factory=list)

    @property
    def total_daily_waste(self) -> float:
        return sum(a.estimated_waste_per_day for a in self.alerts)

    @property
    def total_monthly_waste(self) -> float:
        return self.total_daily_waste * 30

    @property
    def critical_alerts(self) -> list[WasteAlert]:
        return [a for a in self.alerts if a.severity == Severity.CRITICAL]

    @property
    def high_alerts(self) -> list[WasteAlert]:
        return [a for a in self.alerts if a.severity == Severity.HIGH]

    @property
    def by_type(self) -> dict[WasteType, list[WasteAlert]]:
        result = {}
        for alert in self.alerts:
            if alert.waste_type not in result:
                result[alert.waste_type] = []
            result[alert.waste_type].append(alert)
        return result

    @property
    def by_provider(self) -> dict[str, list[WasteAlert]]:
        result = {}
        for alert in self.alerts:
            provider = alert.instance.provider
            if provider not in result:
                result[provider] = []
            result[provider].append(alert)
        return result

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at.isoformat(),
            "summary": {
                "instances_analyzed": self.total_instances_analyzed,
                "total_alerts": len(self.alerts),
                "critical_alerts": len(self.critical_alerts),
                "high_alerts": len(self.high_alerts),
                "daily_waste": round(self.total_daily_waste, 2),
                "monthly_waste": round(self.total_monthly_waste, 2),
            },
            "by_type": {
                waste_type.value: {
                    "count": len(alerts),
                    "daily_waste": round(sum(a.estimated_waste_per_day for a in alerts), 2),
                }
                for waste_type, alerts in self.by_type.items()
            },
            "alerts": [a.to_dict() for a in self.alerts],
        }


class WasteDetector:
    """Detects waste and inefficiencies in GPU usage."""

    def __init__(
        self,
        aggregator: Optional[SpendAggregator] = None,
        rules: Optional[list[WasteRule]] = None,
    ):
        self.aggregator = aggregator or SpendAggregator()
        self.rules = rules or DEFAULT_RULES.copy()

    def add_rule(self, rule: WasteRule) -> None:
        """Add a custom waste detection rule."""
        self.rules.append(rule)

    def remove_rule(self, waste_type: WasteType) -> None:
        """Remove rules of a specific type."""
        self.rules = [r for r in self.rules if r.waste_type != waste_type]

    def enable_rule(self, waste_type: WasteType) -> None:
        """Enable a rule type."""
        for rule in self.rules:
            if rule.waste_type == waste_type:
                rule.enabled = True

    def disable_rule(self, waste_type: WasteType) -> None:
        """Disable a rule type."""
        for rule in self.rules:
            if rule.waste_type == waste_type:
                rule.enabled = False

    def analyze_instance(self, instance: GPUInstance) -> list[WasteAlert]:
        """Run all rules against a single instance."""
        alerts = []

        for rule in self.rules:
            if not rule.enabled:
                continue

            try:
                alert = rule.evaluate(instance)
                if alert:
                    alerts.append(alert)
            except Exception as e:
                print(f"Error evaluating rule {rule.name}: {e}")

        return alerts

    def analyze(self, instances: Optional[list[GPUInstance]] = None) -> WasteReport:
        """
        Analyze all instances for waste.

        If instances not provided, fetches from aggregator.
        """
        if instances is None:
            instances = self.aggregator.get_all_instances()

        all_alerts = []

        for instance in instances:
            alerts = self.analyze_instance(instance)
            all_alerts.extend(alerts)

        # Sort by severity and waste amount
        severity_order = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 1,
            Severity.MEDIUM: 2,
            Severity.LOW: 3,
        }

        all_alerts.sort(
            key=lambda a: (severity_order[a.severity], -a.estimated_waste_per_day)
        )

        return WasteReport(
            generated_at=datetime.now(),
            total_instances_analyzed=len(instances),
            alerts=all_alerts,
        )

    def get_quick_wins(self, min_savings: float = 100.0) -> list[WasteAlert]:
        """
        Get high-impact, easy-to-fix waste alerts.

        Returns alerts sorted by potential monthly savings.
        """
        report = self.analyze()

        # Filter for actionable alerts with significant savings
        quick_wins = [
            a for a in report.alerts
            if a.monthly_waste >= min_savings
            and a.waste_type in (
                WasteType.IDLE_GPU,
                WasteType.SPOT_OPPORTUNITY,
            )
        ]

        # Sort by monthly savings descending
        quick_wins.sort(key=lambda a: -a.monthly_waste)

        return quick_wins

    def estimate_total_savings(self) -> dict:
        """Estimate total potential savings."""
        report = self.analyze()

        return {
            "daily_waste": report.total_daily_waste,
            "monthly_waste": report.total_monthly_waste,
            "annual_waste": report.total_monthly_waste * 12,
            "by_type": {
                waste_type.value: sum(a.monthly_waste for a in alerts)
                for waste_type, alerts in report.by_type.items()
            },
            "actionable_now": sum(
                a.monthly_waste for a in report.alerts
                if a.severity in (Severity.HIGH, Severity.CRITICAL)
            ),
        }
