"""
Recommender - Generate optimization recommendations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from computer.connect.base import GPUInstance, GPUType, PricingType
from computer.see.aggregator import SpendAggregator
from computer.waste.detector import WasteDetector, WasteReport


class RecommendationType(str, Enum):
    """Types of optimization recommendations."""
    TERMINATE_IDLE = "terminate_idle"
    SWITCH_TO_SPOT = "switch_to_spot"
    DOWNSIZE_INSTANCE = "downsize_instance"
    CHANGE_REGION = "change_region"
    CHANGE_PROVIDER = "change_provider"
    SCHEDULE_SHUTDOWN = "schedule_shutdown"
    USE_RESERVED = "use_reserved"
    BATCH_WORKLOADS = "batch_workloads"


class Priority(str, Enum):
    """Recommendation priority."""
    CRITICAL = "critical"  # Do this now
    HIGH = "high"  # Do this week
    MEDIUM = "medium"  # Do this month
    LOW = "low"  # Nice to have


@dataclass
class Recommendation:
    """A single optimization recommendation."""
    rec_type: RecommendationType
    priority: Priority
    title: str
    description: str
    monthly_savings: float
    effort: str  # "low", "medium", "high"
    instance_id: Optional[str] = None
    provider: Optional[str] = None
    action_steps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "type": self.rec_type.value,
            "priority": self.priority.value,
            "title": self.title,
            "description": self.description,
            "monthly_savings": round(self.monthly_savings, 2),
            "effort": self.effort,
            "instance_id": self.instance_id,
            "provider": self.provider,
            "action_steps": self.action_steps,
        }


@dataclass
class OptimizationReport:
    """Complete optimization report."""
    generated_at: datetime
    recommendations: list[Recommendation] = field(default_factory=list)

    @property
    def total_monthly_savings(self) -> float:
        return sum(r.monthly_savings for r in self.recommendations)

    @property
    def quick_wins(self) -> list[Recommendation]:
        """Low effort, high savings recommendations."""
        return [
            r for r in self.recommendations
            if r.effort == "low" and r.monthly_savings > 50
        ]

    @property
    def by_priority(self) -> dict[Priority, list[Recommendation]]:
        result = {}
        for rec in self.recommendations:
            if rec.priority not in result:
                result[rec.priority] = []
            result[rec.priority].append(rec)
        return result

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at.isoformat(),
            "summary": {
                "total_recommendations": len(self.recommendations),
                "total_monthly_savings": round(self.total_monthly_savings, 2),
                "quick_wins_count": len(self.quick_wins),
                "quick_wins_savings": round(
                    sum(r.monthly_savings for r in self.quick_wins), 2
                ),
            },
            "by_priority": {
                priority.value: {
                    "count": len(recs),
                    "savings": round(sum(r.monthly_savings for r in recs), 2),
                }
                for priority, recs in self.by_priority.items()
            },
            "recommendations": [r.to_dict() for r in self.recommendations],
        }


class Recommender:
    """Generates optimization recommendations."""

    # Provider spot discounts
    SPOT_DISCOUNTS = {
        "aws": 0.65,
        "gcp": 0.70,
        "azure": 0.60,
    }

    # Cheaper alternatives by GPU type
    CHEAPER_ALTERNATIVES = {
        GPUType.A100_80GB: [
            ("lambda", GPUType.A100_80GB, 1.29),
            ("runpod", GPUType.A100_80GB, 1.49),
            ("vastai", GPUType.A100_80GB, 1.50),
        ],
        GPUType.H100_80GB: [
            ("lambda", GPUType.H100_80GB, 1.99),
            ("runpod", GPUType.H100_80GB, 2.39),
            ("vastai", GPUType.H100_80GB, 2.50),
        ],
        GPUType.RTX_4090: [
            ("runpod", GPUType.RTX_4090, 0.44),
            ("vastai", GPUType.RTX_4090, 0.45),
        ],
    }

    def __init__(
        self,
        aggregator: Optional[SpendAggregator] = None,
        waste_detector: Optional[WasteDetector] = None,
    ):
        self.aggregator = aggregator or SpendAggregator()
        self.waste_detector = waste_detector or WasteDetector(self.aggregator)

    def generate_recommendations(self) -> OptimizationReport:
        """Generate all optimization recommendations."""
        recommendations = []

        # Get current state
        instances = self.aggregator.get_all_instances()
        waste_report = self.waste_detector.analyze(instances)

        # Generate recommendations from each source
        recommendations.extend(self._from_waste_report(waste_report))
        recommendations.extend(self._spot_opportunities(instances))
        recommendations.extend(self._provider_alternatives(instances))
        recommendations.extend(self._scheduling_opportunities(instances))

        # Sort by priority and savings
        priority_order = {
            Priority.CRITICAL: 0,
            Priority.HIGH: 1,
            Priority.MEDIUM: 2,
            Priority.LOW: 3,
        }
        recommendations.sort(
            key=lambda r: (priority_order[r.priority], -r.monthly_savings)
        )

        # Remove duplicates (same instance, similar recommendation)
        seen = set()
        unique_recs = []
        for rec in recommendations:
            key = (rec.instance_id, rec.rec_type)
            if key not in seen:
                seen.add(key)
                unique_recs.append(rec)

        return OptimizationReport(
            generated_at=datetime.now(),
            recommendations=unique_recs,
        )

    def _from_waste_report(
        self,
        report: WasteReport
    ) -> list[Recommendation]:
        """Convert waste alerts to recommendations."""
        recommendations = []

        for alert in report.alerts:
            if alert.waste_type.value == "idle_gpu":
                recommendations.append(Recommendation(
                    rec_type=RecommendationType.TERMINATE_IDLE,
                    priority=Priority.CRITICAL if alert.monthly_waste > 500 else Priority.HIGH,
                    title=f"Terminate idle {alert.instance.gpu_type.value}",
                    description=alert.message,
                    monthly_savings=alert.monthly_waste,
                    effort="low",
                    instance_id=alert.instance.instance_id,
                    provider=alert.instance.provider,
                    action_steps=[
                        f"Verify instance {alert.instance.instance_id} is not needed",
                        "Export any data if required",
                        f"Terminate instance via {alert.instance.provider} console",
                    ],
                ))

            elif alert.waste_type.value == "spot_opportunity":
                recommendations.append(Recommendation(
                    rec_type=RecommendationType.SWITCH_TO_SPOT,
                    priority=Priority.MEDIUM,
                    title=f"Switch to spot pricing",
                    description=alert.message,
                    monthly_savings=alert.monthly_waste,
                    effort="medium",
                    instance_id=alert.instance.instance_id,
                    provider=alert.instance.provider,
                    action_steps=[
                        "Review workload fault tolerance",
                        "Set up checkpointing for long-running jobs",
                        f"Migrate to spot instance on {alert.instance.provider}",
                    ],
                ))

            elif alert.waste_type.value == "oversized_instance":
                recommendations.append(Recommendation(
                    rec_type=RecommendationType.DOWNSIZE_INSTANCE,
                    priority=Priority.MEDIUM,
                    title=f"Downsize {alert.instance.gpu_type.value}",
                    description=alert.message,
                    monthly_savings=alert.monthly_waste,
                    effort="medium",
                    instance_id=alert.instance.instance_id,
                    provider=alert.instance.provider,
                    action_steps=[
                        "Profile actual memory usage",
                        "Test workload on smaller instance",
                        "Migrate to downsized instance",
                    ],
                ))

        return recommendations

    def _spot_opportunities(
        self,
        instances: list[GPUInstance]
    ) -> list[Recommendation]:
        """Find spot pricing opportunities."""
        recommendations = []

        for instance in instances:
            if not instance.is_running:
                continue

            if instance.pricing_type != PricingType.ON_DEMAND:
                continue

            discount = self.SPOT_DISCOUNTS.get(instance.provider, 0.5)
            monthly_savings = instance.hourly_cost * 24 * 30 * discount

            if monthly_savings > 50:  # Only recommend if significant
                recommendations.append(Recommendation(
                    rec_type=RecommendationType.SWITCH_TO_SPOT,
                    priority=Priority.MEDIUM,
                    title=f"Switch {instance.instance_type} to spot",
                    description=(
                        f"Running on-demand at ${instance.hourly_cost:.2f}/hr. "
                        f"Spot pricing could save ~{discount*100:.0f}%"
                    ),
                    monthly_savings=monthly_savings,
                    effort="medium",
                    instance_id=instance.instance_id,
                    provider=instance.provider,
                    action_steps=[
                        "Verify workload can handle interruptions",
                        "Implement checkpointing if needed",
                        "Request spot instance with same configuration",
                        "Migrate workload and terminate on-demand instance",
                    ],
                ))

        return recommendations

    def _provider_alternatives(
        self,
        instances: list[GPUInstance]
    ) -> list[Recommendation]:
        """Find cheaper provider alternatives."""
        recommendations = []

        for instance in instances:
            if not instance.is_running:
                continue

            alternatives = self.CHEAPER_ALTERNATIVES.get(instance.gpu_type, [])

            for provider, gpu_type, rate in alternatives:
                if provider == instance.provider:
                    continue

                current_monthly = instance.hourly_cost * 24 * 30
                alternative_monthly = rate * instance.gpu_count * 24 * 30
                savings = current_monthly - alternative_monthly

                if savings > 100:  # Significant savings only
                    recommendations.append(Recommendation(
                        rec_type=RecommendationType.CHANGE_PROVIDER,
                        priority=Priority.LOW,
                        title=f"Move to {provider}",
                        description=(
                            f"Current: ${instance.hourly_cost:.2f}/hr on {instance.provider}. "
                            f"Alternative: ${rate:.2f}/hr on {provider}"
                        ),
                        monthly_savings=savings,
                        effort="high",
                        instance_id=instance.instance_id,
                        provider=instance.provider,
                        action_steps=[
                            f"Create account on {provider} if needed",
                            "Verify feature parity (networking, storage, etc.)",
                            "Test workload on new provider",
                            "Migrate data and configurations",
                            "Switch over and terminate old instance",
                        ],
                    ))
                    break  # Only suggest best alternative

        return recommendations

    def _scheduling_opportunities(
        self,
        instances: list[GPUInstance]
    ) -> list[Recommendation]:
        """Find scheduling optimization opportunities."""
        recommendations = []

        # Group instances by purpose (using tags if available)
        dev_instances = [
            i for i in instances
            if i.is_running and any(
                tag in str(i.tags).lower()
                for tag in ["dev", "development", "test", "staging"]
            )
        ]

        for instance in dev_instances:
            # Dev instances could be scheduled
            # Assume 12 hours off per day
            monthly_savings = instance.hourly_cost * 12 * 30

            if monthly_savings > 50:
                recommendations.append(Recommendation(
                    rec_type=RecommendationType.SCHEDULE_SHUTDOWN,
                    priority=Priority.MEDIUM,
                    title=f"Schedule {instance.instance_type} shutdown",
                    description=(
                        f"Development instance running 24/7. "
                        f"Scheduling off-hours shutdown could save ${monthly_savings:.0f}/month"
                    ),
                    monthly_savings=monthly_savings,
                    effort="low",
                    instance_id=instance.instance_id,
                    provider=instance.provider,
                    action_steps=[
                        "Identify usage hours (e.g., 8am-8pm)",
                        f"Set up scheduled shutdown via {instance.provider} or Lambda/Cloud Functions",
                        "Test auto-start and shutdown",
                        "Monitor for a week to verify savings",
                    ],
                ))

        return recommendations

    def get_quick_wins(self, min_savings: float = 100.0) -> list[Recommendation]:
        """Get low-effort, high-impact recommendations."""
        report = self.generate_recommendations()
        return [
            r for r in report.recommendations
            if r.effort == "low" and r.monthly_savings >= min_savings
        ]

    def get_savings_summary(self) -> dict:
        """Get summary of potential savings."""
        report = self.generate_recommendations()

        by_type = {}
        for rec in report.recommendations:
            if rec.rec_type not in by_type:
                by_type[rec.rec_type] = 0
            by_type[rec.rec_type] += rec.monthly_savings

        return {
            "total_monthly_savings": report.total_monthly_savings,
            "total_annual_savings": report.total_monthly_savings * 12,
            "quick_wins": {
                "count": len(report.quick_wins),
                "monthly_savings": sum(r.monthly_savings for r in report.quick_wins),
            },
            "by_type": {k.value: round(v, 2) for k, v in by_type.items()},
            "recommendation_count": len(report.recommendations),
        }
