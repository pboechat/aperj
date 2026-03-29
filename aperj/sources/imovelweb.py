"""Scraper for ImovelWeb - https://www.imovelweb.com.br"""

from __future__ import annotations

from urllib.parse import quote_plus

from aperj.models import Listing, parse_price_brl
from aperj.sources.base import BaseSource


class ImovelWebSource(BaseSource):
    name = "imovelweb"
    base_url = "https://www.imovelweb.com.br"

    async def _do_scrape(self, keywords: list[str]) -> list[Listing]:
        base_path = f"{self.base_url}/apartamentos-venda-rio-de-janeiro-rj"
        queries = keywords or [""]
        all_listings: list[Listing] = []
        seen_urls: set[str] = set()

        async with self._build_session() as session:
            for kw in queries:
                if kw:
                    url = f"{base_path}-q-{quote_plus(kw)}.html"
                else:
                    url = f"{base_path}.html"
                html = await self._fetch(session, url)
                soup = self._soup(html)
                batch = self._parse_page(soup)
                for listing in batch:
                    if listing.url not in seen_urls:
                        seen_urls.add(listing.url)
                        all_listings.append(listing)

        return all_listings

    def _parse_page(self, soup: "BeautifulSoup") -> list[Listing]:  # type: ignore[name-defined]
        listings: list[Listing] = []

        for card in soup.select(
            "[data-qa='posting'], .postingCard, [class*='PostingCard']"
        )[:self.max_results]:
            title_el = card.select_one(
                "[data-qa='posting-title'], h2, [class*='postingTitle']"
            )
            price_el = card.select_one(
                "[data-qa='posting-price'], [class*='Price']"
            )
            addr_el = card.select_one(
                "[data-qa='posting-location'], [class*='location'], address"
            )
            link_el = card.select_one("a[href]")

            features = card.select("[class*='feature'], [class*='Feature'] li, .postingMainFeatures span")
            bedrooms = bathrooms = area = parking = ""
            for feat in features:
                txt = feat.get_text(strip=True).lower()
                if "quarto" in txt or "dorm" in txt:
                    bedrooms = "".join(c for c in txt if c.isdigit())
                elif "banheir" in txt:
                    bathrooms = "".join(c for c in txt if c.isdigit())
                elif "m²" in txt or "area" in txt:
                    area = "".join(c for c in txt if c.isdigit() or c == ".")
                elif "vaga" in txt or "garag" in txt:
                    parking = "".join(c for c in txt if c.isdigit())

            href = ""
            if link_el and link_el.get("href"):
                href = link_el["href"]
                if href.startswith("/"):
                    href = self.base_url + href

            listings.append(Listing(
                title=title_el.get_text(strip=True) if title_el else "",
                price_brl=parse_price_brl(price_el.get_text(strip=True) if price_el else ""),
                address=addr_el.get_text(strip=True) if addr_el else "",
                area_m2=area,
                bedrooms=bedrooms,
                bathrooms=bathrooms,
                parking_spots=parking,
                url=href,
                source=self.name,
            ))
        return listings
