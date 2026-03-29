"""Scraper for Lopes - https://www.lopes.com.br"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from aperj.models import Listing, parse_price_brl
from aperj.sources.base import BaseSource


def _slugify(text: str) -> str:
    """Convert *text* to a URL-friendly slug (e.g. 'Barra da Tijuca' -> 'barra-da-tijuca')."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[\s_]+", "-", text)


class LopesSource(BaseSource):
    name = "lopes"
    base_url = "https://www.lopes.com.br"

    async def _do_scrape(self, keywords: list[str]) -> list[Listing]:
        queries = keywords or [""]
        all_listings: list[Listing] = []
        seen_urls: set[str] = set()

        async with self._build_session() as session:
            for kw in queries:
                if kw:
                    bairro_slug = _slugify(kw)
                    url = f"{self.base_url}/busca/venda/br/rj/rio-de-janeiro/{bairro_slug}/tipo/apartamento"
                else:
                    url = f"{self.base_url}/busca/venda/br/rj/rio-de-janeiro/tipo/apartamento"
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

        for article in soup.select("article")[:self.max_results]:
            price_el = article.select_one("p.price")
            type_el = article.select_one("h2.type")
            location_el = article.select_one("span.location p")

            # Parse structured attributes: area, quartos, banheiros, vagas
            bedrooms = bathrooms = area = parking = ""
            for li in article.select("ul.attributes li p"):
                txt = li.get_text(strip=True).lower()
                if "m²" in txt or "m2" in txt:
                    m = re.match(r"(\d[\d.]*)", txt)
                    area = m.group(1) if m else ""
                elif "quarto" in txt or "dorm" in txt:
                    m = re.match(r"(\d+)", txt)
                    bedrooms = m.group(1) if m else ""
                elif "banheir" in txt:
                    m = re.match(r"(\d+)", txt)
                    bathrooms = m.group(1) if m else ""
                elif "vaga" in txt:
                    m = re.match(r"(\d+)", txt)
                    parking = m.group(1) if m else ""

            # The article's parent <a> holds the href
            parent_a = article.parent
            href = ""
            if parent_a and parent_a.name == "a" and parent_a.get("href"):
                href = parent_a["href"]
                if href.startswith("/"):
                    href = self.base_url + href

            title = type_el.get_text(strip=True) if type_el else ""
            address = location_el.get_text(strip=True) if location_el else ""

            # Parse neighbourhood from address like
            # "Rua Bambina, Botafogo - Rio de Janeiro"
            neighborhood = ""
            if address:
                comma_parts = address.split(", ", 1)
                if len(comma_parts) >= 2:
                    # second part is "Botafogo - Rio de Janeiro"
                    neighborhood = comma_parts[1].split(" - ")[0].strip()

            listings.append(Listing(
                title=title,
                price_brl=parse_price_brl(price_el.get_text(strip=True) if price_el else ""),
                address=address,
                neighborhood=neighborhood,
                area_m2=area,
                bedrooms=bedrooms,
                bathrooms=bathrooms,
                parking_spots=parking,
                url=href,
                source=self.name,
            ))
        return listings
