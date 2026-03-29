"""Scraper for Even - https://www.even.com.br"""

from __future__ import annotations

import json

from aperj.models import Listing, parse_price_brl
from aperj.sources.base import BaseSource


class EvenSource(BaseSource):
    name = "even"
    base_url = "https://www.even.com.br"

    async def _do_scrape(self, keywords: list[str]) -> list[Listing]:
        url = f"{self.base_url}/encontre-seu-even/resultado?tipo_busca=todos"

        async with self._build_session() as session:
            html = await self._fetch(session, url)

        soup = self._soup(html)
        listings: list[Listing] = []

        # Even embeds all data in __NEXT_DATA__
        script = soup.select_one("script#__NEXT_DATA__")
        if not script or not script.string:
            return listings

        data = json.loads(script.string)
        emps = data.get("props", {}).get("pageProps", {}).get("empreendimentos", [])

        for emp in emps:
            loc = emp.get("localizacao", {})
            estado = loc.get("estado", {})
            if estado.get("sigla", "").upper() != "RJ":
                continue

            bairro = loc.get("bairro", {}).get("nome", "")
            cidade = loc.get("cidade", {}).get("nome", "")
            endereco = loc.get("enderecoExibicao", "")
            address = f"{endereco}, {bairro} - {cidade}" if endereco else f"{bairro} - {cidade}"

            preco_info = emp.get("preco", {})
            price = ""
            if isinstance(preco_info, dict) and preco_info.get("preco"):
                price = f"R$ {preco_info['preco']:,.0f}".replace(",", ".")

            area_min = emp.get("areaMinima") or None
            area_max = emp.get("areaMaxima") or None

            dorm_min = emp.get("dormitorioMinimo") or None
            dorm_max = emp.get("dormitorioMaximo") or None

            vagas_min = emp.get("vagasGaragemMinimo") or None
            vagas_max = emp.get("vagasGaragemMaximo") or None

            slug_url = emp.get("slugUrl", "")
            listing_url = f"{self.base_url}/{slug_url}" if slug_url else ""

            listings.append(Listing(
                title=emp.get("nome", ""),
                price_brl=parse_price_brl(price),
                address=address,
                neighborhood=bairro,
                area_m2=area_min,
                area_max_m2=area_max if area_max != area_min else None,
                bedrooms=dorm_min,
                bedrooms_max=dorm_max if dorm_max != dorm_min else None,
                parking_spots=vagas_min,
                parking_max=vagas_max if vagas_max != vagas_min else None,
                description=emp.get("descricaoCurta1", ""),
                url=listing_url,
                source=self.name,
            ))
            if len(listings) >= self.max_results:
                break

        return listings
