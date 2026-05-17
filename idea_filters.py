from __future__ import annotations

import re


TRIVIAL_PATTERNS = [
    r"^\s*$",
    r"^(jaja|jeje|haha|lol)+$",
    r"^(wow|nice|cool|brutal|genial|lindo|top|fire|uff|excelente)[!. ]*$",
    r"^(me encanta|qué lindo|que lindo|buenísimo|buenisimo)[!. ]*$",
    r"^[🔥❤️😍👏🙌✨💯 ]+$",
    r"^(precio|info|más info|mas info|dm|hola)[?!. ]*$",
]


QUALITY_SIGNALS = [
    "porque",
    "cómo",
    "como",
    "por qué",
    "por que",
    "referencia",
    "proceso",
    "criterio",
    "marca",
    "identidad",
    "workshop",
    "consultoría",
    "consultoria",
    "colaborar",
    "proyecto",
    "aprendí",
    "aprendi",
    "me sirve",
]


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def is_trivial_message(text: str) -> bool:
    cleaned = normalize_text(text)
    return any(re.match(pattern, cleaned) for pattern in TRIVIAL_PATTERNS)


def is_quality_comment(text: str) -> bool:
    cleaned = normalize_text(text)
    if is_trivial_message(cleaned):
        return False
    if len(cleaned.split()) >= 8:
        return True
    return any(signal in cleaned for signal in QUALITY_SIGNALS)


def filter_quality_comments(comments: list[str]) -> list[str]:
    return [comment for comment in comments if is_quality_comment(comment)]
