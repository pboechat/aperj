"""Scraper for MRV - https://www.mrv.com.br

MRV's listing page is a client-rendered SPA so the HTML contains no data.
Instead we:
  1. Fetch the sitemap to discover individual property-page URLs for RJ.
  2. Fetch each property page (plain HTML, no JS needed).
  3. Extract the ``<script type="application/ld+json">`` block that contains
     a ``schema.org/RealEstateListing`` with name, address, area, rooms, etc.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from aperj.models import Listing, PropertyType, parse_price_brl
from aperj.sources.base import BaseSource

_SITEMAP_URL = "https://www.mrv.com.br/sitemap.xml"
# Only property detail pages (state/city/slug); skip city-level pages.
_DETAIL_RE = re.compile(
    r"https://www\.mrv\.com\.br/imoveis/rio-de-janeiro/[^/]+/[^<]+"
)


class MrvSource(BaseSource):
    name = "mrv"
    base_url = "https://www.mrv.com.br"

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_jsonld_listing(html: str) -> dict[str, Any] | None:
        """Return the first ``RealEstateListing`` JSON-LD block, or *None*."""
        for m in re.finditer(
            r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
            html,
            re.DOTALL,
        ):
            try:
                data = json.loads(m.group(1))
            except (json.JSONDecodeError, ValueError):
                continue
            if data.get("@type") == "RealEstateListing":
                return data
        return None

    def _jsonld_to_listing(self, data: dict[str, Any], page_url: str) -> Listing:
        about: dict[str, Any] = data.get("about") or {}
        offers: dict[str, Any] = data.get("offers") or {}
        floor_size: dict[str, Any] = about.get("floorSize") or {}

        # City from the breadcrumb or URL
        city = ""
        breadcrumb = page_url.rstrip("/").split("/")
        if len(breadcrumb) >= 5:
            city = breadcrumb[-2].replace("-", " ").title()

        # Property type heuristic
        ptype = PropertyType.APARTMENT
        slug = page_url.rsplit("/", 1)[-1].lower()
        if "lote" in slug:
            ptype = PropertyType.OTHER
        elif "casa" in slug:
            ptype = PropertyType.HOUSE

        area: float | None = None
        try:
            area = float(floor_size.get("value", ""))
        except (ValueError, TypeError):
            pass

        bedrooms: int | None = None
        try:
            bedrooms = int(about.get("numberOfRooms", ""))
        except (ValueError, TypeError):
            pass

        return Listing(
            title=data.get("name", ""),
            description=(data.get("description") or "")[:500],
            url=data.get("url") or page_url,
            source=self.name,
            address=about.get("address", ""),
            city=city,
            state="RJ",
            property_type=ptype,
            area_m2=area,
            bedrooms=bedrooms,
            price_brl=parse_price_brl(str(offers.get("price", ""))),
        )

    # ------------------------------------------------------------------
    # scrape
    # ------------------------------------------------------------------

    async def _do_scrape(self, keywords: list[str]) -> list[Listing]:
        async with self._build_session() as session:
            sitemap_xml = await self._fetch(session, _SITEMAP_URL)

        detail_urls = _DETAIL_RE.findall(sitemap_xml)[: self.max_results]
        if not detail_urls:
            self.logger.warning("No RJ property URLs found in MRV sitemap.")
            return []

        self.logger.info("MRV sitemap: %d RJ property pages to fetch.", len(detail_urls))

        listings: list[Listing] = []

        async def _fetch_detail(url: str) -> None:
            try:
                async with self._build_session() as session:
                    html = await self._fetch(session, url)
                data = self._parse_jsonld_listing(html)
                if data:
                    listings.append(self._jsonld_to_listing(data, url))
                else:
                    self.logger.debug("No RealEstateListing JSON-LD on %s", url)
            except Exception:
                self.logger.debug("Failed to fetch %s", url, exc_info=True)

        # Fetch detail pages with limited concurrency
        sem = asyncio.Semaphore(5)

        async def _bounded(url: str) -> None:
            async with sem:
                await _fetch_detail(url)

        await asyncio.gather(*[_bounded(u) for u in detail_urls])
        return listings
