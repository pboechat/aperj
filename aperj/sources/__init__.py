"""Source registry - auto-discovers and exposes all available scrapers."""

from __future__ import annotations

from typing import Any

from aperj.sources.base import BaseSource
from aperj.sources.cyrela import CyrelaSource
from aperj.sources.even import EvenSource
from aperj.sources.imoveisnet import ImoveisNetSource
from aperj.sources.imovelweb import ImovelWebSource
from aperj.sources.judicearaujo import JudiceAraujoSource
from aperj.sources.lopes import LopesSource
from aperj.sources.mercadolivre import MercadoLivreSource
from aperj.sources.mrv import MrvSource
from aperj.sources.nestoria import NestoriaSource
from aperj.sources.nuroa import NuroaSource
from aperj.sources.olx import OlxSource
from aperj.sources.patrimovel import PatrimovelSource
from aperj.sources.portalrjimoveis import PortalRJImoveisSource
from aperj.sources.vivareal import VivaRealSource
from aperj.sources.zapimoveis import ZapImoveisSource

ALL_SOURCE_CLASSES: list[type[BaseSource]] = [
    ZapImoveisSource,
    VivaRealSource,
    ImovelWebSource,
    OlxSource,
    NuroaSource,
    NestoriaSource,
    PortalRJImoveisSource,
    ImoveisNetSource,
    MercadoLivreSource,
    JudiceAraujoSource,
    LopesSource,
    PatrimovelSource,
    CyrelaSource,
    EvenSource,
    MrvSource,
]


def get_all_sources(config: dict[str, Any]) -> list[BaseSource]:
    """Instantiate all registered sources that are enabled in *config*."""
    sources = [cls(config) for cls in ALL_SOURCE_CLASSES]
    return [s for s in sources if s._enabled()]


def get_source_by_name(name: str, config: dict[str, Any]) -> BaseSource | None:
    """Return a single source instance by name, or *None* if not found."""
    for cls in ALL_SOURCE_CLASSES:
        if cls.name == name:
            return cls(config)
    return None
