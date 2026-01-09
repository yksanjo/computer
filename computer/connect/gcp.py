"""
GCP Connector - Connect to Google Cloud for GPU cost data.
"""

import os
from datetime import datetime
from typing import Optional

from computer.connect.base import (
    BaseConnector,
    GPUInstance,
    GPUType,
    PricingType,
    UsageRecord,
)

# GCP GPU type mappings
GCP_GPU_MAPPING = {
    "nvidia-tesla-a100": GPUType.A100_40GB,
    "nvidia-a100-80gb": GPUType.A100_80GB,
    "nvidia-h100-80gb": GPUType.H100_80GB,
    "nvidia-tesla-v100": GPUType.V100_16GB,
    "nvidia-l4": GPUType.L4,
    "nvidia-tesla-t4": GPUType.T4,
}

# GCP GPU hourly pricing (us-central1, approximate)
GCP_GPU_PRICING = {
    "nvidia-tesla-a100": 2.93,
    "nvidia-a100-80gb": 3.67,
    "nvidia-h100-80gb": 10.80,
    "nvidia-tesla-v100": 2.48,
    "nvidia-l4": 0.81,
    "nvidia-tesla-t4": 0.35,
}


class GCPConnector(BaseConnector):
    """Google Cloud Platform connector for GPU spend analysis."""

    provider_name = "gcp"

    def __init__(
        self,
        project_id: Optional[str] = None,
        credentials_path: Optional[str] = None,
    ):
        self.project_id = project_id or os.getenv("GCP_PROJECT_ID")
        self.credentials_path = credentials_path or os.getenv(
            "GOOGLE_APPLICATION_CREDENTIALS"
        )
        self._connected = False
        self._compute_client = None
        self._billing_client = None

    def connect(self) -> bool:
        """Connect to GCP."""
        try:
            # Set credentials path if provided
            if self.credentials_path:
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.credentials_path

            from google.cloud import compute_v1
            from google.cloud import billing_v1

            self._compute_client = compute_v1.InstancesClient()
            self._billing_client = billing_v1.CloudBillingClient()
            self._connected = True
            return True

        except ImportError:
            print("Google Cloud libraries not installed.")
            print("Run: pip install google-cloud-compute google-cloud-billing")
            return False
        except Exception as e:
            print(f"GCP connection failed: {e}")
            return False

    def list_gpu_instances(self) -> list[GPUInstance]:
        """List all GPU instances."""
        if not self._connected:
            if not self.connect():
                # Return demo data if not connected
                return self._demo_instances()

        instances = []

        try:
            from google.cloud import compute_v1

            # List all zones
            zones_client = compute_v1.ZonesClient()
            zones = zones_client.list(project=self.project_id)

            for zone in zones:
                zone_name = zone.name

                request = compute_v1.ListInstancesRequest(
                    project=self.project_id,
                    zone=zone_name,
                )

                for instance in self._compute_client.list(request=request):
                    # Check for GPU accelerators
                    if not instance.guest_accelerators:
                        continue

                    for accelerator in instance.guest_accelerators:
                        gpu_type_str = accelerator.accelerator_type.split("/")[-1]
                        gpu_type = GCP_GPU_MAPPING.get(
                            gpu_type_str, GPUType.UNKNOWN
                        )
                        gpu_count = accelerator.accelerator_count

                        hourly_cost = GCP_GPU_PRICING.get(gpu_type_str, 0.0) * gpu_count

                        # Determine pricing type
                        pricing_type = PricingType.ON_DEMAND
                        if instance.scheduling.preemptible:
                            pricing_type = PricingType.PREEMPTIBLE
                            hourly_cost *= 0.3

                        instances.append(GPUInstance(
                            instance_id=str(instance.id),
                            provider="gcp",
                            instance_type=instance.machine_type.split("/")[-1],
                            gpu_type=gpu_type,
                            gpu_count=gpu_count,
                            region=zone_name,
                            pricing_type=pricing_type,
                            hourly_cost=hourly_cost,
                            status=instance.status.lower(),
                            launched_at=None,
                            tags=dict(instance.labels) if instance.labels else {},
                        ))

        except Exception as e:
            print(f"Error listing GCP instances: {e}")
            return self._demo_instances()

        return instances

    def _demo_instances(self) -> list[GPUInstance]:
        """Return demo instances for testing without credentials."""
        return [
            GPUInstance(
                instance_id="gcp-demo-1",
                provider="gcp",
                instance_type="n1-standard-8",
                gpu_type=GPUType.T4,
                gpu_count=1,
                region="us-central1-a",
                pricing_type=PricingType.ON_DEMAND,
                hourly_cost=0.35,
                status="running",
                gpu_utilization=45.0,
            ),
            GPUInstance(
                instance_id="gcp-demo-2",
                provider="gcp",
                instance_type="a2-highgpu-1g",
                gpu_type=GPUType.A100_40GB,
                gpu_count=1,
                region="us-central1-a",
                pricing_type=PricingType.ON_DEMAND,
                hourly_cost=2.93,
                status="running",
                gpu_utilization=5.0,  # Idle!
            ),
        ]

    def get_usage(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> list[UsageRecord]:
        """Get GPU usage records."""
        # Return demo data for now
        return self._demo_usage(start_date, end_date)

    def _demo_usage(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> list[UsageRecord]:
        """Generate demo usage data."""
        from datetime import timedelta

        records = []
        current = start_date

        while current < end_date:
            next_day = current + timedelta(days=1)

            # T4 instance usage
            records.append(UsageRecord(
                instance_id="gcp-demo-1",
                provider="gcp",
                start_time=current,
                end_time=next_day,
                hours_used=24.0,
                cost=0.35 * 24,
                gpu_type=GPUType.T4,
                gpu_count=1,
                pricing_type=PricingType.ON_DEMAND,
                region="us-central1-a",
            ))

            # A100 instance usage (idle)
            records.append(UsageRecord(
                instance_id="gcp-demo-2",
                provider="gcp",
                start_time=current,
                end_time=next_day,
                hours_used=24.0,
                cost=2.93 * 24,
                gpu_type=GPUType.A100_40GB,
                gpu_count=1,
                pricing_type=PricingType.ON_DEMAND,
                region="us-central1-a",
            ))

            current = next_day

        return records

    def get_current_spend(self) -> float:
        """Get current month's GPU spend."""
        now = datetime.now()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        usage_records = self.get_usage(start_of_month, now)
        return sum(r.cost for r in usage_records)
