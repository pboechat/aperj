"""Scraper for Nuroa - https://www.nuroa.com.br"""

from __future__ import annotations

import re

from aperj.models import Listing, parse_price_brl
from aperj.sources.base import BaseSource


class NuroaSource(BaseSource):
    name = "nuroa"
    base_url = "https://www.nuroa.com.br"

    async def _do_scrape(self, keywords: list[str]) -> list[Listing]:
        url = f"{self.base_url}/venda/apartamento-rio-de-janeiro"

        async with self._build_session() as session:
            html = await self._fetch(session, url)

        soup = self._soup(html)
        listings: list[Listing] = []

        for container in soup.select(".nu_desc_container")[:self.max_results * 3]:
            # Skip empty ad placeholders
            details = container.select_one(".nu_listing_details")
            if not details:
                continue

            title_el = container.select_one("h3.nu_list_title")
            addr_el = container.select_one("p.nu_sub")
            if addr_el:
                mapa_span = addr_el.select_one("span.nu_ver_mapa")
                if mapa_span:
                    mapa_span.decompose()
            link_el = container.select_one("a.nu_adlink")

            price = ""
            bedrooms = bathrooms = area = ""
            price_parts = details.select(".nu_price span[itemprop='price']")
            if price_parts:
                price = f"R$ {price_parts[0].get_text(strip=True)}"

            for li in details.select("ul.nu_features li"):
                txt = li.get_text(strip=True).lower()
                if "brl/m" in txt or "/m²" in txt:
                    continue  # skip price-per-m²
                if "dormitório" in txt or "quarto" in txt:
                    bedrooms = re.sub(r"[^\d]", "", txt)
                elif "banheiro" in txt:
                    bathrooms = re.sub(r"[^\d]", "", txt)
                elif "m2" in txt or "m²" in txt:
                    area = re.sub(r"[^\d.,]", "", txt.split("m")[0])

            href = ""
            if link_el and link_el.get("href"):
                href = link_el["href"]

            listings.append(Listing(
                title=title_el.get_text(strip=True) if title_el else "",
                price_brl=parse_price_brl(price),
                address=addr_el.get_text(strip=True) if addr_el else "",
                area_m2=area,
                bedrooms=bedrooms,
                bathrooms=bathrooms,
                url=href,
                source=self.name,
            ))
        return listings
