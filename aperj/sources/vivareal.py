"""Scraper for VivaReal - https://www.vivareal.com.br"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote_plus

from aperj.models import Listing, parse_price_brl
from aperj.sources.base import BaseSource


def _parse_first_number(text: str) -> float | None:
    """Extract the first number from a string like '68 m²' or '75-85 m²'."""
    m = re.search(r"[\d.,]+", text.replace(".", "").replace(",", "."))
    if not m:
        return None
    try:
        return float(m.group())
    except ValueError:
        return None


def _parse_first_int(text: str) -> int | None:
    """Extract the first integer from a string like '2' or '1-2'."""
    m = re.search(r"\d+", text)
    return int(m.group()) if m else None


class VivaRealSource(BaseSource):
    name = "vivareal"
    base_url = "https://www.vivareal.com.br"

    _API = "https://glue-api.vivareal.com/v2/listings"

    async def _do_scrape(self, keywords: list[str]) -> list[Listing]:
        queries = keywords or [""]
        all_listings: list[Listing] = []
        seen_urls: set[str] = set()

        for kw in queries:
            batch = await self._scrape_one(kw)
            for listing in batch:
                if listing.url not in seen_urls:
                    seen_urls.add(listing.url)
                    all_listings.append(listing)

        return all_listings

    async def _scrape_one(self, keyword: str) -> list[Listing]:
        query = keyword
        params = (
            f"?business=SALE"
            f"&listingType=USED"
            f"&addressState=Rio de Janeiro"
            f"&addressCity=Rio de Janeiro"
            f"&q={quote_plus(query)}"
            f"&size={self.max_results}"
        )
        url = f"{self._API}{params}"

        headers = {
            "x-domain": "www.vivareal.com.br",
            "accept": "application/json",
        }

        async with self._build_session() as session:
            session.headers.update(headers)
            try:
                data: dict[str, Any] = await self._fetch_json(session, url)
            except Exception:
                return await self._scrape_html(session, keyword)

        return self._parse_api(data)

    def _parse_api(self, data: dict[str, Any]) -> list[Listing]:
        listings: list[Listing] = []
        for item in data.get("search", {}).get("result", {}).get("listings", []):
            info = item.get("listing", {})
            address = info.get("address", {})
            pricing = info.get("pricingInfos", [{}])
            price = pricing[0].get("price", "") if pricing else ""
            listings.append(Listing(
                title=info.get("title", ""),
                price_brl=parse_price_brl(price),
                address=address.get("street", ""),
                neighborhood=address.get("neighborhood", ""),
                area_m2=str(info.get("totalAreas", [""])[0]) if info.get("totalAreas") else "",
                bedrooms=str(info.get("bedrooms", [""])[0]) if info.get("bedrooms") else "",
                bathrooms=str(info.get("bathrooms", [""])[0]) if info.get("bathrooms") else "",
                parking_spots=str(
                    info.get("parkingSpaces", [""])[0]
                ) if info.get("parkingSpaces") else "",
                url=f"{self.base_url}/imovel/{info.get('id', '')}",
                source=self.name,
            ))
            if len(listings) >= self.max_results:
                break
        return listings

    async def _scrape_html(self, session: Any, keywords: list[str]) -> list[Listing]:
        query = "+".join(quote_plus(k) for k in keywords)
        url = f"{self.base_url}/venda/rj/rio-de-janeiro/?q={query}"
        html = await self._fetch(session, url)
        soup = self._soup(html)
        listings: list[Listing] = []

        # Listing cards are <a> tags whose href points to a property page.
        cards = soup.find_all(
            "a",
            href=lambda h: h and ("/imovel/" in h or "/imoveis-lancamentos/" in h),
        )
        for card in cards[:self.max_results]:
            href = card.get("href", "")
            # hrefs are already absolute; only prepend base_url for relative ones
            card_url = href if href.startswith("http") else self.base_url + href

            title_el = card.select_one("h2")
            title = title_el.get_text(strip=True) if title_el else ""

            addr_el = card.select_one("p.text-1-75")
            address = addr_el.get_text(strip=True) if addr_el else ""

            # Extract neighborhood from the h2 text: "...em<Bairro>, Rio de Janeiro"
            neighborhood = ""
            if title:
                m = re.search(r"em\s*(.+?),\s*Rio de Janeiro", title)
                if m:
                    neighborhood = m.group(1).strip()

            # Extract amenities from h3 elements with sr-only label spans
            amenities: dict[str, str] = {}
            for h3 in card.find_all("h3"):
                label_el = h3.find("span", class_="sr-only")
                if not label_el:
                    continue
                label = label_el.get_text(strip=True).lower()
                value = h3.get_text(strip=True).replace(label_el.get_text(strip=True), "", 1).strip()
                amenities[label] = value

            area_str = amenities.get("tamanho do imóvel", "")
            bedrooms_str = amenities.get("quantidade de quartos", "")
            bathrooms_str = amenities.get("quantidade de banheiros", "")
            parking_str = amenities.get("quantidade de vagas de garagem", "")

            # Price: first <p> whose text starts with "R$"
            price_text = ""
            condo_text = ""
            for p in card.find_all("p"):
                txt = p.get_text(strip=True)
                if txt.startswith("R$") and not price_text:
                    price_text = txt
                elif txt.startswith("Cond."):
                    condo_text = txt

            listings.append(Listing(
                title=title,
                price_brl=parse_price_brl(price_text),
                condo_fee_brl=parse_price_brl(condo_text),
                address=address,
                neighborhood=neighborhood,
                area_m2=_parse_first_number(area_str),
                bedrooms=_parse_first_int(bedrooms_str),
                bathrooms=_parse_first_int(bathrooms_str),
                parking_spots=_parse_first_int(parking_str),
                url=card_url,
                source=self.name,
            ))
        return listings
