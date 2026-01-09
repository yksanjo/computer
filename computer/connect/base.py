"""
Base classes for cloud provider connectors.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class GPUType(str, Enum):
    """Standard GPU types across providers."""
    # NVIDIA Datacenter
    A100_40GB = "a100-40gb"
    A100_80GB = "a100-80gb"
    H100_80GB = "h100-80gb"
    H100_SXM = "h100-sxm"
    V100_16GB = "v100-16gb"
    V100_32GB = "v100-32gb"
    A10G = "a10g"
    L4 = "l4"
    L40S = "l40s"
    T4 = "t4"

    # NVIDIA Consumer/Prosumer
    RTX_4090 = "rtx-4090"
    RTX_4080 = "rtx-4080"
    RTX_3090 = "rtx-3090"
    RTX_3080 = "rtx-3080"

    # AMD
    MI250X = "mi250x"
    MI300X = "mi300x"

    UNKNOWN = "unknown"


class PricingType(str, Enum):
    """Pricing models."""
    ON_DEMAND = "on-demand"
    SPOT = "spot"
    RESERVED = "reserved"
    PREEMPTIBLE = "preemptible"


@dataclass
class GPUInstance:
    """Represents a GPU instance across any provider."""
    instance_id: str
    provider: str
    instance_type: str
    gpu_type: GPUType
    gpu_count: int
    region: str
    pricing_type: PricingType
    hourly_cost: float
    status: str  # running, stopped, terminated
    launched_at: Optional[datetime] = None
    tags: dict = field(default_factory=dict)

    # Utilization metrics (if available)
    gpu_utilization: Optional[float] = None  # 0-100%
    memory_utilization: Optional[float] = None  # 0-100%

    @property
    def is_running(self) -> bool:
        return self.status.lower() in ("running", "active")

    @property
    def is_idle(self) -> bool:
        """Consider idle if utilization < 10% for running instances."""
        if not self.is_running:
            return False
        if self.gpu_utilization is not None:
            return self.gpu_utilization < 10.0
        return False


@dataclass
class UsageRecord:
    """Cost and usage record for a time period."""
    instance_id: str
    provider: str
    start_time: datetime
    end_time: datetime
    hours_used: float
    cost: float
    gpu_type: GPUType
    gpu_count: int
    pricing_type: PricingType
    region: str

    @property
    def effective_hourly_rate(self) -> float:
        if self.hours_used > 0:
            return self.cost / self.hours_used
        return 0.0


class BaseConnector(ABC):
    """Base class for all cloud provider connectors."""

    provider_name: str = "base"

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to the provider. Returns True if successful."""
        pass

    @abstractmethod
    def list_gpu_instances(self) -> list[GPUInstance]:
        """List all GPU instances (running and stopped)."""
        pass

    @abstractmethod
    def get_usage(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> list[UsageRecord]:
        """Get usage records for a time period."""
        pass

    @abstractmethod
    def get_current_spend(self) -> float:
        """Get current month's GPU spend."""
        pass

    def get_instance_by_id(self, instance_id: str) -> Optional[GPUInstance]:
        """Get a specific instance by ID."""
        instances = self.list_gpu_instances()
        for instance in instances:
            if instance.instance_id == instance_id:
                return instance
        return None
