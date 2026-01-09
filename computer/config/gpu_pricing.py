"""
GPU Pricing Reference Data

Last updated: January 2025
Prices are approximate and vary by region/availability.
"""

from computer.connect.base import GPUType

# GPU pricing by provider (hourly rates in USD)
GPU_PRICING = {
    "aws": {
        # P5 instances (H100)
        "p5.48xlarge": {"gpu_type": GPUType.H100_80GB, "gpus": 8, "hourly": 98.32},
        # P4 instances (A100)
        "p4d.24xlarge": {"gpu_type": GPUType.A100_40GB, "gpus": 8, "hourly": 32.77},
        "p4de.24xlarge": {"gpu_type": GPUType.A100_80GB, "gpus": 8, "hourly": 40.97},
        # P3 instances (V100)
        "p3.2xlarge": {"gpu_type": GPUType.V100_16GB, "gpus": 1, "hourly": 3.06},
        "p3.8xlarge": {"gpu_type": GPUType.V100_16GB, "gpus": 4, "hourly": 12.24},
        "p3.16xlarge": {"gpu_type": GPUType.V100_16GB, "gpus": 8, "hourly": 24.48},
        # G5 instances (A10G)
        "g5.xlarge": {"gpu_type": GPUType.A10G, "gpus": 1, "hourly": 1.006},
        "g5.2xlarge": {"gpu_type": GPUType.A10G, "gpus": 1, "hourly": 1.212},
        "g5.4xlarge": {"gpu_type": GPUType.A10G, "gpus": 1, "hourly": 1.624},
        "g5.12xlarge": {"gpu_type": GPUType.A10G, "gpus": 4, "hourly": 5.672},
        "g5.48xlarge": {"gpu_type": GPUType.A10G, "gpus": 8, "hourly": 16.288},
        # G4 instances (T4)
        "g4dn.xlarge": {"gpu_type": GPUType.T4, "gpus": 1, "hourly": 0.526},
        "g4dn.2xlarge": {"gpu_type": GPUType.T4, "gpus": 1, "hourly": 0.752},
        "g4dn.12xlarge": {"gpu_type": GPUType.T4, "gpus": 4, "hourly": 3.912},
    },
    "gcp": {
        "nvidia-tesla-a100": {"gpu_type": GPUType.A100_40GB, "gpus": 1, "hourly": 2.93},
        "nvidia-a100-80gb": {"gpu_type": GPUType.A100_80GB, "gpus": 1, "hourly": 3.67},
        "nvidia-h100-80gb": {"gpu_type": GPUType.H100_80GB, "gpus": 1, "hourly": 10.80},
        "nvidia-tesla-v100": {"gpu_type": GPUType.V100_16GB, "gpus": 1, "hourly": 2.48},
        "nvidia-l4": {"gpu_type": GPUType.L4, "gpus": 1, "hourly": 0.81},
        "nvidia-tesla-t4": {"gpu_type": GPUType.T4, "gpus": 1, "hourly": 0.35},
    },
    "azure": {
        "Standard_NC24ads_A100_v4": {"gpu_type": GPUType.A100_80GB, "gpus": 1, "hourly": 3.67},
        "Standard_NC48ads_A100_v4": {"gpu_type": GPUType.A100_80GB, "gpus": 2, "hourly": 7.35},
        "Standard_ND96asr_v4": {"gpu_type": GPUType.A100_40GB, "gpus": 8, "hourly": 27.20},
        "Standard_NC8as_T4_v3": {"gpu_type": GPUType.T4, "gpus": 1, "hourly": 0.752},
        "Standard_NC16as_T4_v3": {"gpu_type": GPUType.T4, "gpus": 1, "hourly": 1.204},
    },
    "vastai": {
        # Marketplace pricing varies - these are typical rates
        "rtx-4090": {"gpu_type": GPUType.RTX_4090, "gpus": 1, "hourly_range": (0.40, 0.60)},
        "rtx-3090": {"gpu_type": GPUType.RTX_3090, "gpus": 1, "hourly_range": (0.20, 0.35)},
        "a100-40gb": {"gpu_type": GPUType.A100_40GB, "gpus": 1, "hourly_range": (1.00, 1.50)},
        "a100-80gb": {"gpu_type": GPUType.A100_80GB, "gpus": 1, "hourly_range": (1.30, 1.80)},
        "h100": {"gpu_type": GPUType.H100_80GB, "gpus": 1, "hourly_range": (2.00, 3.00)},
    },
    "runpod": {
        # Community vs Secure cloud pricing
        "rtx-4090": {"gpu_type": GPUType.RTX_4090, "gpus": 1, "community": 0.44, "secure": 0.74},
        "rtx-3090": {"gpu_type": GPUType.RTX_3090, "gpus": 1, "community": 0.22, "secure": 0.44},
        "a100-80gb": {"gpu_type": GPUType.A100_80GB, "gpus": 1, "community": 1.19, "secure": 1.89},
        "h100": {"gpu_type": GPUType.H100_80GB, "gpus": 1, "community": 2.39, "secure": 3.89},
    },
    "lambda": {
        "gpu_1x_a100": {"gpu_type": GPUType.A100_40GB, "gpus": 1, "hourly": 1.10},
        "gpu_1x_a100_sxm4": {"gpu_type": GPUType.A100_80GB, "gpus": 1, "hourly": 1.29},
        "gpu_8x_a100": {"gpu_type": GPUType.A100_40GB, "gpus": 8, "hourly": 8.80},
        "gpu_1x_h100_pcie": {"gpu_type": GPUType.H100_80GB, "gpus": 1, "hourly": 1.99},
        "gpu_8x_h100_sxm5": {"gpu_type": GPUType.H100_SXM, "gpus": 8, "hourly": 23.92},
    },
}


def get_price(
    provider: str,
    instance_type: str,
    pricing_type: str = "on-demand"
) -> float:
    """
    Get hourly price for an instance type.

    Args:
        provider: Cloud provider name
        instance_type: Instance type identifier
        pricing_type: "on-demand", "spot", "community", "secure"

    Returns:
        Hourly price in USD
    """
    provider_lower = provider.lower()
    if provider_lower not in GPU_PRICING:
        return 0.0

    instance_lower = instance_type.lower()
    if instance_lower not in GPU_PRICING[provider_lower]:
        return 0.0

    pricing = GPU_PRICING[provider_lower][instance_lower]

    # Handle different pricing structures
    if "hourly" in pricing:
        base_price = pricing["hourly"]
    elif "hourly_range" in pricing:
        # Use midpoint for ranges
        low, high = pricing["hourly_range"]
        base_price = (low + high) / 2
    elif pricing_type == "community" and "community" in pricing:
        base_price = pricing["community"]
    elif pricing_type == "secure" and "secure" in pricing:
        base_price = pricing["secure"]
    else:
        base_price = pricing.get("community", 0.0)

    # Apply spot discount
    if pricing_type == "spot":
        base_price *= 0.35  # ~65% discount

    return base_price


def get_cheapest_option(
    gpu_type: GPUType,
    gpu_count: int = 1
) -> tuple[str, str, float]:
    """
    Find the cheapest option for a GPU type.

    Returns:
        Tuple of (provider, instance_type, hourly_price)
    """
    cheapest = None
    cheapest_price = float("inf")
    cheapest_instance = None

    for provider, instances in GPU_PRICING.items():
        for instance_type, pricing in instances.items():
            if pricing.get("gpu_type") != gpu_type:
                continue

            if pricing.get("gpus", 1) < gpu_count:
                continue

            # Get price
            if "hourly" in pricing:
                price = pricing["hourly"]
            elif "hourly_range" in pricing:
                price = pricing["hourly_range"][0]  # Use low end
            elif "community" in pricing:
                price = pricing["community"]
            else:
                continue

            # Normalize to per-GPU price
            price_per_gpu = price / pricing.get("gpus", 1)

            if price_per_gpu < cheapest_price:
                cheapest_price = price_per_gpu
                cheapest = provider
                cheapest_instance = instance_type

    if cheapest:
        return (cheapest, cheapest_instance, cheapest_price * gpu_count)

    return ("unknown", "unknown", 0.0)
