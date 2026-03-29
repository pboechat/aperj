"""Scraper for QuintoAndar - https://www.quintoandar.com.br"""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

from aperj.models import Listing, parse_price_brl
from aperj.sources.base import BaseSource


def _first_int(text: str) -> int | None:
    m = re.search(r"\d+", text)
    return int(m.group()) if m else None


def _first_float(text: str) -> float | None:
    m = re.search(r"[\d]+(?:[.,]\d+)?", text.replace(".", "").replace(",", "."))
    if not m:
        return None
    try:
        return float(m.group())
    except ValueError:
        return None


class QuintoAndarSource(BaseSource):
    name = "quintoandar"
    base_url = "https://www.quintoandar.com.br"

    @staticmethod
    def _slugify(text: str) -> str:
        text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
        text = re.sub(r"[^\w\s-]", "", text).strip().lower()
        return re.sub(r"[\s_]+", "-", text)

    async def _do_scrape(self, keywords: list[str]) -> list[Listing]:
        queries = keywords or [""]
        all_listings: list[Listing] = []
        seen_urls: set[str] = set()

        async with self._build_session() as session:
            for kw in queries:
                if kw:
                    slug = self._slugify(kw)
                    url = f"{self.base_url}/comprar/imovel/{slug}-rio-de-janeiro-rj-brasil"
                else:
                    url = f"{self.base_url}/comprar/imovel/rio-de-janeiro-rj-brasil"
                html = await self._fetch(session, url)
                soup = self._soup(html)

                # Try __NEXT_DATA__ first (Next.js app).
                next_data = soup.select_one("script#__NEXT_DATA__")
                if next_data and next_data.string:
                    try:
                        batch = self._parse_next_data(json.loads(next_data.string))
                    except (ValueError, KeyError):
                        batch = self._parse_html(soup)
                else:
                    batch = self._parse_html(soup)

                for listing in batch:
                    if listing.url not in seen_urls:
                        seen_urls.add(listing.url)
                        all_listings.append(listing)

        return all_listings

    def _parse_next_data(self, data: dict[str, Any]) -> list[Listing]:
        page_props = data.get("props", {}).get("pageProps", {})
        hits = (
            page_props.get("hits")
            or page_props.get("listings")
            or page_props.get("houses")
            or page_props.get("initialResults", {}).get("hits")
            or page_props.get("searchResults", {}).get("hits")
            or []
        )
        # Newer layout stores houses inside initialState as a dict keyed by ID.
        if not hits:
            houses_dict = page_props.get("initialState", {}).get("houses", {})
            if isinstance(houses_dict, dict):
                hits = [v for k, v in houses_dict.items() if isinstance(v, dict)]
        listings: list[Listing] = []
        for item in hits[: self.max_results]:
            house_id = str(item.get("id", item.get("houseId", "")))
            raw_address = item.get("address", item.get("streetName", ""))
            # address may be a nested dict like {"address": "...", "city": "..."}
            if isinstance(raw_address, dict):
                address = raw_address.get("address", "")
            else:
                address = raw_address
            neighborhood = item.get("neighbourhood", item.get("regionName", ""))
            area = item.get("area", item.get("areaM2", ""))
            bedrooms = item.get("bedrooms", item.get("dorms", ""))
            bathrooms = item.get("bathrooms", "")
            parking = item.get("parkingSpaces", item.get("parkingSpots", item.get("garageSpaces", "")))
            price = item.get("salePrice", item.get("price", ""))
            condo = item.get("totalCost", item.get("condoIptu", ""))
            prop_type = str(item.get("type", item.get("propertyType", ""))).lower()

            title_parts = []
            if prop_type:
                title_parts.append(prop_type.capitalize())
            if bedrooms:
                title_parts.append(f"{bedrooms} quartos")
            if neighborhood:
                title_parts.append(str(neighborhood))
            title = " - ".join(title_parts) if title_parts else ""

            slug = f"comprar/{prop_type or 'imovel'}"
            listing_url = f"{self.base_url}/imovel/{house_id}/{slug}" if house_id else ""

            listings.append(Listing(
                title=title,
                price_brl=parse_price_brl(str(price)),
                condo_fee_brl=parse_price_brl(str(condo)) if condo else None,
                address=str(address),
                neighborhood=str(neighborhood),
                area_m2=_first_float(str(area)) if area else None,
                bedrooms=_first_int(str(bedrooms)) if bedrooms else None,
                bathrooms=_first_int(str(bathrooms)) if bathrooms else None,
                parking_spots=_first_int(str(parking)) if parking else None,
                url=listing_url,
                source=self.name,
            ))
        return listings

    # Pattern used in QuintoAndar listing link text:
    # "... R$ {price} R$ {condo} Condo. + IPTU {area} m² · {bedrooms} quartos · {parking} vagas
    #  {Street}, {Neighborhood} · Rio de Janeiro"
    _CARD_RE = re.compile(
        r"R\$\s*(?P<price>[\d.,]+)\s+"
        r"R\$\s*(?P<condo>[\d.,]+)\s*Condo\.\s*\+\s*IPTU\s*"
        r"(?P<area>\d[\d.]*)\s*m[²2]\s*·\s*"
        r"(?P<bedrooms>\d+)\s*quartos?"
        r"(?:\s*·\s*(?P<parking>\d+)\s*vagas?)?\s*"
        r"(?P<address>[^,·]+),\s*(?P<neighborhood>[^·]+)·\s*Rio de Janeiro",
    )

    def _parse_html(self, soup: Any) -> list[Listing]:
        listings: list[Listing] = []

        # Listing cards are <a> tags whose href contains /imovel/{id}/comprar/.
        cards = soup.find_all(
            "a",
            href=lambda h: h and re.search(r"/imovel/\d+/comprar/", h),
        )
        seen_urls: set[str] = set()
        for card in cards:
            href = card.get("href", "")
            # Strip tracking query params
            clean_href = re.sub(r"\?.*$", "", href)
            card_url = clean_href if clean_href.startswith("http") else self.base_url + clean_href
            if card_url in seen_urls:
                continue
            seen_urls.add(card_url)

            card_text = card.get_text(" ", strip=True)
            m = self._CARD_RE.search(card_text)
            if m:
                neighborhood = m.group("neighborhood").strip()
                address = m.group("address").strip()
                area = _first_float(m.group("area"))
                bedrooms = _first_int(m.group("bedrooms"))
                parking = _first_int(m.group("parking")) if m.group("parking") else None
                condo_text = m.group("condo")
                price_text = m.group("price")
            else:
                # Fallback: extract what we can from the text
                neighborhood = ""
                address = ""
                area = _first_float(ma.group(1)) if (ma := re.search(r"(\d[\d.]*)\s*metros?\s*quadrados?", card_text)) else None
                bedrooms = _first_int(ma.group(1)) if (ma := re.search(r"(\d+)\s*quartos?", card_text)) else None
                parking = _first_int(ma.group(1)) if (ma := re.search(r"(\d+)\s*vagas?", card_text)) else None
                condo_text = ""
                price_text = ""
                # Card format: "R$ {sale_price} R$ {condo} Condo. + IPTU ..."
                prices = re.findall(r"R\$\s*([\d.,]+)", card_text)
                if prices:
                    price_text = prices[0]
                    if len(prices) >= 2:
                        condo_text = prices[1]

            # Extract property type from the URL slug
            prop_match = re.search(r"/comprar/(apartamento|casa|cobertura|studio|flat|loft)", card_url)
            prop_type_str = prop_match.group(1) if prop_match else ""

            title_parts = []
            if prop_type_str:
                title_parts.append(prop_type_str.capitalize())
            if bedrooms is not None:
                title_parts.append(f"{bedrooms} quartos")
            if neighborhood:
                title_parts.append(neighborhood)
            title = " - ".join(title_parts) if title_parts else card_text[:80]

            listings.append(Listing(
                title=title,
                price_brl=parse_price_brl(price_text),
                condo_fee_brl=parse_price_brl(condo_text) if condo_text else None,
                address=address,
                neighborhood=neighborhood,
                area_m2=area,
                bedrooms=bedrooms,
                parking_spots=parking,
                url=card_url,
                source=self.name,
            ))
            if len(listings) >= self.max_results:
                break
        return listings
