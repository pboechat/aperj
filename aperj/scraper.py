"""Orchestrator - runs all source scrapers concurrently via asyncio."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any

from rich.console import Console

from aperj.models import Listing
from aperj.sources import get_all_sources
from aperj.sources.base import BaseSource

logger = logging.getLogger(__name__)


async def scrape_source(
    source: BaseSource, keywords: list[str], delay: float = 0.0
) -> list[Listing]:
    """Scrape a single source (used as an asyncio task)."""
    if delay > 0:
        await asyncio.sleep(delay)
    return await source.scrape(keywords)


def _listing_matches_keywords(listing: Listing, keywords_lower: list[str]) -> bool:
    """Return True if any keyword appears in the listing's text fields."""
    searchable = " ".join(
        s for s in (listing.title, listing.description, listing.address, listing.neighborhood)
        if s
    ).lower()
    return any(kw in searchable for kw in keywords_lower)


async def scrape_all(
    config: dict[str, Any],
    keywords: list[str],
    source_names: list[str] | None = None,
    progress: bool = True,
    filter_keywords: list[str] | None = None,
) -> list[Listing]:
    """Run all (or selected) sources concurrently and aggregate results.

    Parameters
    ----------
    config:
        Full application configuration dict.
    keywords:
        Search keywords to pass to every source.
    source_names:
        If provided, only run sources whose ``name`` is in this list.
    progress:
        If *True*, print a status line to stderr as each source finishes.
    filter_keywords:
        If provided, only keep listings whose text fields contain at
        least one of these keywords (case-insensitive).
    """
    sources = get_all_sources(config)

    if source_names:
        allowed = set(source_names)
        sources = [s for s in sources if s.name in allowed]

    total = len(sources)
    logger.info(
        "Launching %d source(s) concurrently: %s",
        total,
        ", ".join(s.name for s in sources),
    )

    console = Console(stderr=True) if progress else None
    completed_count = 0
    lock = asyncio.Lock()

    async def _scrape_with_progress(
        source: BaseSource, keywords: list[str], delay: float
    ) -> list[Listing]:
        nonlocal completed_count
        listings = await scrape_source(source, keywords, delay=delay)
        async with lock:
            completed_count += 1
            if console is not None:
                console.print(
                    f"Scraping source [cyan]{completed_count}/{total}[/cyan] "
                    f"([magenta]{source.name}[/magenta]) "
                    f"- listings [green]{len(listings)}[/green]"
                )
        return listings

    tasks = [
        asyncio.create_task(
            _scrape_with_progress(s, keywords, delay=i * random.uniform(0.3, 0.8))
        )
        for i, s in enumerate(sources)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_listings: list[Listing] = []
    for source, result in zip(sources, results):
        if isinstance(result, BaseException):
            logger.error("Source %s raised an exception: %s", source.name, result)
        else:
            all_listings.extend(result)

    logger.info("Total listings collected: %d", len(all_listings))

    if filter_keywords:
        kw_lower = [k.lower() for k in filter_keywords]
        before = len(all_listings)
        all_listings = [l for l in all_listings if _listing_matches_keywords(l, kw_lower)]
        dropped = before - len(all_listings)
        if dropped:
            logger.info(
                "Keyword filter: kept %d/%d listings matching %s.",
                len(all_listings), before, filter_keywords,
            )

    return all_listings


def filter_listings(
    listings: list[Listing],
    *,
    min_price_brl: int | None = None,
    max_price_brl: int | None = None,
    min_condo_brl: int | None = None,
    max_condo_brl: int | None = None,
    min_iptu_brl: int | None = None,
    max_iptu_brl: int | None = None,
    min_area_m2: float | None = None,
    max_area_m2: float | None = None,
    min_bedrooms: int | None = None,
    max_bedrooms: int | None = None,
    min_suites: int | None = None,
    max_suites: int | None = None,
    min_bathrooms: int | None = None,
    max_bathrooms: int | None = None,
    min_parking: int | None = None,
    max_parking: int | None = None,
    listing_type: str | None = None,
    property_types: list[str] | None = None,
    neighborhoods: list[str] | None = None,
) -> list[Listing]:
    """Apply post-scrape filters to a list of listings.

    Listings with ``None`` in a filtered field are **excluded** when a
    min/max constraint is set (we can't verify they satisfy it).
    """
    before = len(listings)

    def _ok(listing: Listing) -> bool:  # noqa: C901
        # ── price ─────────────────────────────────────────────────
        if min_price_brl is not None:
            if listing.price_brl is None or listing.price_brl < min_price_brl:
                return False
        if max_price_brl is not None:
            if listing.price_brl is None or listing.price_brl > max_price_brl:
                return False
        # ── condo fee ─────────────────────────────────────────────
        if min_condo_brl is not None:
            if listing.condo_fee_brl is None or listing.condo_fee_brl < min_condo_brl:
                return False
        if max_condo_brl is not None:
            if listing.condo_fee_brl is None or listing.condo_fee_brl > max_condo_brl:
                return False
        # ── IPTU ──────────────────────────────────────────────────
        if min_iptu_brl is not None:
            if listing.iptu_brl is None or listing.iptu_brl < min_iptu_brl:
                return False
        if max_iptu_brl is not None:
            if listing.iptu_brl is None or listing.iptu_brl > max_iptu_brl:
                return False
        # ── area ──────────────────────────────────────────────────
        if min_area_m2 is not None:
            if listing.area_m2 is None or listing.area_m2 < min_area_m2:
                return False
        if max_area_m2 is not None:
            if listing.area_m2 is None or listing.area_m2 > max_area_m2:
                return False
        # ── bedrooms ──────────────────────────────────────────────
        if min_bedrooms is not None:
            if listing.bedrooms is None or listing.bedrooms < min_bedrooms:
                return False
        if max_bedrooms is not None:
            if listing.bedrooms is None or listing.bedrooms > max_bedrooms:
                return False
        # ── suites ────────────────────────────────────────────────
        if min_suites is not None:
            if listing.suites is None or listing.suites < min_suites:
                return False
        if max_suites is not None:
            if listing.suites is None or listing.suites > max_suites:
                return False
        # ── bathrooms ─────────────────────────────────────────────
        if min_bathrooms is not None:
            if listing.bathrooms is None or listing.bathrooms < min_bathrooms:
                return False
        if max_bathrooms is not None:
            if listing.bathrooms is None or listing.bathrooms > max_bathrooms:
                return False
        # ── parking ───────────────────────────────────────────────
        if min_parking is not None:
            if listing.parking_spots is None or listing.parking_spots < min_parking:
                return False
        if max_parking is not None:
            if listing.parking_spots is None or listing.parking_spots > max_parking:
                return False
        # ── listing type ──────────────────────────────────────────
        if listing_type is not None:
            if listing.listing_type.value != listing_type:
                return False
        # ── property type ─────────────────────────────────────────
        if property_types is not None:
            if listing.property_type.value not in property_types:
                return False
        # ── neighborhood ──────────────────────────────────────────
        if neighborhoods is not None:
            nb_lower = listing.neighborhood.lower()
            if not any(n.lower() in nb_lower for n in neighborhoods):
                return False
        return True

    filtered = [l for l in listings if _ok(l)]
    dropped = before - len(filtered)
    if dropped:
        logger.info("Post-scrape filters: kept %d/%d listings.", len(filtered), before)
    return filtered
