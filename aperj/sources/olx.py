"""Scraper for OLX - https://www.olx.com.br"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote_plus

from aperj.models import Listing, parse_price_brl
from aperj.sources.base import BaseSource


class OlxSource(BaseSource):
    name = "olx"
    base_url = "https://www.olx.com.br"

    async def _do_scrape(self, keywords: list[str]) -> list[Listing]:
        base = f"{self.base_url}/imoveis/venda/estado-rj/rio-de-janeiro-e-regiao"
        queries = keywords or [""]
        all_listings: list[Listing] = []
        seen_urls: set[str] = set()

        async with self._build_session() as session:
            for kw in queries:
                url = f"{base}?q={quote_plus(kw)}" if kw else base
                html = await self._fetch(session, url)
                soup = self._soup(html)

                # OLX is a Next.js app – structured data lives in __NEXT_DATA__.
                next_data = soup.select_one("script#__NEXT_DATA__")
                if next_data and next_data.string:
                    batch = self._parse_next_data(json.loads(next_data.string))
                else:
                    batch = self._parse_html(soup)

                for listing in batch:
                    if listing.url not in seen_urls:
                        seen_urls.add(listing.url)
                        all_listings.append(listing)

        return all_listings

    def _parse_next_data(self, data: dict[str, Any]) -> list[Listing]:
        ads = data.get("props", {}).get("pageProps", {}).get("ads", [])
        listings: list[Listing] = []
        for ad in ads[: self.max_results]:
            props = {p["name"]: p["value"] for p in ad.get("properties", []) if "name" in p}
            area = props.get("size", "")
            if area:
                area = "".join(c for c in area if c.isdigit() or c == ".")
            listings.append(
                Listing(
                    title=ad.get("subject", "") or ad.get("title", ""),
                    price_brl=parse_price_brl(ad.get("price", "") or ad.get("priceValue", "")),
                    address=ad.get("location", ""),
                    neighborhood=(ad.get("locationDetails") or {}).get("neighbourhood", ""),
                    area_m2=area,
                    bedrooms=str(props.get("rooms", "")),
                    bathrooms=str(props.get("bathrooms", "")),
                    parking_spots=str(props.get("garage_spaces", "")),
                    url=ad.get("url", ""),
                    source=self.name,
                )
            )
        return listings

    def _parse_html(self, soup: "BeautifulSoup") -> list[Listing]:  # type: ignore[name-defined]
        listings: list[Listing] = []
        for card in soup.select(
            "[data-ds-component='DS-AdCard'], #ad-list li, [class*='adCard']"
        )[: self.max_results]:
            title_el = card.select_one("h2, [class*='title']")
            price_el = card.select_one("[class*='price'], [class*='Price']")
            link_el = card.select_one("a[href]")
            addr_el = card.select_one("[class*='location'], [class*='detail']")

            href = ""
            if link_el and link_el.get("href"):
                href = link_el["href"]
                if href.startswith("/"):
                    href = self.base_url + href

            listings.append(Listing(
                title=title_el.get_text(strip=True) if title_el else "",
                price_brl=parse_price_brl(price_el.get_text(strip=True) if price_el else ""),
                address=addr_el.get_text(strip=True) if addr_el else "",
                url=href,
                source=self.name,
            ))
        return listings
