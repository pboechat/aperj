"""Scraper for Portal RJ Imóveis - https://www.portalrjimoveis.com.br"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote_plus

from aperj.models import Listing, parse_price_brl
from aperj.sources.base import BaseSource


class PortalRJImoveisSource(BaseSource):
    name = "portalrjimoveis"
    base_url = "https://www.portalrjimoveis.com.br"

    async def _do_scrape(self, keywords: list[str]) -> list[Listing]:
        categoria = "apartamento"
        bairro_keywords: list[str] = []
        for kw in keywords:
            low = kw.lower()
            if "cobertura" in low:
                categoria = "cobertura"
            elif "flat" in low:
                categoria = "flat"
            else:
                bairro_keywords.append(kw)

        base_url = (
            f"{self.base_url}/busca-imoveis.html"
            f"?finalidade=venda&categoria={quote_plus(categoria)}"
            f"&cidade=rio+de+janeiro&estado=rj"
        )
        bairro_queries = bairro_keywords or [""]
        all_listings: list[Listing] = []
        seen_urls: set[str] = set()

        async with self._build_session() as session:
            for bairro in bairro_queries:
                url = f"{base_url}&bairro={quote_plus(bairro)}" if bairro else base_url
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

        for card in soup.select(".card")[:self.max_results]:
            # Price from overlay
            price_el = card.select_one("p.precofoto")
            price = price_el.get_text(strip=True) if price_el else ""

            # Title and address from h2
            h2 = card.select_one("h2")
            title = ""
            address = ""
            if h2:
                addr_span = h2.select_one("span.enderecoh2")
                if addr_span:
                    address = addr_span.get_text(strip=True).lstrip("  ")
                    addr_span.decompose()
                title = h2.get_text(strip=True)

            # Features from ul li
            bedrooms = parking = area_val = ""
            for li in card.select("ul li"):
                txt = li.get_text(strip=True).lower()
                if "quarto" in txt:
                    m = re.match(r"(\d+)", txt)
                    bedrooms = m.group(1) if m else ""
                elif "vaga" in txt:
                    m = re.match(r"(\d+)", txt)
                    parking = m.group(1) if m else ""
                elif "m2" in txt or "m²" in txt:
                    m = re.match(r"(\d+)", txt)
                    area_val = m.group(1) if m else ""

            # Link
            link_el = card.select_one("a[href]")
            href = ""
            if link_el and link_el.get("href"):
                href = link_el["href"]
                if href.startswith("/") or not href.startswith("http"):
                    href = self.base_url + "/" + href.lstrip("/")

            # Parse neighbourhood from address like
            # "Rua Sorocaba - Botafogo, Rio de Janeiro - RJ"
            neighborhood = ""
            if address:
                parts = address.split(" - ")
                if len(parts) >= 2:
                    # second part is "Botafogo, Rio de Janeiro" or just "Botafogo"
                    neighborhood = parts[1].split(",")[0].strip()

            listings.append(Listing(
                title=title,
                price_brl=parse_price_brl(price),
                address=address,
                neighborhood=neighborhood,
                area_m2=area_val,
                bedrooms=bedrooms,
                parking_spots=parking,
                url=href,
                source=self.name,
            ))
        return listings
