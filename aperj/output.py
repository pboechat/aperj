"""Output formatters - rich console table and CSV file writer."""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from rich.console import Console
from rich.table import Table

from aperj.models import Listing

logger = logging.getLogger(__name__)


def print_rich_table(listings: list[Listing]) -> None:
    """Pretty-print listings as a Rich table to stdout."""
    console = Console()

    if not listings:
        console.print("[bold yellow]No listings found.[/bold yellow]")
        return

    table = Table(
        title="[bold cyan]Apê RJ - Apartment Listings[/bold cyan]",
        show_lines=True,
        expand=True,
    )
    table.add_column("#", style="dim", width=4)
    table.add_column("Source", style="magenta", width=14)
    table.add_column("Title", style="bold", max_width=40)
    table.add_column("Price", style="green", width=16)
    table.add_column("Neighborhood", width=18)
    table.add_column("Area (m²)", width=10)
    table.add_column("Beds", width=5)
    table.add_column("Baths", width=5)
    table.add_column("Parking", width=7)
    table.add_column("URL", style="blue underline", max_width=50, overflow="fold")

    for idx, listing in enumerate(listings, start=1):
        table.add_row(
            str(idx),
            listing.source,
            listing.title or "-",
            listing.fmt_price() or "-",
            listing.fmt_location() or "-",
            listing.fmt_area() or "-",
            listing.fmt_bedrooms() or "-",
            str(listing.bathrooms) if listing.bathrooms is not None else "-",
            listing.fmt_parking() or "-",
            listing.url or "-",
        )

    console.print(table)
    console.print(f"\n[bold]{len(listings)}[/bold] listing(s) found.\n")


def write_csv(listings: list[Listing], path: str | Path) -> Path:
    """Write listings to a CSV file and return the resolved path."""
    path = Path(path)
    logger.info("Writing %d listing(s) to %s", len(listings), path)

    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(Listing.csv_header())
        for listing in listings:
            writer.writerow(listing.csv_row())

    logger.info("CSV written successfully.")
    return path
