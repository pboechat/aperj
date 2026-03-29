"""Data models for apartment listings."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import asdict, dataclass, fields
from enum import Enum
from typing import ClassVar


class ListingType(str, Enum):
    """Whether a property is for sale or rent."""

    SALE = "venda"
    RENT = "aluguel"


class PropertyType(str, Enum):
    """Kind of property."""

    APARTMENT = "apartamento"
    PENTHOUSE = "cobertura"
    FLAT = "flat"
    STUDIO = "studio"
    LOFT = "loft"
    HOUSE = "casa"
    OTHER = "outro"


@dataclass(slots=True)
class Listing:
    """A single real-estate listing scraped from a source.

    Monetary fields (``price_brl``, ``condo_fee_brl``, ``iptu_brl``) store
    values in **centavos** (integer) so arithmetic is lossless.  A value of
    ``None`` means the information was not available.  The helper
    ``format_brl`` converts centavos → human-readable ``R$ …`` strings.
    """

    # ── identity ──────────────────────────────────────────────────────
    title: str = ""
    description: str = ""
    url: str = ""
    source: str = ""

    # ── classification ────────────────────────────────────────────────
    listing_type: ListingType = ListingType.SALE
    property_type: PropertyType = PropertyType.APARTMENT

    # ── location ──────────────────────────────────────────────────────
    address: str = ""
    neighborhood: str = ""
    city: str = "Rio de Janeiro"
    state: str = "RJ"

    # ── pricing (centavos) ────────────────────────────────────────────
    price_brl: int | None = None
    condo_fee_brl: int | None = None
    iptu_brl: int | None = None

    # ── features ──────────────────────────────────────────────────────
    area_m2: float | None = None
    area_max_m2: float | None = None      # for ranges (e.g. new builds)
    bedrooms: int | None = None
    bedrooms_max: int | None = None       # for ranges
    suites: int | None = None
    bathrooms: int | None = None
    parking_spots: int | None = None
    parking_max: int | None = None        # for ranges

    # ── display helpers ──────────────────────────────────────────────

    @staticmethod
    def format_brl(centavos: int | None) -> str:
        """Format centavos as ``R$ 1.234,56`` or ``R$ 1.234`` (no cents)."""
        if centavos is None:
            return ""
        reais, cents = divmod(abs(centavos), 100)
        sign = "-" if centavos < 0 else ""
        int_part = f"{reais:,}".replace(",", ".")
        if cents:
            return f"{sign}R$ {int_part},{cents:02d}"
        return f"{sign}R$ {int_part}"

    def fmt_price(self) -> str:
        return self.format_brl(self.price_brl)

    def fmt_condo(self) -> str:
        return self.format_brl(self.condo_fee_brl)

    def fmt_iptu(self) -> str:
        return self.format_brl(self.iptu_brl)

    def fmt_area(self) -> str:
        if self.area_m2 is None:
            return ""
        a = _fmt_num(self.area_m2)
        if self.area_max_m2 is not None and self.area_max_m2 != self.area_m2:
            return f"{a}–{_fmt_num(self.area_max_m2)}"
        return a

    def fmt_bedrooms(self) -> str:
        if self.bedrooms is None:
            return ""
        if self.bedrooms_max is not None and self.bedrooms_max != self.bedrooms:
            return f"{self.bedrooms}–{self.bedrooms_max}"
        return str(self.bedrooms)

    def fmt_parking(self) -> str:
        if self.parking_spots is None:
            return ""
        if self.parking_max is not None and self.parking_max != self.parking_spots:
            return f"{self.parking_spots}–{self.parking_max}"
        return str(self.parking_spots)

    def fmt_location(self) -> str:
        """Best-effort one-liner for the property location."""
        if self.neighborhood and self.address:
            return self.address
        return self.neighborhood or self.address or ""

    # ── serialisation ─────────────────────────────────────────────────

    def to_dict(self) -> dict[str, str]:
        """Flat dict with human-readable values - suitable for CSV."""
        return {
            "title": self.title,
            "description": self.description,
            "url": self.url,
            "source": self.source,
            "listing_type": self.listing_type.value,
            "property_type": self.property_type.value,
            "address": self.address,
            "neighborhood": self.neighborhood,
            "city": self.city,
            "state": self.state,
            "price": self.fmt_price(),
            "condo_fee": self.fmt_condo(),
            "iptu": self.fmt_iptu(),
            "area_m2": self.fmt_area(),
            "bedrooms": self.fmt_bedrooms(),
            "suites": str(self.suites) if self.suites is not None else "",
            "bathrooms": str(self.bathrooms) if self.bathrooms is not None else "",
            "parking_spots": self.fmt_parking(),
        }

    _CSV_COLUMNS: ClassVar[list[str]] = [
        "source", "listing_type", "property_type",
        "price", "condo_fee", "iptu",
        "neighborhood", "address", "city", "state",
        "area_m2", "bedrooms", "suites", "bathrooms", "parking_spots",
        "title", "url",
    ]

    @classmethod
    def csv_header(cls) -> list[str]:
        return list(cls._CSV_COLUMNS)

    def csv_row(self) -> list[str]:
        d = self.to_dict()
        return [d.get(k, "") for k in self._CSV_COLUMNS]


# ── private helpers ───────────────────────────────────────────────────

def _fmt_num(v: float | str) -> str:
    """Format a number dropping ``.0`` when integer.

    If *v* is a range string like ``'227 a 415'``, only the first number
    is used (the caller should split ranges into separate fields instead).
    """
    if isinstance(v, str):
        m = re.search(r"[\d]+(?:[.,]\d+)?", v)
        if m is None:
            return v
        v = float(m.group().replace(",", "."))
    return str(int(v)) if v == int(v) else f"{v:g}"


def parse_price_brl(text: str) -> int | None:
    """Parse a Brazilian price string into centavos.

    Handles formats like ``R$ 1.234.567``, ``R$ 1.234,56``, ``1234567``, etc.
    Returns ``None`` when the string contains no recognisable number.
    """
    if not text:
        return None
    # Strip currency symbol, whitespace, dots used as thousands separators
    cleaned = re.sub(r"[R$\s.]", "", text)
    # Replace comma (decimal separator) with a dot
    cleaned = cleaned.replace(",", ".")
    m = re.search(r"\d+(?:\.\d+)?", cleaned)
    if not m:
        return None
    return int(round(float(m.group()) * 100))


def listings_to_csv(listings: list[Listing]) -> str:
    """Serialize a list of listings to a CSV string."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(Listing.csv_header())
    for listing in listings:
        writer.writerow(listing.csv_row())
    return buf.getvalue()
