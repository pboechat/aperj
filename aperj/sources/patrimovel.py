"""Scraper for Patrimóvel - https://patrimovel.com.br"""

from __future__ import annotations

from aperj.models import Listing, parse_price_brl
from aperj.sources.base import BaseSource


class PatrimovelSource(BaseSource):
    name = "patrimovel"
    base_url = "https://patrimovel.com.br"

    async def _do_scrape(self, keywords: list[str]) -> list[Listing]:
        urls = [
            f"{self.base_url}/lancamentos/",
            f"{self.base_url}/prontos/",
        ]

        all_listings: list[Listing] = []
        async with self._build_session() as session:
            for page_url in urls:
                try:
                    html = await self._fetch(session, page_url)
                except Exception:
                    self.logger.debug("Failed to fetch %s", page_url)
                    continue
                all_listings.extend(self._parse_page(html))
                if len(all_listings) >= self.max_results:
                    break
        return all_listings[:self.max_results]

    def _parse_page(self, html: str) -> list[Listing]:
        soup = self._soup(html)
        listings: list[Listing] = []

        for article in soup.select("article[data-title]"):
            title = article.get("data-title", "")
            bairro = article.get("data-bairro", "")
            area = article.get("data-area", "")
            quartos = article.get("data-quartos", "")
            garagem = article.get("data-garagem", "")
            valor = article.get("data-valor", "")
            permalink = article.get("data-permalink", "")

            price = ""
            if valor:
                try:
                    price = f"R$ {int(valor):,}".replace(",", ".")
                except ValueError:
                    price = valor

            # Price from span.price inside the card (formatted)
            price_el = article.select_one("span.price")
            if price_el:
                price = price_el.get_text(strip=True)

            listings.append(Listing(
                title=title,
                price_brl=parse_price_brl(price),
                neighborhood=bairro,
                address=bairro,
                area_m2=area,
                bedrooms=quartos,
                parking_spots=garagem,
                url=permalink,
                source=self.name,
            ))
        return listings
