"""Scraper for Cyrela - https://www.cyrela.com.br"""

from __future__ import annotations

import re

from aperj.models import Listing, parse_price_brl
from aperj.sources.base import BaseSource


def _first_int(text: str) -> int | None:
    """Return the first integer found in *text*, or ``None``."""
    m = re.search(r"\d+", text)
    return int(m.group()) if m else None


def _last_int(text: str) -> int | None:
    """Return the last integer found in *text*, or ``None``."""
    nums = re.findall(r"\d+", text)
    return int(nums[-1]) if nums else None


def _int_range(text: str) -> tuple[int | None, int | None]:
    """Return (min, max) integers from *text* (e.g. ``'70 a 130'``)."""
    nums = re.findall(r"\d+", text)
    if not nums:
        return None, None
    if len(nums) == 1:
        return int(nums[0]), None
    return int(nums[0]), int(nums[-1])


class CyrelaSource(BaseSource):
    name = "cyrela"
    base_url = "https://www.cyrela.com.br"

    async def _do_scrape(self, keywords: list[str]) -> list[Listing]:
        url = f"{self.base_url}/empreendimentos?field_cidade=62"

        async with self._build_session() as session:
            html = await self._fetch(session, url)

        soup = self._soup(html)
        listings: list[Listing] = []

        for card in soup.select("article.empreendimento-card")[:self.max_results]:
            title = card.get("data-label", "")
            neighborhood = card.get("data-bairro", "")
            city = card.get("data-cidade", "Rio de Janeiro")
            price = parse_price_brl(card.get("data-valor", ""))

            link_el = card.select_one("a.empreendimento-card-trigger")
            href = ""
            if link_el and link_el.get("href"):
                href = link_el["href"]
                if href.startswith("/"):
                    href = self.base_url + href

            # Area (m²) – next to the "metragem" icon
            area_img = card.find("img", alt=lambda a: a and "metragem" in a.lower())
            area_text = area_img.parent.get_text() if area_img else ""
            area_min, area_max = _int_range(area_text)

            # Bedrooms – inside .field_dormitorios
            dorm_el = card.select_one(".field_dormitorios")
            bed_text = dorm_el.get_text() if dorm_el else ""
            beds_min, beds_max = _int_range(bed_text)

            # Suites – next to the "suíte" icon
            suite_img = card.find("img", alt=lambda a: a and "suíte" in a.lower())
            suite_text = suite_img.parent.get_text() if suite_img else ""
            suites = _first_int(suite_text)

            # Parking – next to the "vaga" icon
            vaga_img = card.find("img", alt=lambda a: a and "vaga" in a.lower())
            vaga_text = vaga_img.parent.get_text() if vaga_img else ""
            parking_min, parking_max = _int_range(vaga_text)

            listings.append(Listing(
                title=title,
                neighborhood=neighborhood,
                city=city,
                price_brl=price,
                area_m2=float(area_min) if area_min else None,
                area_max_m2=float(area_max) if area_max else None,
                bedrooms=beds_min,
                bedrooms_max=beds_max,
                suites=suites,
                parking_spots=parking_min,
                parking_max=parking_max,
                url=href,
                source=self.name,
            ))
        return listings
