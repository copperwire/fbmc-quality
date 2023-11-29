from datetime import datetime, timedelta

import typer
from pytz import timezone

from fbmc_quality.entsoe_data.fetch_entsoe_data import fetch_net_position_from_crossborder_flows

app = typer.Typer()


@app.command()
def main(
    from_date: datetime = typer.Argument(..., help="From date (required) - will be converted to date"),
    to_date: datetime = typer.Argument(..., help="To date (required) - will be converted to date"),
):
    # Check if the folder path is provided, use default if not

    typer.echo("Storing ENTSOE Transparency data ")
    typer.echo(f"From Date: {from_date}")
    typer.echo(f"To Date: {to_date}")

    utc = timezone("utc")
    from_date = utc.localize(from_date)
    to_date = utc.localize(to_date)
    current = from_date

    while current < to_date:
        _ = fetch_net_position_from_crossborder_flows(current, current + timedelta(days=1))
        typer.echo(f"Stored data for {current}")
        current += timedelta(days=1)


if __name__ == "__main__":
    app()
