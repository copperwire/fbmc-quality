from datetime import datetime, timedelta

import typer
from fbmc_quality.jao_data.fetch_jao_data import fetch_jao_dataframe_timeseries

app = typer.Typer()


@app.command()
def main(
    from_date: datetime = typer.Argument(..., help="From date (required) - will be converted to date"),
    to_date: datetime = typer.Argument(..., help="To date (required) - will be converted to date"),
):
    # Check if the folder path is provided, use default if not

    typer.echo("Storing JAO data ")
    typer.echo(f"From Date: {from_date}")
    typer.echo(f"To Date: {to_date}")

    current = from_date

    while current < to_date:
        _ = fetch_jao_dataframe_timeseries(current, current + timedelta(days=1))
        typer.echo(f"Stored data for {current}")
        current += timedelta(days=1)


if __name__ == "__main__":
    app()
