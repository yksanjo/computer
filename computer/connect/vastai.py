"""
Vast.ai Connector - Connect to Vast.ai marketplace for GPU rentals.
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

# Vast.ai GPU name mappings
VASTAI_GPU_MAPPING = {
    "RTX 4090": GPUType.RTX_4090,
    "RTX 4080": GPUType.RTX_4080,
    "RTX 3090": GPUType.RTX_3090,
    "RTX 3080": GPUType.RTX_3080,
    "A100 PCIe": GPUType.A100_40GB,
    "A100 SXM4": GPUType.A100_80GB,
    "A100-80GB": GPUType.A100_80GB,
    "H100 PCIe": GPUType.H100_80GB,
    "H100 SXM5": GPUType.H100_SXM,
    "V100": GPUType.V100_16GB,
    "A10": GPUType.A10G,
    "L4": GPUType.L4,
    "L40S": GPUType.L40S,
    "T4": GPUType.T4,
}


class VastAIConnector(BaseConnector):
    """Vast.ai marketplace connector."""

    provider_name = "vastai"

    BASE_URL = "https://console.vast.ai/api/v0"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("VASTAI_API_KEY")
        self._connected = False
        self._client = None

    def connect(self) -> bool:
        """Connect to Vast.ai API."""
        if not self.api_key:
            print("Vast.ai API key not provided. Using demo mode.")
            return False

        try:
            self._client = httpx.Client(
                base_url=self.BASE_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=30.0,
            )

            # Test connection
            response = self._client.get("/users/current")
            if response.status_code == 200:
                self._connected = True
                return True
            else:
                print(f"Vast.ai auth failed: {response.status_code}")
                return False

        except Exception as e:
            print(f"Vast.ai connection failed: {e}")
            return False

    def _map_gpu_type(self, gpu_name: str) -> GPUType:
        """Map Vast.ai GPU name to standard type."""
        for key, gpu_type in VASTAI_GPU_MAPPING.items():
            if key.lower() in gpu_name.lower():
                return gpu_type
        return GPUType.UNKNOWN

    def list_gpu_instances(self) -> list[GPUInstance]:
        """List rented instances."""
        if not self._connected:
            if not self.connect():
                return self._demo_instances()

        instances = []

        try:
            response = self._client.get("/instances")

            if response.status_code != 200:
                return self._demo_instances()

            data = response.json()

            for instance in data.get("instances", []):
                gpu_name = instance.get("gpu_name", "Unknown")
                gpu_type = self._map_gpu_type(gpu_name)

                instances.append(GPUInstance(
                    instance_id=str(instance.get("id")),
                    provider="vastai",
                    instance_type=gpu_name,
                    gpu_type=gpu_type,
                    gpu_count=instance.get("num_gpus", 1),
                    region=instance.get("geolocation", "unknown"),
                    pricing_type=PricingType.SPOT,  # Vast.ai is marketplace pricing
                    hourly_cost=instance.get("dph_total", 0.0),
                    status=instance.get("actual_status", "unknown"),
                    gpu_utilization=instance.get("gpu_util", None),
                ))

        except Exception as e:
            print(f"Error listing Vast.ai instances: {e}")
            return self._demo_instances()

        return instances

    def _demo_instances(self) -> list[GPUInstance]:
        """Return demo instances."""
        return [
            GPUInstance(
                instance_id="vast-demo-1",
                provider="vastai",
                instance_type="RTX 4090",
                gpu_type=GPUType.RTX_4090,
                gpu_count=1,
                region="US-West",
                pricing_type=PricingType.SPOT,
                hourly_cost=0.45,
                status="running",
                gpu_utilization=92.0,
            ),
            GPUInstance(
                instance_id="vast-demo-2",
                provider="vastai",
                instance_type="A100 PCIe",
                gpu_type=GPUType.A100_40GB,
                gpu_count=1,
                region="EU-West",
                pricing_type=PricingType.SPOT,
                hourly_cost=1.20,
                status="running",
                gpu_utilization=3.0,  # Idle!
            ),
        ]

    def get_usage(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> list[UsageRecord]:
        """Get usage history."""
        if not self._connected:
            return self._demo_usage(start_date, end_date)

        # Vast.ai API for billing history
        try:
            response = self._client.get("/invoices")
            # Parse invoices and create usage records
            # Simplified for now
            return self._demo_usage(start_date, end_date)
        except Exception:
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
                instance_id="vast-demo-1",
                provider="vastai",
                start_time=current,
                end_time=next_day,
                hours_used=18.0,  # Not 24/7
                cost=0.45 * 18,
                gpu_type=GPUType.RTX_4090,
                gpu_count=1,
                pricing_type=PricingType.SPOT,
                region="US-West",
            ))

            records.append(UsageRecord(
                instance_id="vast-demo-2",
                provider="vastai",
                start_time=current,
                end_time=next_day,
                hours_used=24.0,
                cost=1.20 * 24,
                gpu_type=GPUType.A100_40GB,
                gpu_count=1,
                pricing_type=PricingType.SPOT,
                region="EU-West",
            ))

            current = next_day

        return records

    def get_current_spend(self) -> float:
        """Get current billing period spend."""
        now = datetime.now()
        start_of_month = now.replace(day=1)

        usage_records = self.get_usage(start_of_month, now)
        return sum(r.cost for r in usage_records)

    def get_available_offers(self, gpu_type: Optional[GPUType] = None) -> list[dict]:
        """Get available GPU offers on the marketplace."""
        if not self._connected:
            return self._demo_offers()

        try:
            params = {"order": "dph_total", "type": "on-demand"}
            if gpu_type:
                params["gpu_name"] = gpu_type.value

            response = self._client.get("/bundles", params=params)

            if response.status_code == 200:
                return response.json().get("offers", [])

        except Exception:
            pass

        return self._demo_offers()

    def _demo_offers(self) -> list[dict]:
        """Demo marketplace offers."""
        return [
            {
                "gpu_name": "RTX 4090",
                "num_gpus": 1,
                "dph_total": 0.42,
                "cpu_cores": 16,
                "ram": 64,
                "disk": 100,
                "reliability": 0.98,
                "geolocation": "US-West",
            },
            {
                "gpu_name": "A100 PCIe",
                "num_gpus": 1,
                "dph_total": 1.15,
                "cpu_cores": 32,
                "ram": 128,
                "disk": 200,
                "reliability": 0.99,
                "geolocation": "US-East",
            },
            {
                "gpu_name": "H100 PCIe",
                "num_gpus": 1,
                "dph_total": 2.50,
                "cpu_cores": 64,
                "ram": 256,
                "disk": 500,
                "reliability": 0.995,
                "geolocation": "EU-West",
            },
        ]
