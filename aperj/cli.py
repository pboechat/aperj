"""Command-line interface for aperj."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from aperj import __version__
from aperj.config import DEFAULT_CONFIG_PATH, get_keywords, init_config, load_config
from aperj.models import ListingType, PropertyType
from aperj.output import print_rich_table, write_csv
from aperj.scraper import filter_listings, scrape_all

logger = logging.getLogger("aperj")


def _configure_logging(verbosity: int) -> None:
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )


def main(argv: list[str] | None = None) -> None:
    """Entry-point for the ``aperj`` console script."""
    parser = argparse.ArgumentParser(
        prog="aperj",
        description=(
            "Apê RJ - scrape apartment/flat listings from multiple "
            "Brazilian real-estate websites."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--init-config",
        action="store_true",
        default=False,
        help="Create a default config file and exit.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help=f"Path to config file (default: {DEFAULT_CONFIG_PATH}).",
    )
    parser.add_argument(
        "--keywords", "-k",
        nargs="+",
        default=None,
        help="Search keywords (merged with config keywords).",
    )
    parser.add_argument(
        "--sources", "-s",
        nargs="+",
        default=None,
        help="Only scrape these sources (by name).",
    )
    parser.add_argument(
        "--export",
        type=Path,
        default=None,
        metavar="FILE",
        help="Write results to a CSV file.",
    )
    parser.add_argument(
        "--no-rich",
        action="store_true",
        default=False,
        help="Suppress pretty-printed table output.",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=None,
        help="Override max results per source.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="count",
        default=0,
        help="Increase logging verbosity (-v for INFO, -vv for DEBUG).",
    )
    parser.add_argument(
        "--flaresolverr",
        type=str,
        default=None,
        metavar="URL",
        help="FlareSolverr endpoint for Cloudflare-protected sites (e.g. http://localhost:8191/v1).",
    )

    # ── post-scrape filters ───────────────────────────────────────────
    filt = parser.add_argument_group("filters", "Post-scrape listing filters")
    filt.add_argument(
        "--min-price", type=float, default=None, metavar="BRL",
        help="Minimum price in BRL (e.g. 200000).",
    )
    filt.add_argument(
        "--max-price", type=float, default=None, metavar="BRL",
        help="Maximum price in BRL (e.g. 800000).",
    )
    filt.add_argument(
        "--min-condo", type=float, default=None, metavar="BRL",
        help="Minimum condo fee in BRL.",
    )
    filt.add_argument(
        "--max-condo", type=float, default=None, metavar="BRL",
        help="Maximum condo fee in BRL.",
    )
    filt.add_argument(
        "--min-iptu", type=float, default=None, metavar="BRL",
        help="Minimum IPTU in BRL.",
    )
    filt.add_argument(
        "--max-iptu", type=float, default=None, metavar="BRL",
        help="Maximum IPTU in BRL.",
    )
    filt.add_argument(
        "--min-area-m2", type=float, default=None, metavar="M2",
        help="Minimum area in square metres.",
    )
    filt.add_argument(
        "--max-area-m2", type=float, default=None, metavar="M2",
        help="Maximum area in square metres.",
    )
    filt.add_argument(
        "--min-bedrooms", type=int, default=None,
        help="Minimum number of bedrooms.",
    )
    filt.add_argument(
        "--max-bedrooms", type=int, default=None,
        help="Maximum number of bedrooms.",
    )
    filt.add_argument(
        "--min-suites", type=int, default=None,
        help="Minimum number of suites.",
    )
    filt.add_argument(
        "--max-suites", type=int, default=None,
        help="Maximum number of suites.",
    )
    filt.add_argument(
        "--min-bathrooms", type=int, default=None,
        help="Minimum number of bathrooms.",
    )
    filt.add_argument(
        "--max-bathrooms", type=int, default=None,
        help="Maximum number of bathrooms.",
    )
    filt.add_argument(
        "--min-parking", type=int, default=None,
        help="Minimum number of parking spots.",
    )
    filt.add_argument(
        "--max-parking", type=int, default=None,
        help="Maximum number of parking spots.",
    )
    filt.add_argument(
        "--listing-type", type=str, default=None,
        choices=[t.value for t in ListingType],
        help="Keep only listings of this type (venda/aluguel).",
    )
    filt.add_argument(
        "--property-type", type=str, nargs="+", default=None,
        metavar="TYPE",
        help="Keep only these property types (e.g. apartamento cobertura).",
    )
    filt.add_argument(
        "--neighborhood", type=str, nargs="+", default=None,
        metavar="NAME",
        help="Keep only listings in these neighborhoods (case-insensitive substring match).",
    )
    args = parser.parse_args(argv)

    _configure_logging(args.verbose)

    # --init-config: create config and exit
    if args.init_config:
        path = init_config(args.config)
        print(f"Config initialised at {path}")
        return

    # Load config
    config = load_config(args.config)

    # CLI overrides
    if args.max_results is not None:
        config["max_results_per_source"] = args.max_results
    if args.flaresolverr is not None:
        config["flaresolverr_url"] = args.flaresolverr

    keywords = get_keywords(config, args.keywords)

    # CLI --keywords act as a post-scrape filter; config keywords are search terms.
    filter_keywords = args.keywords or []
    logger.info("Search keywords: %s", keywords)
    if filter_keywords:
        logger.info("Filter keywords: %s", filter_keywords)

    # Run the async scraper
    listings = asyncio.run(
        scrape_all(
            config, keywords,
            source_names=args.sources,
            progress=not args.no_rich,
            filter_keywords=filter_keywords,
        )
    )

    # Post-scrape filters
    listings = filter_listings(
        listings,
        min_price_brl=int(args.min_price * 100) if args.min_price is not None else None,
        max_price_brl=int(args.max_price * 100) if args.max_price is not None else None,
        min_condo_brl=int(args.min_condo * 100) if args.min_condo is not None else None,
        max_condo_brl=int(args.max_condo * 100) if args.max_condo is not None else None,
        min_iptu_brl=int(args.min_iptu * 100) if args.min_iptu is not None else None,
        max_iptu_brl=int(args.max_iptu * 100) if args.max_iptu is not None else None,
        min_area_m2=args.min_area_m2,
        max_area_m2=args.max_area_m2,
        min_bedrooms=args.min_bedrooms,
        max_bedrooms=args.max_bedrooms,
        min_suites=args.min_suites,
        max_suites=args.max_suites,
        min_bathrooms=args.min_bathrooms,
        max_bathrooms=args.max_bathrooms,
        min_parking=args.min_parking,
        max_parking=args.max_parking,
        listing_type=args.listing_type,
        property_types=args.property_type,
        neighborhoods=args.neighborhood,
    )

    # Output
    if not args.no_rich:
        print_rich_table(listings)

    csv_path = args.export or config.get("output", {}).get("csv_path")
    if csv_path:
        written = write_csv(listings, csv_path)
        logger.info("Results written to %s", written)

    if not listings:
        sys.exit(1)
