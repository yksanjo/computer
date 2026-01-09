"""
Basic tests for Computer platform.
"""

import pytest
from datetime import datetime, timedelta

from computer.connect.base import GPUInstance, GPUType, PricingType, UsageRecord
from computer.see import SpendAggregator
from computer.waste import WasteDetector
from computer.forecast import CostPredictor
from computer.optimize import Recommender


class TestGPUInstance:
    """Tests for GPUInstance model."""

    def test_is_running(self):
        instance = GPUInstance(
            instance_id="test-1",
            provider="test",
            instance_type="test-type",
            gpu_type=GPUType.A100_40GB,
            gpu_count=1,
            region="us-east-1",
            pricing_type=PricingType.ON_DEMAND,
            hourly_cost=2.93,
            status="running",
        )
        assert instance.is_running is True

        instance.status = "stopped"
        assert instance.is_running is False

    def test_is_idle(self):
        instance = GPUInstance(
            instance_id="test-1",
            provider="test",
            instance_type="test-type",
            gpu_type=GPUType.A100_40GB,
            gpu_count=1,
            region="us-east-1",
            pricing_type=PricingType.ON_DEMAND,
            hourly_cost=2.93,
            status="running",
            gpu_utilization=5.0,
        )
        assert instance.is_idle is True

        instance.gpu_utilization = 50.0
        assert instance.is_idle is False

        instance.status = "stopped"
        assert instance.is_idle is False


class TestSpendAggregator:
    """Tests for SpendAggregator."""

    def test_empty_aggregator(self):
        aggregator = SpendAggregator()
        instances = aggregator.get_all_instances()
        assert instances == []

    def test_get_summary_empty(self):
        aggregator = SpendAggregator()
        summary = aggregator.get_summary()
        assert summary.total_cost == 0
        assert summary.total_instances == 0


class TestWasteDetector:
    """Tests for WasteDetector."""

    def test_detect_idle_gpu(self):
        aggregator = SpendAggregator()
        detector = WasteDetector(aggregator)

        # Create an idle instance
        idle_instance = GPUInstance(
            instance_id="idle-1",
            provider="test",
            instance_type="test-type",
            gpu_type=GPUType.A100_40GB,
            gpu_count=1,
            region="us-east-1",
            pricing_type=PricingType.ON_DEMAND,
            hourly_cost=2.93,
            status="running",
            gpu_utilization=3.0,  # < 5% threshold
        )

        alerts = detector.analyze_instance(idle_instance)
        assert len(alerts) > 0
        assert any(a.waste_type.value == "idle_gpu" for a in alerts)

    def test_no_waste_for_utilized_gpu(self):
        aggregator = SpendAggregator()
        detector = WasteDetector(aggregator)

        utilized_instance = GPUInstance(
            instance_id="utilized-1",
            provider="test",
            instance_type="test-type",
            gpu_type=GPUType.A100_40GB,
            gpu_count=1,
            region="us-east-1",
            pricing_type=PricingType.ON_DEMAND,
            hourly_cost=2.93,
            status="running",
            gpu_utilization=85.0,
        )

        alerts = detector.analyze_instance(utilized_instance)
        idle_alerts = [a for a in alerts if a.waste_type.value == "idle_gpu"]
        assert len(idle_alerts) == 0


class TestCostPredictor:
    """Tests for CostPredictor."""

    def test_training_estimate(self):
        predictor = CostPredictor()
        estimate = predictor.estimate_training_cost(
            model_size_params=7.0,
            gpu_type=GPUType.A100_80GB,
            gpu_count=8,
            training_tokens=1e12,
        )

        assert estimate.estimated_hours > 0
        assert estimate.estimated_cost > 0
        assert len(estimate.provider_costs) > 0
        assert estimate.cheapest_provider != ""

    def test_inference_estimate(self):
        predictor = CostPredictor()
        estimate = predictor.estimate_inference_cost(
            requests_per_day=10000,
            tokens_per_request=1000,
            gpu_type=GPUType.A100_40GB,
        )

        assert estimate["gpu_hours_per_day"] > 0
        assert estimate["average_daily"] > 0


class TestRecommender:
    """Tests for Recommender."""

    def test_generate_recommendations(self):
        aggregator = SpendAggregator()
        recommender = Recommender(aggregator)

        report = recommender.generate_recommendations()
        assert report is not None
        assert hasattr(report, "total_monthly_savings")

    def test_quick_wins(self):
        aggregator = SpendAggregator()
        recommender = Recommender(aggregator)

        quick_wins = recommender.get_quick_wins(min_savings=0)
        # May be empty with no connectors, that's OK
        assert isinstance(quick_wins, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
