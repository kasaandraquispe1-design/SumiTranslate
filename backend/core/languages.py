"""Supported languages for Sumire Translate."""

LANGUAGES = [
    {"code": "es", "name": "Español", "flag": "🇪🇸"},
    {"code": "en", "name": "Inglés", "flag": "🇬🇧"},
    {"code": "fr", "name": "Francés", "flag": "🇫🇷"},
    {"code": "pt", "name": "Portugués", "flag": "🇵🇹"},
    {"code": "de", "name": "Alemán", "flag": "🇩🇪"},
    {"code": "it", "name": "Italiano", "flag": "🇮🇹"},
]

LANGUAGE_BY_CODE = {item["code"]: item for item in LANGUAGES}


def language_name(code: str) -> str:
    return LANGUAGE_BY_CODE.get(code, {}).get("name", code)
