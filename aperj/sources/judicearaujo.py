"""Scraper for Judice & Araujo - https://www.judicearaujo.com.br"""

from __future__ import annotations

import re

from aperj.models import Listing
from aperj.sources.base import BaseSource


class JudiceAraujoSource(BaseSource):
    name = "judicearaujo"
    base_url = "https://www.judicearaujo.com.br"

    async def _do_scrape(self, keywords: list[str]) -> list[Listing]:
        url = f"{self.base_url}/lancamentos"

        async with self._build_session() as session:
            html = await self._fetch(session, url)

        soup = self._soup(html)
        listings: list[Listing] = []

        for card in soup.select('a[href*="/lancamento/"]')[:self.max_results]:
            href = card.get("href", "")
            if href.startswith("/"):
                href = self.base_url + href

            title_el = card.select_one("span.font-bold")
            addr_el = card.select_one("span.text-xs.text-grey-350")

            bedrooms = bathrooms = area = parking = ""
            for feat_div in card.select("div[id]"):
                span = feat_div.select_one("span.font-small-3")
                if not span:
                    continue
                txt = span.get_text(" ", strip=True).lower()
                fid = (feat_div.get("id") or "").lower()
                digits = re.sub(r"[^\d a-z]", "", txt).strip()
                if "quarto" in fid or "quarto" in txt:
                    bedrooms = digits.split()[0] if digits else txt
                elif "banheir" in fid or "banheir" in txt:
                    bathrooms = digits.split()[0] if digits else txt
                elif "m²" in fid or "m²" in txt or "m2" in txt:
                    area = txt.replace("m²", "").replace("m2", "").strip()
                elif "vaga" in fid or "vaga" in txt:
                    parking = digits.split()[0] if digits else txt

            listings.append(Listing(
                title=title_el.get_text(strip=True) if title_el else "",
                address=addr_el.get_text(strip=True) if addr_el else "",
                area_m2=area,
                bedrooms=bedrooms,
                bathrooms=bathrooms,
                parking_spots=parking,
                url=href,
                source=self.name,
            ))
        return listings
