"""Pricing model for the Sumire Translate beta.

The beta is intentionally inexpensive: the first 1,000 translatable words
are free and additional usage is sold in small, student-friendly packages.
The temporary maximum purchase is S/ 3.00 per order.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import uuid4

FREE_WORDS = 1_000
MAX_PAYMENT_PEN = Decimal("3.00")


@dataclass(frozen=True)
class Package:
    key: str
    name: str
    words: int
    price: Decimal
    description: str


# Temporary beta prices: deliberately low while translation quality,
# PDF reconstruction, speed and language coverage are still being improved.
PACKAGES = (
    Package("p5000", "5,000 palabras", 5_000, Decimal("0.50"), "Para pruebas y documentos pequeños"),
    Package("p10000", "10,000 palabras", 10_000, Decimal("1.00"), "Para apuntes y artículos"),
    Package("p20000", "20,000 palabras", 20_000, Decimal("2.00"), "Para documentos medianos"),
    Package("p30000", "30,000 palabras", 30_000, Decimal("3.00"), "Máximo temporal de la beta"),
)


def new_order_id() -> str:
    return f"SUM-{uuid4().hex[:8].upper()}"


def get_package(key: str) -> Package | None:
    return next((package for package in PACKAGES if package.key == key), None)


def package_for_words(words: int) -> Package | None:
    return next((package for package in PACKAGES if package.words >= words), None)


def money(value: Decimal) -> str:
    return f"S/ {value:.2f}"
