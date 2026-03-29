"""Scraper for Lopes - https://www.lopes.com.br"""

from __future__ import annotations

import re

from aperj.models import Listing, parse_price_brl
from aperj.sources.base import BaseSource


class LopesSource(BaseSource):
    name = "lopes"
    base_url = "https://www.lopes.com.br"

    async def _do_scrape(self, keywords: list[str]) -> list[Listing]:
        url = f"{self.base_url}/busca/venda/br/rj/rio-de-janeiro/tipo/apartamento"

        async with self._build_session() as session:
            html = await self._fetch(session, url)

        soup = self._soup(html)
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

            listings.append(Listing(
                title=title,
                price_brl=parse_price_brl(price_el.get_text(strip=True) if price_el else ""),
                address=address,
                area_m2=area,
                bedrooms=bedrooms,
                bathrooms=bathrooms,
                parking_spots=parking,
                url=href,
                source=self.name,
            ))
        return listings
