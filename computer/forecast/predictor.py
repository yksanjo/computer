"""
Cost Predictor - Forecast GPU costs based on usage patterns.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import numpy as np

from computer.connect.base import GPUType, UsageRecord
from computer.see.aggregator import SpendAggregator


@dataclass
class CostForecast:
    """Cost forecast for a future period."""
    forecast_date: datetime
    period_start: datetime
    period_end: datetime
    predicted_cost: float
    confidence_low: float
    confidence_high: float
    confidence_level: float = 0.95  # 95% confidence interval

    # Breakdown predictions
    by_provider: dict = field(default_factory=dict)
    by_gpu_type: dict = field(default_factory=dict)

    # Model info
    model_type: str = "linear_trend"
    data_points_used: int = 0

    def to_dict(self) -> dict:
        return {
            "forecast_date": self.forecast_date.isoformat(),
            "period": {
                "start": self.period_start.isoformat(),
                "end": self.period_end.isoformat(),
                "days": (self.period_end - self.period_start).days,
            },
            "prediction": {
                "cost": round(self.predicted_cost, 2),
                "confidence_low": round(self.confidence_low, 2),
                "confidence_high": round(self.confidence_high, 2),
                "confidence_level": self.confidence_level,
            },
            "by_provider": {
                k: round(v, 2) for k, v in self.by_provider.items()
            },
            "by_gpu_type": {
                k: round(v, 2) for k, v in self.by_gpu_type.items()
            },
            "model": {
                "type": self.model_type,
                "data_points": self.data_points_used,
            },
        }


@dataclass
class TrainingCostEstimate:
    """Estimate cost for a specific training run."""
    model_name: str
    gpu_type: GPUType
    gpu_count: int
    estimated_hours: float
    estimated_cost: float
    cost_range_low: float
    cost_range_high: float

    # Provider comparison
    provider_costs: dict = field(default_factory=dict)
    cheapest_provider: str = ""
    cheapest_cost: float = 0.0

    def to_dict(self) -> dict:
        return {
            "model": self.model_name,
            "configuration": {
                "gpu_type": self.gpu_type.value,
                "gpu_count": self.gpu_count,
                "estimated_hours": round(self.estimated_hours, 1),
            },
            "cost": {
                "estimated": round(self.estimated_cost, 2),
                "range_low": round(self.cost_range_low, 2),
                "range_high": round(self.cost_range_high, 2),
            },
            "provider_comparison": {
                k: round(v, 2) for k, v in self.provider_costs.items()
            },
            "recommendation": {
                "cheapest_provider": self.cheapest_provider,
                "cheapest_cost": round(self.cheapest_cost, 2),
            },
        }


class CostPredictor:
    """Predicts future GPU costs based on historical data."""

    # GPU hourly rates by provider (for estimation)
    GPU_RATES = {
        GPUType.A100_40GB: {
            "aws": 32.77 / 8,  # p4d per GPU
            "gcp": 2.93,
            "azure": 3.67,
            "vastai": 1.20,
            "runpod": 1.19,
            "lambda": 1.10,
        },
        GPUType.A100_80GB: {
            "aws": 40.97 / 8,
            "gcp": 3.67,
            "azure": 3.67,
            "vastai": 1.50,
            "runpod": 1.49,
            "lambda": 1.29,
        },
        GPUType.H100_80GB: {
            "aws": 98.32 / 8,
            "gcp": 10.80,
            "azure": 98.32 / 8,
            "vastai": 2.50,
            "runpod": 2.39,
            "lambda": 1.99,
        },
        GPUType.RTX_4090: {
            "vastai": 0.45,
            "runpod": 0.44,
        },
        GPUType.T4: {
            "aws": 0.526,
            "gcp": 0.35,
            "azure": 0.526,
        },
    }

    def __init__(self, aggregator: Optional[SpendAggregator] = None):
        self.aggregator = aggregator or SpendAggregator()

    def forecast_month(
        self,
        target_month: Optional[datetime] = None,
        lookback_days: int = 30,
    ) -> CostForecast:
        """
        Forecast costs for a target month.

        Uses linear trend from lookback period.
        """
        now = datetime.now()

        if target_month is None:
            # Forecast next month
            if now.month == 12:
                target_month = now.replace(year=now.year + 1, month=1, day=1)
            else:
                target_month = now.replace(month=now.month + 1, day=1)

        # Get historical data
        start_date = now - timedelta(days=lookback_days)
        end_date = now

        usage_records = self.aggregator.get_all_usage(start_date, end_date)

        if not usage_records:
            # No data, use current instances as baseline
            return self._forecast_from_current_instances(target_month)

        # Aggregate daily costs
        daily_costs = self._aggregate_daily_costs(usage_records)

        if len(daily_costs) < 3:
            # Not enough data for trend, use average
            avg_daily = sum(daily_costs.values()) / len(daily_costs)
            days_in_month = 30
            predicted = avg_daily * days_in_month

            return CostForecast(
                forecast_date=now,
                period_start=target_month,
                period_end=target_month.replace(day=28) + timedelta(days=4),
                predicted_cost=predicted,
                confidence_low=predicted * 0.7,
                confidence_high=predicted * 1.3,
                data_points_used=len(daily_costs),
            )

        # Fit linear trend
        days = sorted(daily_costs.keys())
        costs = [daily_costs[d] for d in days]

        x = np.arange(len(costs))
        y = np.array(costs)

        # Linear regression
        slope, intercept = np.polyfit(x, y, 1)
        std_dev = np.std(y)

        # Project to target month
        days_ahead = (target_month - now).days
        projected_daily = intercept + slope * (len(costs) + days_ahead)
        projected_daily = max(0, projected_daily)  # No negative costs

        days_in_month = 30
        predicted = projected_daily * days_in_month

        # Confidence interval (95%)
        confidence_margin = 1.96 * std_dev * np.sqrt(days_in_month)

        # Aggregate by provider and GPU type
        by_provider = self._aggregate_by_provider(usage_records)
        by_gpu_type = self._aggregate_by_gpu_type(usage_records)

        # Scale to monthly projection
        total_historical = sum(r.cost for r in usage_records)
        if total_historical > 0:
            scale_factor = predicted / total_historical
            by_provider = {k: v * scale_factor for k, v in by_provider.items()}
            by_gpu_type = {k: v * scale_factor for k, v in by_gpu_type.items()}

        return CostForecast(
            forecast_date=now,
            period_start=target_month,
            period_end=target_month.replace(day=28) + timedelta(days=4),
            predicted_cost=predicted,
            confidence_low=max(0, predicted - confidence_margin),
            confidence_high=predicted + confidence_margin,
            by_provider=by_provider,
            by_gpu_type=by_gpu_type,
            model_type="linear_trend",
            data_points_used=len(costs),
        )

    def _forecast_from_current_instances(
        self,
        target_month: datetime
    ) -> CostForecast:
        """Forecast based on current running instances."""
        instances = self.aggregator.get_all_instances()
        running = [i for i in instances if i.is_running]

        hourly_cost = sum(i.hourly_cost for i in running)
        monthly_cost = hourly_cost * 24 * 30

        by_provider = {}
        by_gpu_type = {}

        for instance in running:
            monthly = instance.hourly_cost * 24 * 30
            by_provider[instance.provider] = by_provider.get(instance.provider, 0) + monthly
            by_gpu_type[instance.gpu_type.value] = by_gpu_type.get(instance.gpu_type.value, 0) + monthly

        return CostForecast(
            forecast_date=datetime.now(),
            period_start=target_month,
            period_end=target_month.replace(day=28) + timedelta(days=4),
            predicted_cost=monthly_cost,
            confidence_low=monthly_cost * 0.8,
            confidence_high=monthly_cost * 1.2,
            by_provider=by_provider,
            by_gpu_type=by_gpu_type,
            model_type="current_instances",
            data_points_used=len(running),
        )

    def _aggregate_daily_costs(
        self,
        records: list[UsageRecord]
    ) -> dict[datetime, float]:
        """Aggregate records into daily costs."""
        daily = {}
        for record in records:
            day = record.start_time.replace(hour=0, minute=0, second=0, microsecond=0)
            daily[day] = daily.get(day, 0) + record.cost
        return daily

    def _aggregate_by_provider(
        self,
        records: list[UsageRecord]
    ) -> dict[str, float]:
        """Aggregate costs by provider."""
        by_provider = {}
        for record in records:
            by_provider[record.provider] = by_provider.get(record.provider, 0) + record.cost
        return by_provider

    def _aggregate_by_gpu_type(
        self,
        records: list[UsageRecord]
    ) -> dict[str, float]:
        """Aggregate costs by GPU type."""
        by_type = {}
        for record in records:
            key = record.gpu_type.value
            by_type[key] = by_type.get(key, 0) + record.cost
        return by_type

    def estimate_training_cost(
        self,
        model_size_params: float,  # In billions
        gpu_type: GPUType = GPUType.A100_80GB,
        gpu_count: int = 8,
        training_tokens: float = 1e12,  # 1 trillion tokens
    ) -> TrainingCostEstimate:
        """
        Estimate cost for a training run.

        Uses scaling laws to estimate training time.
        """
        # Rough estimate: ~6 * params * tokens FLOPs for training
        # A100: ~312 TFLOPS (FP16)
        # H100: ~1979 TFLOPS (FP16)

        flops_per_gpu = {
            GPUType.A100_40GB: 312e12,
            GPUType.A100_80GB: 312e12,
            GPUType.H100_80GB: 1979e12,
            GPUType.H100_SXM: 1979e12,
            GPUType.RTX_4090: 82.6e12,
        }.get(gpu_type, 312e12)

        # Total FLOPs needed (simplified)
        total_flops = 6 * model_size_params * 1e9 * training_tokens

        # GPU hours needed (assuming 40% utilization)
        gpu_seconds = total_flops / (flops_per_gpu * gpu_count * 0.4)
        gpu_hours = gpu_seconds / 3600

        # Get provider costs
        provider_costs = {}
        rates = self.GPU_RATES.get(gpu_type, {})

        for provider, rate in rates.items():
            cost = rate * gpu_count * gpu_hours
            provider_costs[provider] = cost

        if provider_costs:
            cheapest = min(provider_costs.items(), key=lambda x: x[1])
            cheapest_provider, cheapest_cost = cheapest
        else:
            cheapest_provider = "unknown"
            cheapest_cost = 0

        # Average cost across providers
        avg_cost = sum(provider_costs.values()) / len(provider_costs) if provider_costs else 0

        return TrainingCostEstimate(
            model_name=f"{model_size_params}B params",
            gpu_type=gpu_type,
            gpu_count=gpu_count,
            estimated_hours=gpu_hours,
            estimated_cost=avg_cost,
            cost_range_low=cheapest_cost,
            cost_range_high=max(provider_costs.values()) if provider_costs else 0,
            provider_costs=provider_costs,
            cheapest_provider=cheapest_provider,
            cheapest_cost=cheapest_cost,
        )

    def estimate_inference_cost(
        self,
        requests_per_day: int,
        tokens_per_request: int = 1000,
        gpu_type: GPUType = GPUType.A100_40GB,
    ) -> dict:
        """Estimate daily/monthly inference costs."""
        # Rough throughput estimates (tokens/second)
        throughput = {
            GPUType.A100_40GB: 5000,
            GPUType.A100_80GB: 6000,
            GPUType.H100_80GB: 15000,
            GPUType.T4: 1000,
            GPUType.RTX_4090: 3000,
        }.get(gpu_type, 3000)

        # GPU seconds needed per day
        total_tokens = requests_per_day * tokens_per_request
        gpu_seconds_per_day = total_tokens / throughput
        gpu_hours_per_day = gpu_seconds_per_day / 3600

        # Cost estimates
        rates = self.GPU_RATES.get(gpu_type, {})

        daily_costs = {}
        for provider, rate in rates.items():
            daily_costs[provider] = rate * gpu_hours_per_day

        avg_daily = sum(daily_costs.values()) / len(daily_costs) if daily_costs else 0

        return {
            "requests_per_day": requests_per_day,
            "tokens_per_request": tokens_per_request,
            "gpu_type": gpu_type.value,
            "gpu_hours_per_day": round(gpu_hours_per_day, 2),
            "daily_cost": {k: round(v, 2) for k, v in daily_costs.items()},
            "monthly_cost": {k: round(v * 30, 2) for k, v in daily_costs.items()},
            "average_daily": round(avg_daily, 2),
            "average_monthly": round(avg_daily * 30, 2),
        }
