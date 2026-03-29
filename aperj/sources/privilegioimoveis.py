"""Scraper for Privilégio Imóveis - https://www.privilegioimoveis.com.br"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from aperj.models import Listing, parse_price_brl
from aperj.sources.base import BaseSource


def _safe_int(val: Any) -> int | None:
    if val is None or val == "" or val == 0:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _safe_float(val: Any) -> float | None:
    if val is None or val == "" or val == 0:
        return None
    try:
        return float(str(val).replace(",", "."))
    except (ValueError, TypeError):
        return None


class PrivilegioImoveisSource(BaseSource):
    name = "privilegioimoveis"
    base_url = "https://www.privilegioimoveis.com.br"

    # The site is an SPA backed by a JSON API.
    _API = "https://www.privilegioimoveis.com.br/api/imoveis"

    async def _do_scrape(self, keywords: list[str]) -> list[Listing]:
        queries = keywords or [""]
        all_listings: list[Listing] = []
        seen_urls: set[str] = set()

        async with self._build_session() as session:
            session.headers["Accept"] = "application/json"
            for kw in queries:
                params: dict[str, str] = {
                    "finalidade": "2",          # 2 = venda (sale)
                    "pagina": "1",
                    "por_pagina": str(self.max_results),
                }
                if kw:
                    params["endereco"] = kw

                url = f"{self._API}?{urlencode(params)}"
                data: dict[str, Any] = await self._fetch_json(session, url)
                batch = self._parse_api(data)
                for listing in batch:
                    if listing.url not in seen_urls:
                        seen_urls.add(listing.url)
                        all_listings.append(listing)

        return all_listings

    def _parse_api(self, data: dict[str, Any]) -> list[Listing]:
        listings: list[Listing] = []
        for item in data.get("lista", [])[: self.max_results]:
            code = item.get("codigo", "")
            address_parts = [item.get("endereco", ""), item.get("numero", "")]
            address = ", ".join(p for p in address_parts if p).strip(", ")

            listings.append(Listing(
                title=item.get("titulo", ""),
                description=item.get("descricao", ""),
                price_brl=parse_price_brl(str(item.get("valor", ""))),
                condo_fee_brl=parse_price_brl(str(item.get("valorcondominio", ""))),
                iptu_brl=parse_price_brl(str(item.get("valoriptu", ""))),
                address=address,
                neighborhood=item.get("bairro", ""),
                area_m2=_safe_float(item.get("areaprincipal")),
                bedrooms=_safe_int(item.get("numeroquartos")),
                suites=_safe_int(item.get("numerosuites")),
                bathrooms=_safe_int(item.get("numerobanhos")),
                parking_spots=_safe_int(item.get("numerovagas")),
                url=f"{self.base_url}/imoveis/{code}" if code else "",
                source=self.name,
            ))
        return listings
