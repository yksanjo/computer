#!/usr/bin/env python3
"""
Demo script for Computer - GPU Cost Intelligence Platform.

Run this to see the platform in action with demo data.
"""

import json
from datetime import datetime, timedelta

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

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


console = Console()


def main():
    console.print(Panel.fit(
        "[bold blue]Computer[/bold blue]\n"
        "GPU Cost Intelligence Platform\n"
        "[dim]Demo Mode - Using simulated data[/dim]",
        border_style="blue",
    ))
    console.print()

    # Setup aggregator with all providers
    console.print("[bold]1. Connecting to providers...[/bold]")
    aggregator = SpendAggregator()
    aggregator.add_connectors([
        AWSConnector(),
        GCPConnector(),
        AzureConnector(),
        VastAIConnector(),
        RunPodConnector(),
        LambdaConnector(),
    ])
    console.print("   [green]Connected to 6 providers (demo mode)[/green]\n")

    # List instances
    console.print("[bold]2. Fetching GPU instances...[/bold]")
    instances = aggregator.get_all_instances()

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
    console.print()

    # Spend analysis
    console.print("[bold]3. Analyzing spend (last 30 days)...[/bold]")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    summary = aggregator.get_summary(start_date, end_date)

    console.print(Panel(
        f"[bold]Period:[/] {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}\n\n"
        f"[bold]Total Spend:[/] [yellow]${summary.total_cost:,.2f}[/]\n"
        f"[bold]GPU Hours:[/] {summary.total_gpu_hours:,.1f}\n"
        f"[bold]Avg $/GPU-hour:[/] ${summary.avg_cost_per_gpu_hour:.4f}\n\n"
        f"[bold]Estimated Waste:[/] [red]${summary.estimated_waste:,.2f}[/]\n"
        f"[bold]Potential Savings:[/] [green]${summary.potential_savings:,.2f}[/]",
        title="Spend Summary",
    ))
    console.print()

    # Waste detection
    console.print("[bold]4. Detecting waste...[/bold]")
    detector = WasteDetector(aggregator)
    waste_report = detector.analyze()

    console.print(Panel(
        f"[bold]Instances Analyzed:[/] {waste_report.total_instances_analyzed}\n"
        f"[bold]Total Alerts:[/] {len(waste_report.alerts)}\n"
        f"[bold]Critical/High:[/] [red]{len(waste_report.critical_alerts) + len(waste_report.high_alerts)}[/]\n\n"
        f"[bold]Daily Waste:[/] [red]${waste_report.total_daily_waste:,.2f}[/]\n"
        f"[bold]Monthly Waste:[/] [red]${waste_report.total_monthly_waste:,.2f}[/]\n"
        f"[bold]Annual Waste:[/] [red]${waste_report.total_monthly_waste * 12:,.2f}[/]",
        title="Waste Report",
    ))

    if waste_report.alerts:
        table = Table(title="Top Waste Alerts")
        table.add_column("Severity")
        table.add_column("Type")
        table.add_column("Instance")
        table.add_column("Monthly Waste", justify="right")

        for alert in waste_report.alerts[:5]:
            severity_colors = {
                "critical": "red bold",
                "high": "red",
                "medium": "yellow",
                "low": "white",
            }
            color = severity_colors.get(alert.severity.value, "white")
            table.add_row(
                f"[{color}]{alert.severity.value.upper()}[/]",
                alert.waste_type.value,
                alert.instance.instance_id[:15],
                f"[red]${alert.monthly_waste:,.2f}[/]",
            )

        console.print(table)
    console.print()

    # Forecast
    console.print("[bold]5. Forecasting next month...[/bold]")
    predictor = CostPredictor(aggregator)
    now = datetime.now()
    if now.month == 12:
        target = now.replace(year=now.year + 1, month=1, day=1)
    else:
        target = now.replace(month=now.month + 1, day=1)

    forecast = predictor.forecast_month(target)

    console.print(Panel(
        f"[bold]Forecast Period:[/] {forecast.period_start.strftime('%B %Y')}\n\n"
        f"[bold]Predicted Cost:[/] [yellow]${forecast.predicted_cost:,.2f}[/]\n"
        f"[bold]95% Confidence:[/] ${forecast.confidence_low:,.2f} - ${forecast.confidence_high:,.2f}",
        title="Cost Forecast",
    ))
    console.print()

    # Recommendations
    console.print("[bold]6. Generating recommendations...[/bold]")
    recommender = Recommender(aggregator)
    opt_report = recommender.generate_recommendations()

    console.print(Panel(
        f"[bold]Total Recommendations:[/] {len(opt_report.recommendations)}\n"
        f"[bold]Quick Wins:[/] {len(opt_report.quick_wins)}\n\n"
        f"[bold]Total Monthly Savings:[/] [green]${opt_report.total_monthly_savings:,.2f}[/]\n"
        f"[bold]Annual Savings:[/] [green]${opt_report.total_monthly_savings * 12:,.2f}[/]",
        title="Optimization Report",
    ))

    if opt_report.recommendations:
        table = Table(title="Top Recommendations")
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

        for rec in opt_report.recommendations[:5]:
            color = priority_colors.get(rec.priority.value, "white")
            table.add_row(
                f"[{color}]{rec.priority.value.upper()}[/]",
                rec.rec_type.value,
                rec.title[:25],
                f"[green]${rec.monthly_savings:,.2f}[/]",
                rec.effort,
            )

        console.print(table)
    console.print()

    # Training cost estimate
    console.print("[bold]7. Training cost estimate (7B model)...[/bold]")
    estimate = predictor.estimate_training_cost(
        model_size_params=7.0,
        gpu_type=instances[0].gpu_type if instances else None,
        gpu_count=8,
        training_tokens=2e12,
    )

    console.print(Panel(
        f"[bold]Model:[/] 7B parameters\n"
        f"[bold]Training Tokens:[/] 2T\n"
        f"[bold]Configuration:[/] 8x GPUs\n\n"
        f"[bold]Estimated Hours:[/] {estimate.estimated_hours:,.0f}\n"
        f"[bold]Estimated Cost:[/] [yellow]${estimate.estimated_cost:,.2f}[/]\n"
        f"[bold]Cheapest Provider:[/] [green]{estimate.cheapest_provider}[/] at ${estimate.cheapest_cost:,.2f}",
        title="Training Cost Estimate",
    ))
    console.print()

    # Final summary
    console.print(Panel.fit(
        f"[bold green]Summary[/bold green]\n\n"
        f"You're spending [yellow]${running_cost * 24 * 30:,.2f}/month[/yellow] on GPU compute.\n\n"
        f"Computer found:\n"
        f"  - [red]${waste_report.total_monthly_waste:,.2f}/month[/red] in waste\n"
        f"  - [green]${opt_report.total_monthly_savings:,.2f}/month[/green] in potential savings\n\n"
        f"[bold]That's [green]${opt_report.total_monthly_savings * 12:,.2f}/year[/green] you could save![/bold]",
        border_style="green",
    ))


if __name__ == "__main__":
    main()
