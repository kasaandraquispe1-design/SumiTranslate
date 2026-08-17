"""Supported languages for Sumire Translate.

Keep this list in one place so the UI, prompt builder and future document
translation adapters use exactly the same language codes.
"""

LANGUAGES = [
    {"code": "es", "name": "Español", "flag": "🇪🇸"},
    {"code": "en", "name": "Inglés", "flag": "🇬🇧"},
    {"code": "pt", "name": "Portugués", "flag": "🇵🇹"},
    {"code": "fr", "name": "Francés", "flag": "🇫🇷"},
    {"code": "de", "name": "Alemán", "flag": "🇩🇪"},
    {"code": "it", "name": "Italiano", "flag": "🇮🇹"},
    {"code": "ja", "name": "Japonés", "flag": "🇯🇵"},
    {"code": "zh", "name": "Chino", "flag": "🇨🇳"},
    {"code": "ko", "name": "Coreano", "flag": "🇰🇷"},
    {"code": "ru", "name": "Ruso", "flag": "🇷🇺"},
    {"code": "ar", "name": "Árabe", "flag": "🇸🇦"},
]

LANGUAGE_BY_CODE = {item["code"]: item for item in LANGUAGES}


def language_name(code: str) -> str:
    return LANGUAGE_BY_CODE.get(code, {}).get("name", code)
