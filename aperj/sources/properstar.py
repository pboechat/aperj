"""Scraper for Nestoria Brazil (Properstar parent) - https://www.nestoria.com.br

Properstar (properstar.com) is behind an Azure WAF that cannot be bypassed.
Nestoria is the same parent company (ListGlobally / Mitula Group) and serves
the same aggregated listings without a WAF, so we scrape Nestoria instead.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote_plus

from aperj.models import Listing, parse_price_brl
from aperj.sources.base import BaseSource


class ProperstarSource(BaseSource):
    name = "properstar"
    base_url = "https://www.nestoria.com.br"

    async def _do_scrape(self, keywords: list[str]) -> list[Listing]:
        path = "/rio-de-janeiro/comprar"
        queries = keywords or [""]
        all_listings: list[Listing] = []
        seen_urls: set[str] = set()

        async with self._build_session() as session:
            for kw in queries:
                url = f"{self.base_url}{path}?q={quote_plus(kw)}" if kw else f"{self.base_url}{path}"
                html = await self._fetch(session, url)
                soup = self._soup(html)
                batch = self._parse_page(soup)
                for listing in batch:
                    if listing.url not in seen_urls:
                        seen_urls.add(listing.url)
                        all_listings.append(listing)

        return all_listings

    def _parse_page(self, soup: Any) -> list[Listing]:
        listings: list[Listing] = []

        for item in soup.select("ul[class*='result'] > li")[: self.max_results]:
            link = item.select_one("a[data-href]")
            if link is None:
                continue

            title_el = item.select_one(".listing__title__text")
            price_el = item.select_one(".result__details__price")
            location_el = item.select_one(".locationFacet")
            rooms_el = item.select_one(".rooms")
            baths_el = item.select_one(".bathrooms")

            # Rich data attributes on the <a> tag
            data_price = link.get("data-price", "")
            data_rooms = link.get("data-rooms", "")
            data_location = link.get("data-location", "")

            # Build detail URL
            href = link.get("data-href", "")
            if href.startswith("/"):
                href = self.base_url + href

            # Extract area from keywords text, e.g. "65 m²"
            kw_el = item.select_one(".listing__keywords")
            area = ""
            if kw_el:
                m = re.search(r"(\d[\d.,]*)\s*m²", kw_el.get_text())
                if m:
                    area = m.group(1).replace(",", ".")

            listings.append(
                Listing(
                    title=title_el.get_text(strip=True) if title_el else "",
                    price_brl=parse_price_brl(data_price) if data_price else parse_price_brl(
                        price_el.get_text(strip=True) if price_el else ""
                    ),
                    address=data_location or (location_el.get_text(strip=True) if location_el else ""),
                    area_m2=area,
                    bedrooms=data_rooms or "",
                    bathrooms=baths_el.get_text(strip=True).split()[0] if baths_el else "",
                    url=href,
                    source=self.name,
                )
            )
        return listings
