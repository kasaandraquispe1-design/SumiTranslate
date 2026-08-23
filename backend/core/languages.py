"""Supported languages and regional variants for Sumire Translate."""

# Regional variants are intentionally separate because translation style and
# vocabulary differ. In particular, Brazilian Portuguese (pt-BR) and European
# Portuguese (pt-PT) should never be presented as the same target option.
LANGUAGES = [
    {"code": "es", "name": "Español", "flag": "🇪🇸"},
    {"code": "en", "name": "Inglés", "flag": "🇬🇧"},
    {"code": "fr", "name": "Francés", "flag": "🇫🇷"},
    {"code": "pt-BR", "name": "Portugués (Brasil)", "flag": "🇧🇷"},
    {"code": "pt-PT", "name": "Portugués (Portugal)", "flag": "🇵🇹"},
    {"code": "de", "name": "Alemán", "flag": "🇩🇪"},
    {"code": "it", "name": "Italiano", "flag": "🇮🇹"},
]

LANGUAGE_BY_CODE = {item["code"]: item for item in LANGUAGES}


def language_name(code: str) -> str:
    return LANGUAGE_BY_CODE.get(code, {}).get("name", code)
