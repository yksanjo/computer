"""
Waste detection rules and alert types.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from computer.connect.base import GPUInstance, GPUType


class WasteType(str, Enum):
    """Types of GPU waste."""
    IDLE_GPU = "idle_gpu"
    LOW_UTILIZATION = "low_utilization"
    OVERSIZED_INSTANCE = "oversized_instance"
    SPOT_OPPORTUNITY = "spot_opportunity"
    STOPPED_WITH_STORAGE = "stopped_with_storage"
    WRONG_REGION = "wrong_region"
    REDUNDANT_INSTANCE = "redundant_instance"
    LONG_RUNNING_SPOT = "long_running_spot"


class Severity(str, Enum):
    """Alert severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class WasteAlert:
    """A waste detection alert."""
    waste_type: WasteType
    severity: Severity
    instance: GPUInstance
    message: str
    estimated_waste_per_day: float
    recommendation: str
    detected_at: datetime

    @property
    def monthly_waste(self) -> float:
        return self.estimated_waste_per_day * 30

    def to_dict(self) -> dict:
        return {
            "type": self.waste_type.value,
            "severity": self.severity.value,
            "instance_id": self.instance.instance_id,
            "provider": self.instance.provider,
            "gpu_type": self.instance.gpu_type.value,
            "message": self.message,
            "waste_per_day": round(self.estimated_waste_per_day, 2),
            "waste_per_month": round(self.monthly_waste, 2),
            "recommendation": self.recommendation,
            "detected_at": self.detected_at.isoformat(),
        }


@dataclass
class WasteRule:
    """A rule for detecting waste."""
    waste_type: WasteType
    name: str
    description: str
    threshold: float  # Rule-specific threshold
    enabled: bool = True

    def evaluate(self, instance: GPUInstance) -> Optional[WasteAlert]:
        """Evaluate the rule against an instance. Override in subclasses."""
        raise NotImplementedError


class IdleGPURule(WasteRule):
    """Detect completely idle GPUs (<5% utilization)."""

    def __init__(self, threshold: float = 5.0):
        super().__init__(
            waste_type=WasteType.IDLE_GPU,
            name="Idle GPU Detection",
            description="Detect GPUs with near-zero utilization",
            threshold=threshold,
        )

    def evaluate(self, instance: GPUInstance) -> Optional[WasteAlert]:
        if not instance.is_running:
            return None

        if instance.gpu_utilization is None:
            return None

        if instance.gpu_utilization < self.threshold:
            waste_per_day = instance.hourly_cost * 24

            severity = Severity.HIGH if instance.hourly_cost > 5 else Severity.MEDIUM

            return WasteAlert(
                waste_type=self.waste_type,
                severity=severity,
                instance=instance,
                message=f"GPU utilization is only {instance.gpu_utilization:.1f}% (threshold: {self.threshold}%)",
                estimated_waste_per_day=waste_per_day,
                recommendation=f"Consider stopping this instance. Estimated savings: ${waste_per_day * 30:.2f}/month",
                detected_at=datetime.now(),
            )

        return None


class LowUtilizationRule(WasteRule):
    """Detect underutilized GPUs (5-30% utilization)."""

    def __init__(self, threshold: float = 30.0):
        super().__init__(
            waste_type=WasteType.LOW_UTILIZATION,
            name="Low Utilization Detection",
            description="Detect GPUs with low but non-zero utilization",
            threshold=threshold,
        )

    def evaluate(self, instance: GPUInstance) -> Optional[WasteAlert]:
        if not instance.is_running:
            return None

        if instance.gpu_utilization is None:
            return None

        # Only trigger if above idle threshold but below this threshold
        if 5.0 <= instance.gpu_utilization < self.threshold:
            # Estimate waste as the unused capacity cost
            utilization_ratio = instance.gpu_utilization / 100
            waste_ratio = 1 - utilization_ratio
            waste_per_day = instance.hourly_cost * 24 * waste_ratio * 0.5  # Conservative

            return WasteAlert(
                waste_type=self.waste_type,
                severity=Severity.MEDIUM,
                instance=instance,
                message=f"GPU utilization is only {instance.gpu_utilization:.1f}%",
                estimated_waste_per_day=waste_per_day,
                recommendation="Consider batching workloads or downsizing to a smaller instance",
                detected_at=datetime.now(),
            )

        return None


class SpotOpportunityRule(WasteRule):
    """Detect on-demand instances that could use spot pricing."""

    def __init__(self, spot_discount: float = 0.6):
        super().__init__(
            waste_type=WasteType.SPOT_OPPORTUNITY,
            name="Spot Pricing Opportunity",
            description="Detect on-demand instances suitable for spot pricing",
            threshold=spot_discount,
        )

    def evaluate(self, instance: GPUInstance) -> Optional[WasteAlert]:
        from computer.connect.base import PricingType

        if not instance.is_running:
            return None

        if instance.pricing_type != PricingType.ON_DEMAND:
            return None

        # Skip very expensive instances (might be critical workloads)
        if instance.hourly_cost > 50:
            return None

        potential_savings_per_day = instance.hourly_cost * 24 * self.threshold

        return WasteAlert(
            waste_type=self.waste_type,
            severity=Severity.LOW,
            instance=instance,
            message=f"Running on-demand at ${instance.hourly_cost:.2f}/hr. Spot could save ~{self.threshold*100:.0f}%",
            estimated_waste_per_day=potential_savings_per_day,
            recommendation=f"Switch to spot/preemptible pricing. Potential savings: ${potential_savings_per_day * 30:.2f}/month",
            detected_at=datetime.now(),
        )


class OversizedInstanceRule(WasteRule):
    """Detect instances that might be oversized for their workload."""

    def __init__(self, memory_threshold: float = 30.0):
        super().__init__(
            waste_type=WasteType.OVERSIZED_INSTANCE,
            name="Oversized Instance Detection",
            description="Detect instances where GPU memory utilization is very low",
            threshold=memory_threshold,
        )

    def evaluate(self, instance: GPUInstance) -> Optional[WasteAlert]:
        if not instance.is_running:
            return None

        if instance.memory_utilization is None:
            return None

        if instance.memory_utilization < self.threshold:
            # Suggest downgrade based on GPU type
            downgrade_suggestions = {
                GPUType.A100_80GB: GPUType.A100_40GB,
                GPUType.H100_80GB: GPUType.A100_80GB,
                GPUType.RTX_4090: GPUType.RTX_4080,
            }

            suggestion = downgrade_suggestions.get(instance.gpu_type)
            if suggestion:
                # Estimate savings (rough)
                waste_per_day = instance.hourly_cost * 24 * 0.3  # ~30% savings

                return WasteAlert(
                    waste_type=self.waste_type,
                    severity=Severity.MEDIUM,
                    instance=instance,
                    message=f"GPU memory utilization is only {instance.memory_utilization:.1f}%",
                    estimated_waste_per_day=waste_per_day,
                    recommendation=f"Consider downgrading to {suggestion.value} for ~30% cost savings",
                    detected_at=datetime.now(),
                )

        return None


# Default rules
DEFAULT_RULES = [
    IdleGPURule(),
    LowUtilizationRule(),
    SpotOpportunityRule(),
    OversizedInstanceRule(),
]
