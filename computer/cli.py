"""
Computer CLI - Command line interface for GPU cost intelligence.
"""

import json
from datetime import datetime, timedelta
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from computer.connect import (
    AWSConnector,
    GCPConnector,
    AzureConnector,
    VastAIConnector,
    RunPodConnector,
    LambdaConnector,
)
from computer.see import SpendAggregator
from computer.waste import WasteDetector
from computer.forecast import CostPredictor
from computer.optimize import Recommender

app = typer.Typer(
    name="computer",
    help="GPU Cost Intelligence Platform - See, analyze, and optimize your GPU spend",
    add_completion=False,
)
console = Console()


def create_aggregator(
    providers: list[str],
    demo: bool = False,
) -> SpendAggregator:
    """Create aggregator with specified providers."""
    aggregator = SpendAggregator()

    provider_map = {
        "aws": AWSConnector,
        "gcp": GCPConnector,
        "azure": AzureConnector,
        "vastai": VastAIConnector,
        "runpod": RunPodConnector,
        "lambda": LambdaConnector,
    }

    for provider in providers:
        provider_lower = provider.lower()
        if provider_lower in provider_map:
            connector = provider_map[provider_lower]()
            aggregator.add_connector(connector)

    if not demo:
        aggregator.connect_all()

    return aggregator


@app.command()
def status(
    providers: str = typer.Option(
        "all",
        "--providers", "-p",
        help="Comma-separated list of providers (aws,gcp,azure,vastai,runpod,lambda) or 'all'",
    ),
    json_output: bool = typer.Option(
        False,
        "--json", "-j",
        help="Output as JSON",
    ),
):
    """Show current GPU instances and running costs."""
    if providers == "all":
        provider_list = ["aws", "gcp", "azure", "vastai", "runpod", "lambda"]
    else:
        provider_list = [p.strip() for p in providers.split(",")]

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("Connecting to providers...", total=None)
        aggregator = create_aggregator(provider_list, demo=True)

    instances = aggregator.get_all_instances()

    if json_output:
        output = {
            "instances": [
                {
                    "id": i.instance_id,
                    "provider": i.provider,
                    "type": i.instance_type,
                    "gpu": i.gpu_type.value,
                    "gpu_count": i.gpu_count,
                    "region": i.region,
                    "status": i.status,
                    "hourly_cost": i.hourly_cost,
                    "utilization": i.gpu_utilization,
                }
                for i in instances
            ],
            "summary": {
                "total": len(instances),
                "running": len([i for i in instances if i.is_running]),
                "idle": len([i for i in instances if i.is_idle]),
                "hourly_burn": sum(i.hourly_cost for i in instances if i.is_running),
            },
        }
        console.print(json.dumps(output, indent=2))
        return

    # Display table
    table = Table(title="GPU Instances")
    table.add_column("Instance ID", style="cyan")
    table.add_column("Provider", style="magenta")
    table.add_column("GPU Type")
    table.add_column("Count", justify="right")
    table.add_column("Status")
    table.add_column("$/hr", justify="right")
    table.add_column("Util %", justify="right")

    running_cost = 0
    for instance in instances:
        status_color = "green" if instance.is_running else "red"
        util_color = "red" if instance.is_idle else "green"

        util_str = (
            f"[{util_color}]{instance.gpu_utilization:.0f}%[/]"
            if instance.gpu_utilization is not None
            else "-"
        )

        table.add_row(
            instance.instance_id[:20],
            instance.provider,
            instance.gpu_type.value,
            str(instance.gpu_count),
            f"[{status_color}]{instance.status}[/]",
            f"${instance.hourly_cost:.2f}",
            util_str,
        )

        if instance.is_running:
            running_cost += instance.hourly_cost

    console.print(table)
    console.print()

    # Summary
    running = len([i for i in instances if i.is_running])
    idle = len([i for i in instances if i.is_idle])

    console.print(Panel(
        f"[bold]Total Instances:[/] {len(instances)}\n"
        f"[bold]Running:[/] {running}  |  [bold]Idle:[/] [red]{idle}[/]\n"
        f"[bold]Current Burn Rate:[/] [yellow]${running_cost:.2f}/hr[/] | "
        f"[yellow]${running_cost * 24:.2f}/day[/] | "
        f"[yellow]${running_cost * 24 * 30:.2f}/month[/]",
        title="Summary",
    ))


@app.command()
def spend(
    days: int = typer.Option(30, "--days", "-d", help="Number of days to analyze"),
    providers: str = typer.Option("all", "--providers", "-p"),
    json_output: bool = typer.Option(False, "--json", "-j"),
):
    """Show spend analysis for a time period."""
    if providers == "all":
        provider_list = ["aws", "gcp", "azure", "vastai", "runpod", "lambda"]
    else:
        provider_list = [p.strip() for p in providers.split(",")]

    aggregator = create_aggregator(provider_list, demo=True)

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    summary = aggregator.get_summary(start_date, end_date)

    if json_output:
        console.print(json.dumps(summary.to_dict(), indent=2))
        return

    # Display summary
    console.print(Panel(
        f"[bold]Period:[/] {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}\n\n"
        f"[bold]Total Spend:[/] [yellow]${summary.total_cost:,.2f}[/]\n"
        f"[bold]GPU Hours:[/] {summary.total_gpu_hours:,.1f}\n"
        f"[bold]Avg $/GPU-hour:[/] ${summary.avg_cost_per_gpu_hour:.4f}\n\n"
        f"[bold]Idle Instances:[/] [red]{summary.idle_instances}[/] "
        f"({summary.idle_percentage:.1f}%)\n"
        f"[bold]Estimated Waste:[/] [red]${summary.estimated_waste:,.2f}[/]\n"
        f"[bold]Potential Savings:[/] [green]${summary.potential_savings:,.2f}[/]",
        title=f"Spend Summary ({days} days)",
    ))

    # By provider
    if summary.by_provider:
        table = Table(title="Spend by Provider")
        table.add_column("Provider")
        table.add_column("Cost", justify="right")
        table.add_column("Hours", justify="right")
        table.add_column("Instances", justify="right")
        table.add_column("Idle", justify="right")

        for p in summary.by_provider:
            table.add_row(
                p.provider,
                f"${p.total_cost:,.2f}",
                f"{p.total_hours:,.1f}",
                str(p.instance_count),
                f"[red]{p.idle_count}[/]" if p.idle_count > 0 else "0",
            )

        console.print(table)

    # By GPU type
    if summary.by_gpu_type:
        table = Table(title="Spend by GPU Type")
        table.add_column("GPU Type")
        table.add_column("Cost", justify="right")
        table.add_column("Hours", justify="right")
        table.add_column("$/GPU-hr", justify="right")

        for g in summary.by_gpu_type:
            table.add_row(
                g.gpu_type.value,
                f"${g.total_cost:,.2f}",
                f"{g.total_hours:,.1f}",
                f"${g.cost_per_gpu_hour:.4f}",
            )

        console.print(table)

    # Projections
    console.print(Panel(
        f"[bold]Daily Run Rate:[/] ${summary.daily_run_rate:,.2f}\n"
        f"[bold]Monthly Projection:[/] [yellow]${summary.monthly_projection:,.2f}[/]",
        title="Projections",
    ))


@app.command()
def waste(
    providers: str = typer.Option("all", "--providers", "-p"),
    min_savings: float = typer.Option(50.0, "--min", "-m", help="Minimum monthly savings to report"),
    json_output: bool = typer.Option(False, "--json", "-j"),
):
    """Find GPU waste and inefficiencies."""
    if providers == "all":
        provider_list = ["aws", "gcp", "azure", "vastai", "runpod", "lambda"]
    else:
        provider_list = [p.strip() for p in providers.split(",")]

    aggregator = create_aggregator(provider_list, demo=True)
    detector = WasteDetector(aggregator)

    report = detector.analyze()

    if json_output:
        console.print(json.dumps(report.to_dict(), indent=2))
        return

    # Summary
    console.print(Panel(
        f"[bold]Instances Analyzed:[/] {report.total_instances_analyzed}\n"
        f"[bold]Total Alerts:[/] {len(report.alerts)}\n"
        f"[bold]Critical/High:[/] [red]{len(report.critical_alerts) + len(report.high_alerts)}[/]\n\n"
        f"[bold]Daily Waste:[/] [red]${report.total_daily_waste:,.2f}[/]\n"
        f"[bold]Monthly Waste:[/] [red]${report.total_monthly_waste:,.2f}[/]\n"
        f"[bold]Annual Waste:[/] [red]${report.total_monthly_waste * 12:,.2f}[/]",
        title="Waste Report",
    ))

    # Alerts table
    filtered_alerts = [a for a in report.alerts if a.monthly_waste >= min_savings]

    if filtered_alerts:
        table = Table(title=f"Waste Alerts (>${min_savings:.0f}/month)")
        table.add_column("Severity")
        table.add_column("Type")
        table.add_column("Instance")
        table.add_column("Provider")
        table.add_column("Monthly Waste", justify="right")
        table.add_column("Recommendation")

        severity_colors = {
            "critical": "red bold",
            "high": "red",
            "medium": "yellow",
            "low": "white",
        }

        for alert in filtered_alerts:
            color = severity_colors.get(alert.severity.value, "white")
            table.add_row(
                f"[{color}]{alert.severity.value.upper()}[/]",
                alert.waste_type.value,
                alert.instance.instance_id[:15],
                alert.instance.provider,
                f"[red]${alert.monthly_waste:,.2f}[/]",
                alert.recommendation[:40] + "...",
            )

        console.print(table)
    else:
        console.print("[green]No significant waste detected![/]")


@app.command()
def forecast(
    months: int = typer.Option(1, "--months", "-m", help="Months to forecast"),
    providers: str = typer.Option("all", "--providers", "-p"),
    json_output: bool = typer.Option(False, "--json", "-j"),
):
    """Forecast future GPU costs."""
    if providers == "all":
        provider_list = ["aws", "gcp", "azure", "vastai", "runpod", "lambda"]
    else:
        provider_list = [p.strip() for p in providers.split(",")]

    aggregator = create_aggregator(provider_list, demo=True)
    predictor = CostPredictor(aggregator)

    now = datetime.now()
    if now.month + months > 12:
        target = now.replace(year=now.year + 1, month=(now.month + months) % 12)
    else:
        target = now.replace(month=now.month + months, day=1)

    forecast = predictor.forecast_month(target)

    if json_output:
        console.print(json.dumps(forecast.to_dict(), indent=2))
        return

    console.print(Panel(
        f"[bold]Forecast Period:[/] {forecast.period_start.strftime('%B %Y')}\n\n"
        f"[bold]Predicted Cost:[/] [yellow]${forecast.predicted_cost:,.2f}[/]\n"
        f"[bold]95% Confidence:[/] ${forecast.confidence_low:,.2f} - ${forecast.confidence_high:,.2f}\n\n"
        f"[bold]Model:[/] {forecast.model_type}\n"
        f"[bold]Data Points:[/] {forecast.data_points_used}",
        title="Cost Forecast",
    ))

    if forecast.by_provider:
        table = Table(title="Forecast by Provider")
        table.add_column("Provider")
        table.add_column("Predicted Cost", justify="right")

        for provider, cost in forecast.by_provider.items():
            table.add_row(provider, f"${cost:,.2f}")

        console.print(table)


@app.command()
def optimize(
    providers: str = typer.Option("all", "--providers", "-p"),
    quick_wins: bool = typer.Option(False, "--quick", "-q", help="Show only quick wins"),
    json_output: bool = typer.Option(False, "--json", "-j"),
):
    """Get optimization recommendations."""
    if providers == "all":
        provider_list = ["aws", "gcp", "azure", "vastai", "runpod", "lambda"]
    else:
        provider_list = [p.strip() for p in providers.split(",")]

    aggregator = create_aggregator(provider_list, demo=True)
    recommender = Recommender(aggregator)

    report = recommender.generate_recommendations()

    if quick_wins:
        recommendations = report.quick_wins
    else:
        recommendations = report.recommendations

    if json_output:
        console.print(json.dumps(report.to_dict(), indent=2))
        return

    console.print(Panel(
        f"[bold]Total Recommendations:[/] {len(report.recommendations)}\n"
        f"[bold]Quick Wins:[/] {len(report.quick_wins)}\n\n"
        f"[bold]Total Monthly Savings:[/] [green]${report.total_monthly_savings:,.2f}[/]\n"
        f"[bold]Annual Savings:[/] [green]${report.total_monthly_savings * 12:,.2f}[/]",
        title="Optimization Report",
    ))

    if recommendations:
        table = Table(title="Recommendations" if not quick_wins else "Quick Wins")
        table.add_column("Priority")
        table.add_column("Type")
        table.add_column("Title")
        table.add_column("Monthly Savings", justify="right")
        table.add_column("Effort")

        priority_colors = {
            "critical": "red bold",
            "high": "red",
            "medium": "yellow",
            "low": "white",
        }

        for rec in recommendations[:15]:  # Limit display
            color = priority_colors.get(rec.priority.value, "white")
            table.add_row(
                f"[{color}]{rec.priority.value.upper()}[/]",
                rec.rec_type.value,
                rec.title[:30],
                f"[green]${rec.monthly_savings:,.2f}[/]",
                rec.effort,
            )

        console.print(table)

        if len(recommendations) > 15:
            console.print(f"\n[dim]... and {len(recommendations) - 15} more recommendations[/]")


@app.command()
def estimate(
    model_size: float = typer.Argument(..., help="Model size in billions of parameters"),
    tokens: float = typer.Option(1.0, "--tokens", "-t", help="Training tokens in trillions"),
    gpu: str = typer.Option("a100-80gb", "--gpu", "-g", help="GPU type"),
    gpu_count: int = typer.Option(8, "--count", "-c", help="Number of GPUs"),
    json_output: bool = typer.Option(False, "--json", "-j"),
):
    """Estimate training costs for a model."""
    from computer.connect.base import GPUType

    gpu_map = {
        "a100-40gb": GPUType.A100_40GB,
        "a100-80gb": GPUType.A100_80GB,
        "h100": GPUType.H100_80GB,
        "h100-sxm": GPUType.H100_SXM,
        "rtx-4090": GPUType.RTX_4090,
    }

    gpu_type = gpu_map.get(gpu.lower(), GPUType.A100_80GB)

    predictor = CostPredictor()
    estimate = predictor.estimate_training_cost(
        model_size_params=model_size,
        gpu_type=gpu_type,
        gpu_count=gpu_count,
        training_tokens=tokens * 1e12,
    )

    if json_output:
        console.print(json.dumps(estimate.to_dict(), indent=2))
        return

    console.print(Panel(
        f"[bold]Model:[/] {model_size}B parameters\n"
        f"[bold]Training Tokens:[/] {tokens}T\n"
        f"[bold]Configuration:[/] {gpu_count}x {gpu_type.value}\n\n"
        f"[bold]Estimated Hours:[/] {estimate.estimated_hours:,.0f}\n"
        f"[bold]Estimated Cost:[/] [yellow]${estimate.estimated_cost:,.2f}[/]\n"
        f"[bold]Cost Range:[/] ${estimate.cost_range_low:,.2f} - ${estimate.cost_range_high:,.2f}",
        title="Training Cost Estimate",
    ))

    if estimate.provider_costs:
        table = Table(title="Provider Comparison")
        table.add_column("Provider")
        table.add_column("Cost", justify="right")

        sorted_providers = sorted(
            estimate.provider_costs.items(),
            key=lambda x: x[1]
        )

        for provider, cost in sorted_providers:
            is_cheapest = provider == estimate.cheapest_provider
            cost_str = f"[green]${cost:,.2f}[/]" if is_cheapest else f"${cost:,.2f}"
            table.add_row(
                f"[green]{provider}[/]" if is_cheapest else provider,
                cost_str,
            )

        console.print(table)

    console.print(f"\n[bold green]Cheapest:[/] {estimate.cheapest_provider} at ${estimate.cheapest_cost:,.2f}")


@app.command()
def version():
    """Show version information."""
    from computer import __version__
    console.print(f"Computer v{__version__}")
    console.print("GPU Cost Intelligence Platform")


def main():
    """Entry point."""
    app()


if __name__ == "__main__":
    main()
