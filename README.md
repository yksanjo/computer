# Computer

**GPU Cost Intelligence Platform** - See, analyze, and optimize your GPU spend across cloud providers.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

## The Problem

Companies are bleeding money on GPU compute:
- **No visibility** into spend across multiple providers
- **Idle GPUs** running 24/7 at full price
- **Wrong pricing models** - on-demand when spot would work
- **No forecasting** - surprises at the end of the month

## The Solution

Computer provides a unified view of your GPU infrastructure:

```
$ computer status

GPU Instances
┌──────────────────┬──────────┬───────────┬───────┬─────────┬────────┬────────┐
│ Instance ID      │ Provider │ GPU Type  │ Count │ Status  │ $/hr   │ Util % │
├──────────────────┼──────────┼───────────┼───────┼─────────┼────────┼────────┤
│ i-0abc123def456  │ aws      │ a100-40gb │ 8     │ running │ $32.77 │ 85%    │
│ gcp-demo-2       │ gcp      │ a100-40gb │ 1     │ running │ $2.93  │ 5%     │  ← IDLE!
│ vast-demo-1      │ vastai   │ rtx-4090  │ 1     │ running │ $0.45  │ 92%    │
└──────────────────┴──────────┴───────────┴───────┴─────────┴────────┴────────┘

Summary
───────────────────────────────────────────────────────────────────────────────
Total Instances: 3
Running: 3  |  Idle: 1
Current Burn Rate: $36.15/hr | $867.60/day | $26,028.00/month
```

## Features

### 1. Connect - Multi-Cloud Integration
Connect to all major GPU providers with a single interface:
- **AWS** (EC2 GPU instances via Cost Explorer)
- **GCP** (Compute Engine with GPU accelerators)
- **Azure** (NC/ND series VMs)
- **Vast.ai** (GPU marketplace)
- **RunPod** (Cloud GPU)
- **Lambda Labs** (Cloud GPU)

### 2. See - Unified Spend Dashboard
```bash
$ computer spend --days 30

Spend Summary (30 days)
───────────────────────────────────────────────────────────────────────────────
Period: 2024-12-10 to 2025-01-09

Total Spend: $15,432.50
GPU Hours: 12,450.5
Avg $/GPU-hour: $1.2394

Idle Instances: 2 (18.2%)
Estimated Waste: $2,340.00
Potential Savings: $4,120.00
```

### 3. Waste - Find Inefficiencies
```bash
$ computer waste

Waste Report
───────────────────────────────────────────────────────────────────────────────
Instances Analyzed: 11
Total Alerts: 5
Critical/High: 2

Daily Waste: $78.00
Monthly Waste: $2,340.00
Annual Waste: $28,080.00
```

### 4. Forecast - Predict Costs
```bash
$ computer forecast --months 1

Cost Forecast
───────────────────────────────────────────────────────────────────────────────
Forecast Period: February 2025

Predicted Cost: $18,500.00
95% Confidence: $15,200.00 - $21,800.00
```

### 5. Optimize - Get Recommendations
```bash
$ computer optimize --quick

Optimization Report
───────────────────────────────────────────────────────────────────────────────
Total Recommendations: 8
Quick Wins: 3

Total Monthly Savings: $4,120.00
Annual Savings: $49,440.00

Recommendations
┌──────────┬─────────────────┬────────────────────────┬─────────────────┬────────┐
│ Priority │ Type            │ Title                  │ Monthly Savings │ Effort │
├──────────┼─────────────────┼────────────────────────┼─────────────────┼────────┤
│ CRITICAL │ terminate_idle  │ Terminate idle a100    │ $2,100.00       │ low    │
│ HIGH     │ terminate_idle  │ Terminate idle rtx4090 │ $324.00         │ low    │
│ MEDIUM   │ switch_to_spot  │ Switch p4d to spot     │ $1,696.00       │ medium │
└──────────┴─────────────────┴────────────────────────┴─────────────────┴────────┘
```

## Installation

```bash
# Clone the repository
git clone https://github.com/yksanjo/computer.git
cd computer

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install the package
pip install -e .
```

## Quick Start

### CLI Usage

```bash
# Show current GPU instances
computer status

# Analyze spend for the last 30 days
computer spend --days 30

# Find waste and inefficiencies
computer waste

# Get cost forecast
computer forecast

# Get optimization recommendations
computer optimize

# Estimate training cost for a 7B model
computer estimate 7 --tokens 2.0 --gpu h100 --count 8
```

### API Usage

```bash
# Start the API server
uvicorn api.main:app --reload

# API is available at http://localhost:8000
# Docs at http://localhost:8000/docs
```

### Python SDK

```python
from computer import SpendAggregator, WasteDetector, Recommender
from computer.connect import AWSConnector, VastAIConnector

# Setup
aggregator = SpendAggregator()
aggregator.add_connector(AWSConnector())
aggregator.add_connector(VastAIConnector())
aggregator.connect_all()

# Get spend summary
summary = aggregator.get_summary()
print(f"Total spend: ${summary.total_cost:,.2f}")
print(f"Idle instances: {summary.idle_instances}")

# Find waste
detector = WasteDetector(aggregator)
report = detector.analyze()
print(f"Monthly waste: ${report.total_monthly_waste:,.2f}")

# Get recommendations
recommender = Recommender(aggregator)
report = recommender.generate_recommendations()
for rec in report.quick_wins:
    print(f"- {rec.title}: Save ${rec.monthly_savings:,.2f}/month")
```

## Configuration

### Environment Variables

Create a `.env` file (copy from `.env.example`):

```bash
# AWS
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1

# GCP
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
GCP_PROJECT_ID=your-project

# Azure
AZURE_SUBSCRIPTION_ID=your_subscription
AZURE_TENANT_ID=your_tenant
AZURE_CLIENT_ID=your_client
AZURE_CLIENT_SECRET=your_secret

# GPU Marketplaces
VASTAI_API_KEY=your_vastai_key
RUNPOD_API_KEY=your_runpod_key
LAMBDA_API_KEY=your_lambda_key
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check and API info |
| `/instances` | GET | List all GPU instances |
| `/spend` | GET | Get spend analysis |
| `/waste` | GET | Detect waste and inefficiencies |
| `/forecast` | GET | Forecast future costs |
| `/optimize` | GET | Get optimization recommendations |
| `/estimate/training` | POST | Estimate training costs |
| `/estimate/inference` | POST | Estimate inference costs |
| `/pricing` | GET | Get GPU pricing reference |

## Architecture

```
computer/
├── computer/
│   ├── connect/       # Cloud provider integrations
│   │   ├── aws.py
│   │   ├── gcp.py
│   │   ├── azure.py
│   │   ├── vastai.py
│   │   ├── runpod.py
│   │   └── lambda_labs.py
│   ├── see/           # Spend aggregation
│   │   ├── aggregator.py
│   │   └── models.py
│   ├── waste/         # Waste detection
│   │   ├── detector.py
│   │   └── rules.py
│   ├── forecast/      # Cost prediction
│   │   └── predictor.py
│   ├── optimize/      # Recommendations
│   │   └── recommender.py
│   └── cli.py         # CLI interface
├── api/
│   └── main.py        # FastAPI REST API
└── scripts/
    └── demo.py        # Demo script
```

## Roadmap

- [ ] Real-time utilization monitoring
- [ ] Slack/Discord alerts for idle GPUs
- [ ] Budget alerts and thresholds
- [ ] Multi-account support
- [ ] Kubernetes GPU tracking
- [ ] Historical trend analysis
- [ ] Cost allocation by team/project

## Business Model

**Target Market:** AI/ML teams spending $10K-$1M+/month on GPU compute

**Revenue:**
- Self-serve SaaS: $99-499/month based on GPU spend tracked
- Enterprise: $2K-10K/month + percentage of savings identified

**Value Proposition:**
- Average customer wastes 30-50% on GPU compute
- Computer identifies $500-50K/month in savings
- 10-20x ROI on subscription cost

## Why This Matters

The GPU compute market is exploding:
- $50B+ market growing 30%+ annually
- Companies desperately need compute
- But tooling is immature - no "Datadog for GPU spend"

This is the **picks and shovels** play in the AI gold rush.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) first.

---

Built with urgency by [Yoshi Kondo](https://github.com/yksanjo)
