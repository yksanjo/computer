"""
AWS Connector - Connect to AWS Cost Explorer and EC2 for GPU data.
"""

import os
from datetime import datetime, timedelta
from typing import Optional

from computer.connect.base import (
    BaseConnector,
    GPUInstance,
    GPUType,
    PricingType,
    UsageRecord,
)

# AWS GPU instance type mappings
AWS_GPU_MAPPING = {
    # P5 instances (H100)
    "p5.48xlarge": (GPUType.H100_80GB, 8),
    # P4 instances (A100)
    "p4d.24xlarge": (GPUType.A100_40GB, 8),
    "p4de.24xlarge": (GPUType.A100_80GB, 8),
    # P3 instances (V100)
    "p3.2xlarge": (GPUType.V100_16GB, 1),
    "p3.8xlarge": (GPUType.V100_16GB, 4),
    "p3.16xlarge": (GPUType.V100_16GB, 8),
    "p3dn.24xlarge": (GPUType.V100_32GB, 8),
    # G5 instances (A10G)
    "g5.xlarge": (GPUType.A10G, 1),
    "g5.2xlarge": (GPUType.A10G, 1),
    "g5.4xlarge": (GPUType.A10G, 1),
    "g5.8xlarge": (GPUType.A10G, 1),
    "g5.12xlarge": (GPUType.A10G, 4),
    "g5.16xlarge": (GPUType.A10G, 1),
    "g5.24xlarge": (GPUType.A10G, 4),
    "g5.48xlarge": (GPUType.A10G, 8),
    # G6 instances (L4)
    "g6.xlarge": (GPUType.L4, 1),
    "g6.2xlarge": (GPUType.L4, 1),
    "g6.4xlarge": (GPUType.L4, 1),
    "g6.8xlarge": (GPUType.L4, 1),
    "g6.12xlarge": (GPUType.L4, 4),
    "g6.16xlarge": (GPUType.L4, 1),
    "g6.24xlarge": (GPUType.L4, 4),
    "g6.48xlarge": (GPUType.L4, 8),
    # G4 instances (T4)
    "g4dn.xlarge": (GPUType.T4, 1),
    "g4dn.2xlarge": (GPUType.T4, 1),
    "g4dn.4xlarge": (GPUType.T4, 1),
    "g4dn.8xlarge": (GPUType.T4, 1),
    "g4dn.12xlarge": (GPUType.T4, 4),
    "g4dn.16xlarge": (GPUType.T4, 1),
    "g4dn.metal": (GPUType.T4, 8),
}

# On-demand pricing (us-east-1, approximate)
AWS_GPU_PRICING = {
    "p5.48xlarge": 98.32,
    "p4d.24xlarge": 32.77,
    "p4de.24xlarge": 40.97,
    "p3.2xlarge": 3.06,
    "p3.8xlarge": 12.24,
    "p3.16xlarge": 24.48,
    "p3dn.24xlarge": 31.22,
    "g5.xlarge": 1.006,
    "g5.2xlarge": 1.212,
    "g5.4xlarge": 1.624,
    "g5.8xlarge": 2.448,
    "g5.12xlarge": 5.672,
    "g5.16xlarge": 4.096,
    "g5.24xlarge": 8.144,
    "g5.48xlarge": 16.288,
    "g6.xlarge": 0.805,
    "g6.2xlarge": 0.978,
    "g6.4xlarge": 1.323,
    "g6.8xlarge": 2.014,
    "g6.12xlarge": 4.602,
    "g6.16xlarge": 3.397,
    "g6.24xlarge": 6.675,
    "g6.48xlarge": 13.35,
    "g4dn.xlarge": 0.526,
    "g4dn.2xlarge": 0.752,
    "g4dn.4xlarge": 1.204,
    "g4dn.8xlarge": 2.176,
    "g4dn.12xlarge": 3.912,
    "g4dn.16xlarge": 4.352,
    "g4dn.metal": 7.824,
}


class AWSConnector(BaseConnector):
    """AWS Cost Explorer and EC2 connector for GPU spend analysis."""

    provider_name = "aws"

    def __init__(
        self,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        region: str = "us-east-1",
    ):
        self.access_key_id = access_key_id or os.getenv("AWS_ACCESS_KEY_ID")
        self.secret_access_key = secret_access_key or os.getenv("AWS_SECRET_ACCESS_KEY")
        self.region = region or os.getenv("AWS_REGION", "us-east-1")

        self._ec2_client = None
        self._ce_client = None
        self._connected = False

    def connect(self) -> bool:
        """Connect to AWS using boto3."""
        try:
            import boto3

            session_kwargs = {"region_name": self.region}
            if self.access_key_id and self.secret_access_key:
                session_kwargs["aws_access_key_id"] = self.access_key_id
                session_kwargs["aws_secret_access_key"] = self.secret_access_key

            session = boto3.Session(**session_kwargs)
            self._ec2_client = session.client("ec2")
            self._ce_client = session.client("ce", region_name="us-east-1")  # CE is global

            # Test connection
            self._ec2_client.describe_regions(RegionNames=[self.region])
            self._connected = True
            return True

        except ImportError:
            print("boto3 not installed. Run: pip install boto3")
            return False
        except Exception as e:
            print(f"AWS connection failed: {e}")
            return False

    def _is_gpu_instance(self, instance_type: str) -> bool:
        """Check if an instance type has GPUs."""
        return instance_type in AWS_GPU_MAPPING

    def _parse_instance(self, instance: dict, region: str) -> Optional[GPUInstance]:
        """Parse EC2 instance into GPUInstance."""
        instance_type = instance.get("InstanceType", "")

        if not self._is_gpu_instance(instance_type):
            return None

        gpu_type, gpu_count = AWS_GPU_MAPPING.get(
            instance_type, (GPUType.UNKNOWN, 0)
        )

        # Determine pricing type
        lifecycle = instance.get("InstanceLifecycle", "")
        if lifecycle == "spot":
            pricing_type = PricingType.SPOT
        else:
            pricing_type = PricingType.ON_DEMAND

        # Get pricing
        hourly_cost = AWS_GPU_PRICING.get(instance_type, 0.0)
        if pricing_type == PricingType.SPOT:
            hourly_cost *= 0.3  # Approximate spot discount

        # Parse tags
        tags = {}
        for tag in instance.get("Tags", []):
            tags[tag["Key"]] = tag["Value"]

        # Map state
        state = instance.get("State", {}).get("Name", "unknown")

        return GPUInstance(
            instance_id=instance["InstanceId"],
            provider="aws",
            instance_type=instance_type,
            gpu_type=gpu_type,
            gpu_count=gpu_count,
            region=region,
            pricing_type=pricing_type,
            hourly_cost=hourly_cost,
            status=state,
            launched_at=instance.get("LaunchTime"),
            tags=tags,
        )

    def list_gpu_instances(self) -> list[GPUInstance]:
        """List all GPU instances across all regions."""
        if not self._connected:
            if not self.connect():
                return []

        instances = []

        try:
            # Get all regions
            regions_response = self._ec2_client.describe_regions()
            regions = [r["RegionName"] for r in regions_response["Regions"]]

            import boto3

            for region in regions:
                try:
                    regional_ec2 = boto3.client(
                        "ec2",
                        region_name=region,
                        aws_access_key_id=self.access_key_id,
                        aws_secret_access_key=self.secret_access_key,
                    )

                    # Get all instances (not just running)
                    paginator = regional_ec2.get_paginator("describe_instances")

                    for page in paginator.paginate():
                        for reservation in page["Reservations"]:
                            for instance in reservation["Instances"]:
                                gpu_instance = self._parse_instance(instance, region)
                                if gpu_instance:
                                    instances.append(gpu_instance)
                except Exception as e:
                    print(f"Error scanning region {region}: {e}")
                    continue

        except Exception as e:
            print(f"Error listing GPU instances: {e}")

        return instances

    def get_usage(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> list[UsageRecord]:
        """Get GPU usage from Cost Explorer."""
        if not self._connected:
            if not self.connect():
                return []

        records = []

        try:
            # Query Cost Explorer for GPU instance usage
            response = self._ce_client.get_cost_and_usage(
                TimePeriod={
                    "Start": start_date.strftime("%Y-%m-%d"),
                    "End": end_date.strftime("%Y-%m-%d"),
                },
                Granularity="DAILY",
                Metrics=["UnblendedCost", "UsageQuantity"],
                GroupBy=[
                    {"Type": "DIMENSION", "Key": "INSTANCE_TYPE"},
                    {"Type": "DIMENSION", "Key": "REGION"},
                ],
                Filter={
                    "Dimensions": {
                        "Key": "INSTANCE_TYPE",
                        "Values": list(AWS_GPU_MAPPING.keys()),
                    }
                },
            )

            for result in response.get("ResultsByTime", []):
                period_start = datetime.strptime(
                    result["TimePeriod"]["Start"], "%Y-%m-%d"
                )
                period_end = datetime.strptime(
                    result["TimePeriod"]["End"], "%Y-%m-%d"
                )

                for group in result.get("Groups", []):
                    keys = group["Keys"]
                    instance_type = keys[0] if len(keys) > 0 else "unknown"
                    region = keys[1] if len(keys) > 1 else "unknown"

                    cost = float(
                        group["Metrics"]["UnblendedCost"]["Amount"]
                    )
                    usage_hours = float(
                        group["Metrics"]["UsageQuantity"]["Amount"]
                    )

                    gpu_type, gpu_count = AWS_GPU_MAPPING.get(
                        instance_type, (GPUType.UNKNOWN, 0)
                    )

                    if cost > 0 or usage_hours > 0:
                        records.append(UsageRecord(
                            instance_id=f"aggregated-{instance_type}",
                            provider="aws",
                            start_time=period_start,
                            end_time=period_end,
                            hours_used=usage_hours,
                            cost=cost,
                            gpu_type=gpu_type,
                            gpu_count=gpu_count,
                            pricing_type=PricingType.ON_DEMAND,
                            region=region,
                        ))

        except Exception as e:
            print(f"Error getting usage: {e}")

        return records

    def get_current_spend(self) -> float:
        """Get current month's GPU spend."""
        now = datetime.now()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        usage_records = self.get_usage(start_of_month, now)
        return sum(r.cost for r in usage_records)

    def get_spot_pricing(self, instance_type: str, region: str) -> Optional[float]:
        """Get current spot price for an instance type."""
        if not self._connected:
            return None

        try:
            import boto3

            ec2 = boto3.client(
                "ec2",
                region_name=region,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
            )

            response = ec2.describe_spot_price_history(
                InstanceTypes=[instance_type],
                ProductDescriptions=["Linux/UNIX"],
                MaxResults=1,
            )

            if response["SpotPriceHistory"]:
                return float(response["SpotPriceHistory"][0]["SpotPrice"])

        except Exception:
            pass

        return None
