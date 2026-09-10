"""Minimal beta billing model for Sumire Translate.

This module intentionally does not process or verify payments automatically.
During the beta, payments can be received manually through Yape/Plin and
verified by the owner before unlocking a paid package.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import uuid4

FREE_WORDS = 1_000


@dataclass(frozen=True)
class Package:
    key: str
    name: str
    words: int
    price: Decimal
    description: str


PACKAGES = (
    Package("p2500", "2,500 palabras", 2_500, Decimal("1.00"), "Para traducciones pequeñas"),
    Package("p5000", "5,000 palabras", 5_000, Decimal("2.00"), "Para artículos y apuntes"),
    Package("p10000", "10,000 palabras", 10_000, Decimal("4.00"), "Para documentos medianos"),
    Package("p20000", "20,000 palabras", 20_000, Decimal("8.00"), "Para documentos grandes"),
)


def new_order_id() -> str:
    return f"SUM-{uuid4().hex[:8].upper()}"


def get_package(key: str) -> Package | None:
    return next((package for package in PACKAGES if package.key == key), None)


def package_for_words(words: int) -> Package | None:
    return next((package for package in PACKAGES if package.words >= words), None)


def money(value: Decimal) -> str:
    return f"S/ {value:.2f}"
