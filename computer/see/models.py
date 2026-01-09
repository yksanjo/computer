"""
Data models for spend aggregation.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from computer.connect.base import GPUType, PricingType


@dataclass
class ProviderBreakdown:
    """Spend breakdown by provider."""
    provider: str
    total_cost: float
    total_hours: float
    instance_count: int
    running_count: int
    idle_count: int

    @property
    def avg_hourly_rate(self) -> float:
        if self.total_hours > 0:
            return self.total_cost / self.total_hours
        return 0.0

    @property
    def idle_percentage(self) -> float:
        if self.running_count > 0:
            return (self.idle_count / self.running_count) * 100
        return 0.0


@dataclass
class GPUBreakdown:
    """Spend breakdown by GPU type."""
    gpu_type: GPUType
    total_cost: float
    total_hours: float
    gpu_count: int
    avg_utilization: Optional[float] = None

    @property
    def cost_per_gpu_hour(self) -> float:
        if self.total_hours > 0 and self.gpu_count > 0:
            return self.total_cost / (self.total_hours * self.gpu_count)
        return 0.0


@dataclass
class RegionBreakdown:
    """Spend breakdown by region."""
    region: str
    provider: str
    total_cost: float
    instance_count: int


@dataclass
class PricingBreakdown:
    """Spend breakdown by pricing type."""
    pricing_type: PricingType
    total_cost: float
    total_hours: float
    instance_count: int

    @property
    def potential_savings(self) -> float:
        """Estimate savings if switched to spot."""
        if self.pricing_type == PricingType.ON_DEMAND:
            return self.total_cost * 0.6  # ~60% savings with spot
        return 0.0


@dataclass
class SpendSummary:
    """Complete spend summary across all providers."""
    start_date: datetime
    end_date: datetime
    total_cost: float
    total_gpu_hours: float
    total_instances: int
    running_instances: int
    idle_instances: int

    by_provider: list[ProviderBreakdown] = field(default_factory=list)
    by_gpu_type: list[GPUBreakdown] = field(default_factory=list)
    by_region: list[RegionBreakdown] = field(default_factory=list)
    by_pricing: list[PricingBreakdown] = field(default_factory=list)

    # Calculated metrics
    avg_gpu_utilization: Optional[float] = None
    estimated_waste: float = 0.0
    potential_savings: float = 0.0

    @property
    def avg_cost_per_gpu_hour(self) -> float:
        if self.total_gpu_hours > 0:
            return self.total_cost / self.total_gpu_hours
        return 0.0

    @property
    def idle_percentage(self) -> float:
        if self.running_instances > 0:
            return (self.idle_instances / self.running_instances) * 100
        return 0.0

    @property
    def daily_run_rate(self) -> float:
        """Estimated daily spend based on current data."""
        days = (self.end_date - self.start_date).days
        if days > 0:
            return self.total_cost / days
        return self.total_cost

    @property
    def monthly_projection(self) -> float:
        """Projected monthly spend."""
        return self.daily_run_rate * 30

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "period": {
                "start": self.start_date.isoformat(),
                "end": self.end_date.isoformat(),
            },
            "totals": {
                "cost": round(self.total_cost, 2),
                "gpu_hours": round(self.total_gpu_hours, 2),
                "instances": self.total_instances,
                "running": self.running_instances,
                "idle": self.idle_instances,
            },
            "metrics": {
                "avg_cost_per_gpu_hour": round(self.avg_cost_per_gpu_hour, 4),
                "idle_percentage": round(self.idle_percentage, 1),
                "avg_gpu_utilization": round(self.avg_gpu_utilization, 1) if self.avg_gpu_utilization else None,
                "estimated_waste": round(self.estimated_waste, 2),
                "potential_savings": round(self.potential_savings, 2),
            },
            "projections": {
                "daily_run_rate": round(self.daily_run_rate, 2),
                "monthly_projection": round(self.monthly_projection, 2),
            },
            "by_provider": [
                {
                    "provider": p.provider,
                    "cost": round(p.total_cost, 2),
                    "hours": round(p.total_hours, 2),
                    "instances": p.instance_count,
                    "running": p.running_count,
                    "idle": p.idle_count,
                }
                for p in self.by_provider
            ],
            "by_gpu_type": [
                {
                    "gpu_type": g.gpu_type.value,
                    "cost": round(g.total_cost, 2),
                    "hours": round(g.total_hours, 2),
                    "gpu_count": g.gpu_count,
                    "cost_per_gpu_hour": round(g.cost_per_gpu_hour, 4),
                }
                for g in self.by_gpu_type
            ],
            "by_pricing": [
                {
                    "type": p.pricing_type.value,
                    "cost": round(p.total_cost, 2),
                    "hours": round(p.total_hours, 2),
                    "potential_savings": round(p.potential_savings, 2),
                }
                for p in self.by_pricing
            ],
        }
