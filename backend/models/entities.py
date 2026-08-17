"""Lightweight domain models corresponding to Base44 entities.

Persistence is intentionally not implemented yet. These models let the
translation core remain independent from Base44 and can later be mapped to a
real database.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

DocumentType = Literal["txt", "pdf", "docx"]
DocumentStatus = Literal[
    "uploaded", "analyzing", "analyzed", "translating", "completed",
    "validation_failed", "error",
]
PaymentMethod = Literal["yape", "plin", "card"]
Plan = Literal["free", "individual", "professional"]
PaymentStatus = Literal["PENDING", "PAID", "FAILED", "CANCELLED", "REFUNDED"]
TranslationMode = Literal["text", "document"]
UserRole = Literal["admin", "user"]


@dataclass
class Document:
    filename: str
    file_type: DocumentType = "txt"
    file_url: str = ""
    status: DocumentStatus = "uploaded"
    source_lang: str = "en"
    target_lang: str = "es"
    total_words: int = 0
    translatable_words: int = 0
    protected_count: int = 0
    cost: float = 0.0


@dataclass
class Translation:
    source_text: str
    translated_text: str
    document_id: str = ""
    source_lang: str = "en"
    target_lang: str = "es"
    total_words: int = 0
    translatable_words: int = 0
    protected_count: int = 0
    validation_passed: bool = True
    validation_issues: str = ""
    mode: TranslationMode = "text"


@dataclass
class Payment:
    amount: float
    plan: Plan
    method: PaymentMethod
    status: PaymentStatus
    currency: str = "PEN"
    words_purchased: int = 0
    provider_reference: str = ""


@dataclass
class User:
    role: UserRole
