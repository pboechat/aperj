"""Scraper for Imoveis.net - https://www.imoveis.net"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote_plus

from aperj.models import Listing, parse_price_brl
from aperj.sources.base import BaseSource


class ImoveisNetSource(BaseSource):
    name = "imoveisnet"
    base_url = "https://www.imoveis.net"

    async def _do_scrape(self, keywords: list[str]) -> list[Listing]:
        queries = keywords or [""]
        all_listings: list[Listing] = []
        seen_urls: set[str] = set()

        async with self._build_session() as session:
            for kw in queries:
                url = f"{self.base_url}/rio-de-janeiro/venda?q={quote_plus(kw)}"
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

        for card in soup.select(
            ".property-card, .listing-item, .result-item"
        )[:self.max_results]:
            title_el = card.select_one("h2, h3, [class*='title']")
            price_el = card.select_one("[class*='price'], [class*='valor']")
            link_el = card.select_one("a[href]")

            # Address: prefer data-address attribute, fallback to text
            addr = ""
            addr_el = card.select_one("[data-address]")
            if addr_el:
                addr = addr_el.get("data-address", "")
            else:
                addr_el = card.select_one(
                    "li.listing-address, [class*='address']"
                )
                if addr_el:
                    addr = addr_el.get_text(strip=True)

            # Features
            bedrooms = bathrooms = area = parking = ""
            for el in card.select(
                "[class*='detail'] li, [class*='feature'] li"
            ):
                txt = el.get_text(strip=True).lower()
                if "quarto" in txt or "dorm" in txt:
                    m = re.match(r"(\d+)", txt)
                    bedrooms = m.group(1) if m else ""
                elif "banheiro" in txt:
                    m = re.match(r"(\d+)", txt)
                    bathrooms = m.group(1) if m else ""
                elif "m²" in txt or "m2" in txt:
                    m = re.match(r"(\d[\d.]*)", txt)
                    area = m.group(1) if m else ""
                elif "vaga" in txt or "garage" in txt:
                    m = re.match(r"(\d+)", txt)
                    parking = m.group(1) if m else ""

            href = ""
            if link_el and link_el.get("href"):
                href = link_el["href"]
                if href.startswith("/"):
                    href = self.base_url + href

            listings.append(Listing(
                title=title_el.get_text(strip=True) if title_el else "",
                price_brl=parse_price_brl(price_el.get_text(strip=True) if price_el else ""),
                address=addr,
                area_m2=area,
                bedrooms=bedrooms,
                bathrooms=bathrooms,
                parking_spots=parking,
                url=href,
                source=self.name,
            ))

        # Fallback: if redirect to single-listing page, parse that
        if not listings:
            article = soup.select_one("article.ad_listing")
            if article:
                title_el = article.select_one("h1.entry-title")
                price_el = article.select_one(".cp_price")
                loc_el = article.select_one("[data-address]")
                addr = loc_el.get("data-address", "") if loc_el else ""
                link_el = article.select_one("[data-permalink]")
                href = link_el.get("data-permalink", "") if link_el else ""

                listings.append(Listing(
                    title=title_el.get_text(strip=True) if title_el else "",
                    price_brl=parse_price_brl(price_el.get_text(strip=True) if price_el else ""),
                    address=addr,
                    url=href,
                    source=self.name,
                ))
        return listings
