"""Scraper for ZAP Imóveis - https://www.zapimoveis.com.br"""

from __future__ import annotations

import json as _json
import re
from typing import Any
from urllib.parse import quote_plus

from aperj.models import Listing, parse_price_brl
from aperj.sources.base import BaseSource


class ZapImoveisSource(BaseSource):
    name = "zapimoveis"
    base_url = "https://www.zapimoveis.com.br"

    async def _do_scrape(self, keywords: list[str]) -> list[Listing]:
        query = "+".join(quote_plus(k) for k in keywords) if keywords else ""
        url = f"{self.base_url}/venda/imoveis/rj+rio-de-janeiro/"
        if query:
            url += f"?q={query}"

        async with self._build_session() as session:
            html = await self._fetch(session, url)

        soup = self._soup(html)

        # ZAP embeds structured JSON-LD (schema.org ItemList) in the HTML.
        for script in soup.find_all("script"):
            text = script.string or ""
            if text.startswith("{") and '"ItemList"' in text[:200]:
                try:
                    data = _json.loads(text)
                    if data.get("@type") == "ItemList":
                        return self._parse_jsonld(data)
                except (ValueError, KeyError):
                    continue

        return []

    # Pattern: "… em Neighbourhood, City"
    _NEIGHBOURHOOD_RE = re.compile(r"\bem\s+(.+?),\s*[^,]+$")

    def _parse_jsonld(self, data: dict[str, Any]) -> list[Listing]:
        listings: list[Listing] = []
        for entry in data.get("itemListElement", [])[: self.max_results]:
            item = entry.get("item", {})
            address = item.get("address", {})
            offers = item.get("offers", {})
            floor_size = item.get("floorSize", {})

            price_raw = offers.get("price", "")
            area_val = floor_size.get("value", "")

            title = item.get("name", "")
            neighbourhood = self._extract_neighbourhood(title)

            listings.append(
                Listing(
                    title=title,
                    price_brl=parse_price_brl(str(price_raw)),
                    address=address.get("streetAddress", ""),
                    neighborhood=neighbourhood,
                    area_m2=str(area_val) if area_val else "",
                    bedrooms=str(item.get("numberOfBedrooms", "")),
                    bathrooms=str(item.get("numberOfBathroomsTotal", "")),
                    url=item.get("url", ""),
                    source=self.name,
                    description=item.get("description", ""),
                )
            )
        return listings

    @classmethod
    def _extract_neighbourhood(cls, title: str) -> str:
        """Extract neighbourhood from a ZAP title like '… em Tijuca, Rio de Janeiro'."""
        m = cls._NEIGHBOURHOOD_RE.search(title)
        return m.group(1).strip() if m else ""
