"""
RunPod Connector - Connect to RunPod for GPU rentals.
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

# RunPod GPU mappings
RUNPOD_GPU_MAPPING = {
    "NVIDIA RTX 4090": GPUType.RTX_4090,
    "NVIDIA RTX 4080": GPUType.RTX_4080,
    "NVIDIA RTX 3090": GPUType.RTX_3090,
    "NVIDIA A100 80GB PCIe": GPUType.A100_80GB,
    "NVIDIA A100-SXM4-80GB": GPUType.A100_80GB,
    "NVIDIA H100 PCIe": GPUType.H100_80GB,
    "NVIDIA H100 SXM": GPUType.H100_SXM,
    "NVIDIA A10G": GPUType.A10G,
    "NVIDIA L4": GPUType.L4,
    "NVIDIA L40S": GPUType.L40S,
}

# RunPod pricing (approximate, varies by availability)
RUNPOD_PRICING = {
    GPUType.RTX_4090: {"community": 0.44, "secure": 0.74},
    GPUType.RTX_3090: {"community": 0.22, "secure": 0.44},
    GPUType.A100_80GB: {"community": 1.19, "secure": 1.89},
    GPUType.H100_80GB: {"community": 2.39, "secure": 3.89},
    GPUType.A10G: {"community": 0.28, "secure": 0.50},
    GPUType.L4: {"community": 0.24, "secure": 0.44},
}


class RunPodConnector(BaseConnector):
    """RunPod connector for GPU rentals."""

    provider_name = "runpod"

    BASE_URL = "https://api.runpod.io/graphql"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("RUNPOD_API_KEY")
        self._connected = False
        self._client = None

    def connect(self) -> bool:
        """Connect to RunPod API."""
        if not self.api_key:
            print("RunPod API key not provided. Using demo mode.")
            return False

        try:
            self._client = httpx.Client(
                timeout=30.0,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )

            # Test connection with a simple query
            query = """
            query {
                myself {
                    id
                    email
                }
            }
            """

            response = self._client.post(
                self.BASE_URL,
                json={"query": query},
            )

            if response.status_code == 200:
                data = response.json()
                if "errors" not in data:
                    self._connected = True
                    return True

            return False

        except Exception as e:
            print(f"RunPod connection failed: {e}")
            return False

    def _map_gpu_type(self, gpu_name: str) -> GPUType:
        """Map RunPod GPU name to standard type."""
        for key, gpu_type in RUNPOD_GPU_MAPPING.items():
            if key.lower() in gpu_name.lower():
                return gpu_type
        return GPUType.UNKNOWN

    def list_gpu_instances(self) -> list[GPUInstance]:
        """List active pods."""
        if not self._connected:
            if not self.connect():
                return self._demo_instances()

        instances = []

        try:
            query = """
            query {
                myself {
                    pods {
                        id
                        name
                        runtime {
                            gpuCount
                            gpus {
                                name
                            }
                        }
                        costPerHr
                        desiredStatus
                        gpuUtilPercent
                        memoryUtilPercent
                    }
                }
            }
            """

            response = self._client.post(
                self.BASE_URL,
                json={"query": query},
            )

            if response.status_code != 200:
                return self._demo_instances()

            data = response.json()
            pods = data.get("data", {}).get("myself", {}).get("pods", [])

            for pod in pods:
                runtime = pod.get("runtime", {})
                gpus = runtime.get("gpus", [])
                gpu_name = gpus[0].get("name", "Unknown") if gpus else "Unknown"
                gpu_type = self._map_gpu_type(gpu_name)

                instances.append(GPUInstance(
                    instance_id=pod.get("id"),
                    provider="runpod",
                    instance_type=gpu_name,
                    gpu_type=gpu_type,
                    gpu_count=runtime.get("gpuCount", 1),
                    region="runpod-cloud",
                    pricing_type=PricingType.ON_DEMAND,
                    hourly_cost=pod.get("costPerHr", 0.0),
                    status=pod.get("desiredStatus", "unknown").lower(),
                    gpu_utilization=pod.get("gpuUtilPercent"),
                    memory_utilization=pod.get("memoryUtilPercent"),
                ))

        except Exception as e:
            print(f"Error listing RunPod pods: {e}")
            return self._demo_instances()

        return instances

    def _demo_instances(self) -> list[GPUInstance]:
        """Return demo instances."""
        return [
            GPUInstance(
                instance_id="runpod-demo-1",
                provider="runpod",
                instance_type="NVIDIA RTX 4090",
                gpu_type=GPUType.RTX_4090,
                gpu_count=1,
                region="runpod-cloud",
                pricing_type=PricingType.ON_DEMAND,
                hourly_cost=0.44,
                status="running",
                gpu_utilization=85.0,
            ),
            GPUInstance(
                instance_id="runpod-demo-2",
                provider="runpod",
                instance_type="NVIDIA A100 80GB PCIe",
                gpu_type=GPUType.A100_80GB,
                gpu_count=1,
                region="runpod-cloud",
                pricing_type=PricingType.ON_DEMAND,
                hourly_cost=1.19,
                status="running",
                gpu_utilization=8.0,  # Underutilized
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

        # RunPod doesn't have a straightforward billing history API
        # We'd need to track usage ourselves or use their billing dashboard data
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
                instance_id="runpod-demo-1",
                provider="runpod",
                start_time=current,
                end_time=next_day,
                hours_used=20.0,
                cost=0.44 * 20,
                gpu_type=GPUType.RTX_4090,
                gpu_count=1,
                pricing_type=PricingType.ON_DEMAND,
                region="runpod-cloud",
            ))

            records.append(UsageRecord(
                instance_id="runpod-demo-2",
                provider="runpod",
                start_time=current,
                end_time=next_day,
                hours_used=24.0,
                cost=1.19 * 24,
                gpu_type=GPUType.A100_80GB,
                gpu_count=1,
                pricing_type=PricingType.ON_DEMAND,
                region="runpod-cloud",
            ))

            current = next_day

        return records

    def get_current_spend(self) -> float:
        """Get current spend."""
        now = datetime.now()
        start_of_month = now.replace(day=1)

        usage_records = self.get_usage(start_of_month, now)
        return sum(r.cost for r in usage_records)

    def get_available_gpus(self) -> list[dict]:
        """Get available GPU types and pricing."""
        if not self._connected:
            return self._demo_available_gpus()

        try:
            query = """
            query {
                gpuTypes {
                    id
                    displayName
                    memoryInGb
                    secureCloud
                    communityCloud
                    lowestPrice {
                        minimumBidPrice
                        uninterruptablePrice
                    }
                }
            }
            """

            response = self._client.post(
                self.BASE_URL,
                json={"query": query},
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("data", {}).get("gpuTypes", [])

        except Exception:
            pass

        return self._demo_available_gpus()

    def _demo_available_gpus(self) -> list[dict]:
        """Demo available GPUs."""
        return [
            {
                "id": "NVIDIA RTX 4090",
                "displayName": "RTX 4090",
                "memoryInGb": 24,
                "communityCloud": True,
                "secureCloud": True,
                "lowestPrice": {
                    "minimumBidPrice": 0.34,
                    "uninterruptablePrice": 0.44,
                },
            },
            {
                "id": "NVIDIA A100 80GB PCIe",
                "displayName": "A100 80GB",
                "memoryInGb": 80,
                "communityCloud": True,
                "secureCloud": True,
                "lowestPrice": {
                    "minimumBidPrice": 0.99,
                    "uninterruptablePrice": 1.19,
                },
            },
            {
                "id": "NVIDIA H100 PCIe",
                "displayName": "H100",
                "memoryInGb": 80,
                "communityCloud": True,
                "secureCloud": True,
                "lowestPrice": {
                    "minimumBidPrice": 1.99,
                    "uninterruptablePrice": 2.39,
                },
            },
        ]
