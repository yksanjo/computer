"""
Spend Aggregator - Unified view across all providers.
"""

from collections import defaultdict
from datetime import datetime
from typing import Optional

from computer.connect.base import BaseConnector, GPUInstance, GPUType, PricingType, UsageRecord
from computer.see.models import (
    GPUBreakdown,
    PricingBreakdown,
    ProviderBreakdown,
    RegionBreakdown,
    SpendSummary,
)


class SpendAggregator:
    """Aggregates spend data across multiple cloud providers."""

    def __init__(self):
        self.connectors: list[BaseConnector] = []

    def add_connector(self, connector: BaseConnector) -> None:
        """Add a cloud provider connector."""
        self.connectors.append(connector)

    def add_connectors(self, connectors: list[BaseConnector]) -> None:
        """Add multiple connectors."""
        self.connectors.extend(connectors)

    def connect_all(self) -> dict[str, bool]:
        """Connect to all providers. Returns connection status."""
        status = {}
        for connector in self.connectors:
            status[connector.provider_name] = connector.connect()
        return status

    def get_all_instances(self) -> list[GPUInstance]:
        """Get all GPU instances across all providers."""
        instances = []
        for connector in self.connectors:
            try:
                instances.extend(connector.list_gpu_instances())
            except Exception as e:
                print(f"Error getting instances from {connector.provider_name}: {e}")
        return instances

    def get_all_usage(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> list[UsageRecord]:
        """Get all usage records across all providers."""
        records = []
        for connector in self.connectors:
            try:
                records.extend(connector.get_usage(start_date, end_date))
            except Exception as e:
                print(f"Error getting usage from {connector.provider_name}: {e}")
        return records

    def get_summary(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> SpendSummary:
        """
        Generate a comprehensive spend summary.

        If dates not provided, uses current month.
        """
        if end_date is None:
            end_date = datetime.now()
        if start_date is None:
            start_date = end_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Get all data
        instances = self.get_all_instances()
        usage_records = self.get_all_usage(start_date, end_date)

        # Calculate totals
        total_cost = sum(r.cost for r in usage_records)
        total_hours = sum(r.hours_used for r in usage_records)

        running_instances = [i for i in instances if i.is_running]
        idle_instances = [i for i in instances if i.is_idle]

        # Aggregate by provider
        provider_data = defaultdict(lambda: {
            "cost": 0.0,
            "hours": 0.0,
            "instances": set(),
            "running": 0,
            "idle": 0,
        })

        for record in usage_records:
            provider_data[record.provider]["cost"] += record.cost
            provider_data[record.provider]["hours"] += record.hours_used
            provider_data[record.provider]["instances"].add(record.instance_id)

        for instance in instances:
            if instance.is_running:
                provider_data[instance.provider]["running"] += 1
                if instance.is_idle:
                    provider_data[instance.provider]["idle"] += 1

        by_provider = [
            ProviderBreakdown(
                provider=provider,
                total_cost=data["cost"],
                total_hours=data["hours"],
                instance_count=len(data["instances"]),
                running_count=data["running"],
                idle_count=data["idle"],
            )
            for provider, data in provider_data.items()
        ]

        # Aggregate by GPU type
        gpu_data = defaultdict(lambda: {
            "cost": 0.0,
            "hours": 0.0,
            "count": 0,
            "utilizations": [],
        })

        for record in usage_records:
            gpu_data[record.gpu_type]["cost"] += record.cost
            gpu_data[record.gpu_type]["hours"] += record.hours_used
            gpu_data[record.gpu_type]["count"] += record.gpu_count

        for instance in instances:
            if instance.gpu_utilization is not None:
                gpu_data[instance.gpu_type]["utilizations"].append(instance.gpu_utilization)

        by_gpu_type = [
            GPUBreakdown(
                gpu_type=gpu_type,
                total_cost=data["cost"],
                total_hours=data["hours"],
                gpu_count=data["count"],
                avg_utilization=(
                    sum(data["utilizations"]) / len(data["utilizations"])
                    if data["utilizations"] else None
                ),
            )
            for gpu_type, data in gpu_data.items()
        ]

        # Aggregate by region
        region_data = defaultdict(lambda: {"cost": 0.0, "count": 0, "provider": ""})

        for record in usage_records:
            key = f"{record.provider}:{record.region}"
            region_data[key]["cost"] += record.cost
            region_data[key]["count"] += 1
            region_data[key]["provider"] = record.provider

        by_region = [
            RegionBreakdown(
                region=key.split(":")[-1],
                provider=data["provider"],
                total_cost=data["cost"],
                instance_count=data["count"],
            )
            for key, data in region_data.items()
        ]

        # Aggregate by pricing type
        pricing_data = defaultdict(lambda: {"cost": 0.0, "hours": 0.0, "count": 0})

        for record in usage_records:
            pricing_data[record.pricing_type]["cost"] += record.cost
            pricing_data[record.pricing_type]["hours"] += record.hours_used
            pricing_data[record.pricing_type]["count"] += 1

        by_pricing = [
            PricingBreakdown(
                pricing_type=pricing_type,
                total_cost=data["cost"],
                total_hours=data["hours"],
                instance_count=data["count"],
            )
            for pricing_type, data in pricing_data.items()
        ]

        # Calculate overall utilization
        all_utilizations = [
            i.gpu_utilization for i in instances
            if i.gpu_utilization is not None
        ]
        avg_utilization = (
            sum(all_utilizations) / len(all_utilizations)
            if all_utilizations else None
        )

        # Calculate waste (cost of idle instances)
        estimated_waste = sum(
            i.hourly_cost * 24 * (end_date - start_date).days
            for i in idle_instances
        )

        # Calculate potential savings from spot pricing
        potential_savings = sum(p.potential_savings for p in by_pricing)

        return SpendSummary(
            start_date=start_date,
            end_date=end_date,
            total_cost=total_cost,
            total_gpu_hours=total_hours,
            total_instances=len(instances),
            running_instances=len(running_instances),
            idle_instances=len(idle_instances),
            by_provider=by_provider,
            by_gpu_type=by_gpu_type,
            by_region=by_region,
            by_pricing=by_pricing,
            avg_gpu_utilization=avg_utilization,
            estimated_waste=estimated_waste,
            potential_savings=potential_savings,
        )

    def get_current_monthly_spend(self) -> float:
        """Get current month's total spend."""
        now = datetime.now()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        summary = self.get_summary(start_of_month, now)
        return summary.total_cost

    def get_running_cost_per_hour(self) -> float:
        """Get current hourly burn rate."""
        instances = self.get_all_instances()
        return sum(i.hourly_cost for i in instances if i.is_running)
