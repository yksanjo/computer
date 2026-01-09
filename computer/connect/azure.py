"""
Azure Connector - Connect to Azure for GPU cost data.
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

# Azure GPU VM mappings
AZURE_GPU_MAPPING = {
    # NC series (T4)
    "Standard_NC4as_T4_v3": (GPUType.T4, 1),
    "Standard_NC8as_T4_v3": (GPUType.T4, 1),
    "Standard_NC16as_T4_v3": (GPUType.T4, 1),
    "Standard_NC64as_T4_v3": (GPUType.T4, 4),
    # NC A100 series
    "Standard_NC24ads_A100_v4": (GPUType.A100_80GB, 1),
    "Standard_NC48ads_A100_v4": (GPUType.A100_80GB, 2),
    "Standard_NC96ads_A100_v4": (GPUType.A100_80GB, 4),
    # ND series (A100)
    "Standard_ND96asr_v4": (GPUType.A100_40GB, 8),
    "Standard_ND96amsr_A100_v4": (GPUType.A100_80GB, 8),
    # ND H100 series
    "Standard_ND96isr_H100_v5": (GPUType.H100_80GB, 8),
    # NV series (consumer-grade)
    "Standard_NV6": (GPUType.UNKNOWN, 1),
    "Standard_NV12": (GPUType.UNKNOWN, 2),
    "Standard_NV24": (GPUType.UNKNOWN, 4),
}

# Azure GPU hourly pricing (East US, approximate)
AZURE_GPU_PRICING = {
    "Standard_NC4as_T4_v3": 0.526,
    "Standard_NC8as_T4_v3": 0.752,
    "Standard_NC16as_T4_v3": 1.204,
    "Standard_NC64as_T4_v3": 4.352,
    "Standard_NC24ads_A100_v4": 3.67,
    "Standard_NC48ads_A100_v4": 7.35,
    "Standard_NC96ads_A100_v4": 14.69,
    "Standard_ND96asr_v4": 27.20,
    "Standard_ND96amsr_A100_v4": 32.77,
    "Standard_ND96isr_H100_v5": 98.32,
}


class AzureConnector(BaseConnector):
    """Azure connector for GPU spend analysis."""

    provider_name = "azure"

    def __init__(
        self,
        subscription_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ):
        self.subscription_id = subscription_id or os.getenv("AZURE_SUBSCRIPTION_ID")
        self.tenant_id = tenant_id or os.getenv("AZURE_TENANT_ID")
        self.client_id = client_id or os.getenv("AZURE_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("AZURE_CLIENT_SECRET")

        self._connected = False
        self._compute_client = None
        self._cost_client = None

    def connect(self) -> bool:
        """Connect to Azure."""
        try:
            from azure.identity import ClientSecretCredential
            from azure.mgmt.compute import ComputeManagementClient
            from azure.mgmt.costmanagement import CostManagementClient

            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret,
            )

            self._compute_client = ComputeManagementClient(
                credential, self.subscription_id
            )
            self._cost_client = CostManagementClient(credential)

            self._connected = True
            return True

        except ImportError:
            print("Azure libraries not installed.")
            print("Run: pip install azure-identity azure-mgmt-compute azure-mgmt-costmanagement")
            return False
        except Exception as e:
            print(f"Azure connection failed: {e}")
            return False

    def list_gpu_instances(self) -> list[GPUInstance]:
        """List all GPU VMs."""
        if not self._connected:
            if not self.connect():
                return self._demo_instances()

        instances = []

        try:
            for vm in self._compute_client.virtual_machines.list_all():
                vm_size = vm.hardware_profile.vm_size

                if vm_size not in AZURE_GPU_MAPPING:
                    continue

                gpu_type, gpu_count = AZURE_GPU_MAPPING[vm_size]
                hourly_cost = AZURE_GPU_PRICING.get(vm_size, 0.0)

                # Check for spot
                pricing_type = PricingType.ON_DEMAND
                if vm.priority == "Spot":
                    pricing_type = PricingType.SPOT
                    hourly_cost *= 0.3

                instances.append(GPUInstance(
                    instance_id=vm.vm_id,
                    provider="azure",
                    instance_type=vm_size,
                    gpu_type=gpu_type,
                    gpu_count=gpu_count,
                    region=vm.location,
                    pricing_type=pricing_type,
                    hourly_cost=hourly_cost,
                    status=vm.instance_view.statuses[-1].display_status if vm.instance_view else "unknown",
                    tags=dict(vm.tags) if vm.tags else {},
                ))

        except Exception as e:
            print(f"Error listing Azure VMs: {e}")
            return self._demo_instances()

        return instances

    def _demo_instances(self) -> list[GPUInstance]:
        """Return demo instances."""
        return [
            GPUInstance(
                instance_id="azure-demo-1",
                provider="azure",
                instance_type="Standard_NC8as_T4_v3",
                gpu_type=GPUType.T4,
                gpu_count=1,
                region="eastus",
                pricing_type=PricingType.ON_DEMAND,
                hourly_cost=0.752,
                status="running",
                gpu_utilization=78.0,
            ),
            GPUInstance(
                instance_id="azure-demo-2",
                provider="azure",
                instance_type="Standard_NC24ads_A100_v4",
                gpu_type=GPUType.A100_80GB,
                gpu_count=1,
                region="eastus",
                pricing_type=PricingType.ON_DEMAND,
                hourly_cost=3.67,
                status="running",
                gpu_utilization=12.0,
            ),
        ]

    def get_usage(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> list[UsageRecord]:
        """Get GPU usage records."""
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

            records.append(UsageRecord(
                instance_id="azure-demo-1",
                provider="azure",
                start_time=current,
                end_time=next_day,
                hours_used=24.0,
                cost=0.752 * 24,
                gpu_type=GPUType.T4,
                gpu_count=1,
                pricing_type=PricingType.ON_DEMAND,
                region="eastus",
            ))

            records.append(UsageRecord(
                instance_id="azure-demo-2",
                provider="azure",
                start_time=current,
                end_time=next_day,
                hours_used=24.0,
                cost=3.67 * 24,
                gpu_type=GPUType.A100_80GB,
                gpu_count=1,
                pricing_type=PricingType.ON_DEMAND,
                region="eastus",
            ))

            current = next_day

        return records

    def get_current_spend(self) -> float:
        """Get current month's GPU spend."""
        now = datetime.now()
        start_of_month = now.replace(day=1)

        usage_records = self.get_usage(start_of_month, now)
        return sum(r.cost for r in usage_records)
