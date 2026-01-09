"""
Lambda Labs Connector - Connect to Lambda Labs cloud GPU service.
"""

import os
from datetime import datetime
from typing import Optional

import httpx

from computer.connect.base import (
    BaseConnector,
    GPUInstance,
    GPUType,
    PricingType,
    UsageRecord,
)

# Lambda Labs instance type mappings
LAMBDA_GPU_MAPPING = {
    "gpu_1x_a100": (GPUType.A100_40GB, 1),
    "gpu_1x_a100_sxm4": (GPUType.A100_80GB, 1),
    "gpu_8x_a100": (GPUType.A100_40GB, 8),
    "gpu_8x_a100_80gb_sxm4": (GPUType.A100_80GB, 8),
    "gpu_1x_h100_pcie": (GPUType.H100_80GB, 1),
    "gpu_8x_h100_sxm5": (GPUType.H100_SXM, 8),
    "gpu_1x_rtx6000ada": (GPUType.L40S, 1),
    "gpu_1x_a10": (GPUType.A10G, 1),
}

# Lambda Labs pricing (per hour)
LAMBDA_PRICING = {
    "gpu_1x_a100": 1.10,
    "gpu_1x_a100_sxm4": 1.29,
    "gpu_8x_a100": 8.80,
    "gpu_8x_a100_80gb_sxm4": 10.32,
    "gpu_1x_h100_pcie": 1.99,
    "gpu_8x_h100_sxm5": 23.92,
    "gpu_1x_rtx6000ada": 0.80,
    "gpu_1x_a10": 0.60,
}


class LambdaConnector(BaseConnector):
    """Lambda Labs connector."""

    provider_name = "lambda"

    BASE_URL = "https://cloud.lambdalabs.com/api/v1"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("LAMBDA_API_KEY")
        self._connected = False
        self._client = None

    def connect(self) -> bool:
        """Connect to Lambda Labs API."""
        if not self.api_key:
            print("Lambda Labs API key not provided. Using demo mode.")
            return False

        try:
            self._client = httpx.Client(
                base_url=self.BASE_URL,
                timeout=30.0,
                auth=(self.api_key, ""),
            )

            # Test connection
            response = self._client.get("/instances")

            if response.status_code == 200:
                self._connected = True
                return True
            else:
                print(f"Lambda Labs auth failed: {response.status_code}")
                return False

        except Exception as e:
            print(f"Lambda Labs connection failed: {e}")
            return False

    def list_gpu_instances(self) -> list[GPUInstance]:
        """List active instances."""
        if not self._connected:
            if not self.connect():
                return self._demo_instances()

        instances = []

        try:
            response = self._client.get("/instances")

            if response.status_code != 200:
                return self._demo_instances()

            data = response.json()

            for instance in data.get("data", []):
                instance_type = instance.get("instance_type", {})
                type_name = instance_type.get("name", "unknown")

                gpu_type, gpu_count = LAMBDA_GPU_MAPPING.get(
                    type_name, (GPUType.UNKNOWN, 1)
                )
                hourly_cost = LAMBDA_PRICING.get(type_name, 0.0)

                instances.append(GPUInstance(
                    instance_id=instance.get("id"),
                    provider="lambda",
                    instance_type=type_name,
                    gpu_type=gpu_type,
                    gpu_count=gpu_count,
                    region=instance.get("region", {}).get("name", "unknown"),
                    pricing_type=PricingType.ON_DEMAND,
                    hourly_cost=hourly_cost,
                    status=instance.get("status", "unknown"),
                ))

        except Exception as e:
            print(f"Error listing Lambda instances: {e}")
            return self._demo_instances()

        return instances

    def _demo_instances(self) -> list[GPUInstance]:
        """Return demo instances."""
        return [
            GPUInstance(
                instance_id="lambda-demo-1",
                provider="lambda",
                instance_type="gpu_1x_a100",
                gpu_type=GPUType.A100_40GB,
                gpu_count=1,
                region="us-west-2",
                pricing_type=PricingType.ON_DEMAND,
                hourly_cost=1.10,
                status="running",
                gpu_utilization=72.0,
            ),
            GPUInstance(
                instance_id="lambda-demo-2",
                provider="lambda",
                instance_type="gpu_1x_h100_pcie",
                gpu_type=GPUType.H100_80GB,
                gpu_count=1,
                region="us-east-1",
                pricing_type=PricingType.ON_DEMAND,
                hourly_cost=1.99,
                status="running",
                gpu_utilization=15.0,
            ),
        ]

    def get_usage(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> list[UsageRecord]:
        """Get usage records."""
        # Lambda Labs doesn't have a public billing API
        return self._demo_usage(start_date, end_date)

    def _demo_usage(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> list[UsageRecord]:
        """Generate demo usage."""
        from datetime import timedelta

        records = []
        current = start_date

        while current < end_date:
            next_day = current + timedelta(days=1)

            records.append(UsageRecord(
                instance_id="lambda-demo-1",
                provider="lambda",
                start_time=current,
                end_time=next_day,
                hours_used=24.0,
                cost=1.10 * 24,
                gpu_type=GPUType.A100_40GB,
                gpu_count=1,
                pricing_type=PricingType.ON_DEMAND,
                region="us-west-2",
            ))

            records.append(UsageRecord(
                instance_id="lambda-demo-2",
                provider="lambda",
                start_time=current,
                end_time=next_day,
                hours_used=24.0,
                cost=1.99 * 24,
                gpu_type=GPUType.H100_80GB,
                gpu_count=1,
                pricing_type=PricingType.ON_DEMAND,
                region="us-east-1",
            ))

            current = next_day

        return records

    def get_current_spend(self) -> float:
        """Get current spend."""
        now = datetime.now()
        start_of_month = now.replace(day=1)

        usage_records = self.get_usage(start_of_month, now)
        return sum(r.cost for r in usage_records)

    def get_instance_types(self) -> list[dict]:
        """Get available instance types."""
        if not self._connected:
            return self._demo_instance_types()

        try:
            response = self._client.get("/instance-types")

            if response.status_code == 200:
                return response.json().get("data", {})

        except Exception:
            pass

        return self._demo_instance_types()

    def _demo_instance_types(self) -> list[dict]:
        """Demo instance types."""
        return [
            {
                "name": "gpu_1x_a100",
                "description": "1x A100 40GB",
                "price_cents_per_hour": 110,
                "specs": {
                    "vcpus": 24,
                    "memory_gib": 200,
                    "storage_gib": 512,
                },
            },
            {
                "name": "gpu_1x_h100_pcie",
                "description": "1x H100 80GB PCIe",
                "price_cents_per_hour": 199,
                "specs": {
                    "vcpus": 26,
                    "memory_gib": 200,
                    "storage_gib": 512,
                },
            },
            {
                "name": "gpu_8x_h100_sxm5",
                "description": "8x H100 80GB SXM5",
                "price_cents_per_hour": 2392,
                "specs": {
                    "vcpus": 208,
                    "memory_gib": 1800,
                    "storage_gib": 20000,
                },
            },
        ]
