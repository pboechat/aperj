"""Scraper for Mercado Livre Imóveis - https://imoveis.mercadolivre.com.br"""

from __future__ import annotations

import re
from urllib.parse import quote_plus

from aperj.models import Listing, parse_price_brl
from aperj.sources.base import BaseSource


class MercadoLivreSource(BaseSource):
    name = "mercadolivre"
    base_url = "https://imoveis.mercadolivre.com.br"

    async def _do_scrape(self, keywords: list[str]) -> list[Listing]:
        listings: list[Listing] = []
        seen_urls: set[str] = set()

        queries = keywords or [""]

        async with self._build_session() as session:
            for kw in queries:
                url = f"{self.base_url}/apartamentos/venda/rio-de-janeiro/"
                if kw:
                    url += f"?q={quote_plus(kw)}"
                html = await self._fetch(session, url)
                self._parse_page(html, listings, seen_urls)

        return listings

    def _parse_page(
        self,
        html: str,
        listings: list[Listing],
        seen_urls: set[str],
    ) -> None:
        soup = self._soup(html)

        for card in soup.select(".ui-search-layout__item")[:self.max_results]:
            title_el = card.select_one(
                "h2, [class*='poly-component__title'],"
                " [class*='ui-search-item__title']"
            )
            price_el = card.select_one(
                "[class*='poly-price'], [class*='price']"
            )
            link_el = card.select_one("a[href]")
            addr_el = card.select_one(
                "[class*='poly-component__location'],"
                " [class*='location'], [class*='address']"
            )

            href = ""
            if link_el and link_el.get("href"):
                href = link_el["href"]

            # Extract features from attribute list
            bedrooms = area = bathrooms = ""
            for attr in card.select(
                "[class*='key-value'], [class*='attrs'] li,"
                " [class*='attribute'] li"
            ):
                txt = attr.get_text(strip=True).lower()
                if "quarto" in txt or "dorm" in txt:
                    m = re.match(r"(\d+)", txt)
                    bedrooms = m.group(1) if m else ""
                elif "banheiro" in txt:
                    m = re.match(r"(\d+)", txt)
                    bathrooms = m.group(1) if m else ""
                elif "m²" in txt:
                    m = re.match(r"(\d[\d.]*)", txt)
                    area = m.group(1) if m else ""

            if href and href in seen_urls:
                continue
            if href:
                seen_urls.add(href)

            listings.append(Listing(
                title=title_el.get_text(strip=True) if title_el else "",
                price_brl=parse_price_brl(price_el.get_text(strip=True) if price_el else ""),
                address=addr_el.get_text(strip=True) if addr_el else "",
                area_m2=area,
                bedrooms=bedrooms,
                bathrooms=bathrooms,
                url=href,
                source=self.name,
            ))
