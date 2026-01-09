"""
Computer REST API - FastAPI application for GPU cost intelligence.
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from computer import __version__
from computer.connect import (
    AWSConnector,
    GCPConnector,
    AzureConnector,
    VastAIConnector,
    RunPodConnector,
    LambdaConnector,
)
from computer.connect.base import GPUType
from computer.see import SpendAggregator
from computer.waste import WasteDetector
from computer.forecast import CostPredictor
from computer.optimize import Recommender


# FastAPI app
app = FastAPI(
    title="Computer API",
    description="GPU Cost Intelligence Platform - See, analyze, and optimize your GPU spend",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
class ProviderConfig(BaseModel):
    """Provider configuration."""
    providers: list[str] = Field(
        default=["aws", "gcp", "azure", "vastai", "runpod", "lambda"],
        description="List of providers to connect to",
    )
    demo_mode: bool = Field(
        default=True,
        description="Use demo data instead of real API calls",
    )


class TrainingEstimateRequest(BaseModel):
    """Training cost estimate request."""
    model_size_params: float = Field(..., description="Model size in billions of parameters")
    training_tokens: float = Field(1e12, description="Number of training tokens")
    gpu_type: str = Field("a100-80gb", description="GPU type")
    gpu_count: int = Field(8, description="Number of GPUs")


class InferenceEstimateRequest(BaseModel):
    """Inference cost estimate request."""
    requests_per_day: int = Field(..., description="Expected requests per day")
    tokens_per_request: int = Field(1000, description="Average tokens per request")
    gpu_type: str = Field("a100-40gb", description="GPU type")


# Helper functions
def get_aggregator(config: ProviderConfig) -> SpendAggregator:
    """Create aggregator with configured providers."""
    aggregator = SpendAggregator()

    provider_map = {
        "aws": AWSConnector,
        "gcp": GCPConnector,
        "azure": AzureConnector,
        "vastai": VastAIConnector,
        "runpod": RunPodConnector,
        "lambda": LambdaConnector,
    }

    for provider in config.providers:
        provider_lower = provider.lower()
        if provider_lower in provider_map:
            connector = provider_map[provider_lower]()
            aggregator.add_connector(connector)

    if not config.demo_mode:
        aggregator.connect_all()

    return aggregator


def parse_gpu_type(gpu_str: str) -> GPUType:
    """Parse GPU type string to enum."""
    mapping = {
        "a100-40gb": GPUType.A100_40GB,
        "a100-80gb": GPUType.A100_80GB,
        "h100": GPUType.H100_80GB,
        "h100-80gb": GPUType.H100_80GB,
        "h100-sxm": GPUType.H100_SXM,
        "v100": GPUType.V100_16GB,
        "t4": GPUType.T4,
        "l4": GPUType.L4,
        "rtx-4090": GPUType.RTX_4090,
        "rtx-3090": GPUType.RTX_3090,
    }
    return mapping.get(gpu_str.lower(), GPUType.A100_80GB)


# Routes
@app.get("/")
async def root():
    """API root - health check and info."""
    return {
        "name": "Computer API",
        "version": __version__,
        "description": "GPU Cost Intelligence Platform",
        "endpoints": {
            "instances": "/instances",
            "spend": "/spend",
            "waste": "/waste",
            "forecast": "/forecast",
            "optimize": "/optimize",
            "estimate/training": "/estimate/training",
            "estimate/inference": "/estimate/inference",
        },
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/instances")
async def list_instances(
    providers: str = Query("all", description="Comma-separated providers or 'all'"),
    demo: bool = Query(True, description="Use demo data"),
):
    """List all GPU instances across providers."""
    if providers == "all":
        provider_list = ["aws", "gcp", "azure", "vastai", "runpod", "lambda"]
    else:
        provider_list = [p.strip() for p in providers.split(",")]

    config = ProviderConfig(providers=provider_list, demo_mode=demo)
    aggregator = get_aggregator(config)

    instances = aggregator.get_all_instances()

    return {
        "instances": [
            {
                "id": i.instance_id,
                "provider": i.provider,
                "type": i.instance_type,
                "gpu_type": i.gpu_type.value,
                "gpu_count": i.gpu_count,
                "region": i.region,
                "pricing_type": i.pricing_type.value,
                "hourly_cost": i.hourly_cost,
                "status": i.status,
                "is_running": i.is_running,
                "is_idle": i.is_idle,
                "gpu_utilization": i.gpu_utilization,
                "memory_utilization": i.memory_utilization,
            }
            for i in instances
        ],
        "summary": {
            "total": len(instances),
            "running": len([i for i in instances if i.is_running]),
            "idle": len([i for i in instances if i.is_idle]),
            "hourly_burn_rate": sum(i.hourly_cost for i in instances if i.is_running),
            "daily_burn_rate": sum(i.hourly_cost for i in instances if i.is_running) * 24,
            "monthly_burn_rate": sum(i.hourly_cost for i in instances if i.is_running) * 24 * 30,
        },
    }


@app.get("/spend")
async def get_spend(
    days: int = Query(30, description="Number of days to analyze"),
    providers: str = Query("all", description="Comma-separated providers or 'all'"),
    demo: bool = Query(True, description="Use demo data"),
):
    """Get spend analysis for a time period."""
    if providers == "all":
        provider_list = ["aws", "gcp", "azure", "vastai", "runpod", "lambda"]
    else:
        provider_list = [p.strip() for p in providers.split(",")]

    config = ProviderConfig(providers=provider_list, demo_mode=demo)
    aggregator = get_aggregator(config)

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    summary = aggregator.get_summary(start_date, end_date)

    return summary.to_dict()


@app.get("/waste")
async def detect_waste(
    providers: str = Query("all", description="Comma-separated providers or 'all'"),
    min_savings: float = Query(50.0, description="Minimum monthly savings to report"),
    demo: bool = Query(True, description="Use demo data"),
):
    """Detect GPU waste and inefficiencies."""
    if providers == "all":
        provider_list = ["aws", "gcp", "azure", "vastai", "runpod", "lambda"]
    else:
        provider_list = [p.strip() for p in providers.split(",")]

    config = ProviderConfig(providers=provider_list, demo_mode=demo)
    aggregator = get_aggregator(config)
    detector = WasteDetector(aggregator)

    report = detector.analyze()

    # Filter by min_savings
    result = report.to_dict()
    result["alerts"] = [
        a for a in result["alerts"]
        if a["waste_per_month"] >= min_savings
    ]

    return result


@app.get("/forecast")
async def forecast_costs(
    months_ahead: int = Query(1, description="Months to forecast ahead"),
    lookback_days: int = Query(30, description="Days of historical data to use"),
    providers: str = Query("all", description="Comma-separated providers or 'all'"),
    demo: bool = Query(True, description="Use demo data"),
):
    """Forecast future GPU costs."""
    if providers == "all":
        provider_list = ["aws", "gcp", "azure", "vastai", "runpod", "lambda"]
    else:
        provider_list = [p.strip() for p in providers.split(",")]

    config = ProviderConfig(providers=provider_list, demo_mode=demo)
    aggregator = get_aggregator(config)
    predictor = CostPredictor(aggregator)

    now = datetime.now()
    if now.month + months_ahead > 12:
        target = now.replace(
            year=now.year + 1,
            month=(now.month + months_ahead - 1) % 12 + 1,
            day=1
        )
    else:
        target = now.replace(month=now.month + months_ahead, day=1)

    forecast = predictor.forecast_month(target, lookback_days)

    return forecast.to_dict()


@app.get("/optimize")
async def get_recommendations(
    providers: str = Query("all", description="Comma-separated providers or 'all'"),
    quick_wins_only: bool = Query(False, description="Return only quick wins"),
    demo: bool = Query(True, description="Use demo data"),
):
    """Get optimization recommendations."""
    if providers == "all":
        provider_list = ["aws", "gcp", "azure", "vastai", "runpod", "lambda"]
    else:
        provider_list = [p.strip() for p in providers.split(",")]

    config = ProviderConfig(providers=provider_list, demo_mode=demo)
    aggregator = get_aggregator(config)
    recommender = Recommender(aggregator)

    report = recommender.generate_recommendations()
    result = report.to_dict()

    if quick_wins_only:
        result["recommendations"] = [
            r for r in result["recommendations"]
            if r["effort"] == "low" and r["monthly_savings"] > 50
        ]

    return result


@app.post("/estimate/training")
async def estimate_training(request: TrainingEstimateRequest):
    """Estimate training costs for a model."""
    predictor = CostPredictor()
    gpu_type = parse_gpu_type(request.gpu_type)

    estimate = predictor.estimate_training_cost(
        model_size_params=request.model_size_params,
        gpu_type=gpu_type,
        gpu_count=request.gpu_count,
        training_tokens=request.training_tokens,
    )

    return estimate.to_dict()


@app.post("/estimate/inference")
async def estimate_inference(request: InferenceEstimateRequest):
    """Estimate inference costs."""
    predictor = CostPredictor()
    gpu_type = parse_gpu_type(request.gpu_type)

    estimate = predictor.estimate_inference_cost(
        requests_per_day=request.requests_per_day,
        tokens_per_request=request.tokens_per_request,
        gpu_type=gpu_type,
    )

    return estimate


@app.get("/pricing")
async def get_pricing():
    """Get current GPU pricing reference."""
    return {
        "last_updated": "2025-01-01",
        "note": "Prices are approximate and vary by region/availability",
        "providers": {
            "aws": {
                "p5.48xlarge": {"gpu": "8x H100", "hourly": 98.32},
                "p4d.24xlarge": {"gpu": "8x A100 40GB", "hourly": 32.77},
                "g5.xlarge": {"gpu": "1x A10G", "hourly": 1.006},
                "g4dn.xlarge": {"gpu": "1x T4", "hourly": 0.526},
            },
            "gcp": {
                "a100-40gb": {"hourly": 2.93},
                "a100-80gb": {"hourly": 3.67},
                "h100-80gb": {"hourly": 10.80},
                "t4": {"hourly": 0.35},
            },
            "azure": {
                "NC24ads_A100_v4": {"gpu": "1x A100 80GB", "hourly": 3.67},
                "NC8as_T4_v3": {"gpu": "1x T4", "hourly": 0.752},
            },
            "vastai": {
                "rtx-4090": {"hourly_range": "0.40-0.60"},
                "a100-40gb": {"hourly_range": "1.00-1.50"},
                "h100": {"hourly_range": "2.00-3.00"},
            },
            "runpod": {
                "rtx-4090": {"community": 0.44, "secure": 0.74},
                "a100-80gb": {"community": 1.19, "secure": 1.89},
                "h100": {"community": 2.39, "secure": 3.89},
            },
            "lambda": {
                "a100-40gb": {"hourly": 1.10},
                "a100-80gb": {"hourly": 1.29},
                "h100": {"hourly": 1.99},
            },
        },
    }


# Run with: uvicorn api.main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
