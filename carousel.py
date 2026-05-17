from __future__ import annotations

import json

import pandas as pd

from assistant import ai_complete, compact_metrics
from ideas import load_system_prompt


LOCAL_CAROUSEL = {
    "title": "Pinterest no entiende tu barrio",
    "objective": "saves",
    "caption": "Una referencia no se copia: se traduce. Si una marca quiere verse viva, tiene que aprender a mirar su propio contexto.",
    "cta": "Guarda esto y comenta que referencia ves repetida en todos lados.",
    "slides": [
        {
            "number": 1,
            "text": "Pinterest no entiende tu barrio",
            "note": "Portada bold, alto contraste, textura papel.",
        },
        {
            "number": 2,
            "text": "Una referencia bonita no siempre tiene mundo",
            "note": "Mostrar collage de referencia global vs calle local.",
        },
        {
            "number": 3,
            "text": "Antes de copiar una estética, pregúntate: qué cultura sostiene esto?",
            "note": "Slide educativo guardable.",
        },
        {
            "number": 4,
            "text": "Lo LATAM no es adorno: es sistema visual",
            "note": "Meter rótulo, papel, sello, color popular.",
        },
        {
            "number": 5,
            "text": "El criterio está en traducir, no en decorar",
            "note": "Frase central tipo manifiesto.",
        },
        {
            "number": 6,
            "text": "Si tu marca pudiera hablar desde la calle, cómo sonaría?",
            "note": "CTA visual para comentario.",
        },
    ],
}


def inspiration_context(inspirations: pd.DataFrame) -> list[dict]:
    if inspirations.empty:
        return []
    return inspirations.head(8)[["title", "url", "domo_angle", "suggested_content"]].to_dict("records")


def build_carousel_prompt(seed: str, objective: str, posts: pd.DataFrame, inspirations: pd.DataFrame) -> dict:
    return {
        "task": "Crear un carrusel DOMO con frases potentes y estructura slide por slide.",
        "seed": seed,
        "objective": objective,
        "metrics": compact_metrics(posts),
        "inspirations": inspiration_context(inspirations),
        "rules": [
            "No hacer '5 tips' genericos.",
            "Cada frase debe sonar a DOMO: criterio visual LATAM, editorial + calle, simple pero con filo.",
            "Debe servir para shares, saves, comentarios de calidad o leads.",
            "Incluir portada, tension, desarrollo, idea guardable y cierre con CTA.",
        ],
        "return_json_shape": {
            "title": "...",
            "objective": objective,
            "caption": "...",
            "cta": "...",
            "slides": [
                {"number": 1, "text": "...", "note": "..."}
            ],
        },
    }


def generate_carousel(seed: str, objective: str, posts: pd.DataFrame, inspirations: pd.DataFrame) -> dict:
    system = load_system_prompt() + "\nEres guionista de carruseles editoriales para DOMO."
    payload = build_carousel_prompt(seed, objective, posts, inspirations)
    answer = ai_complete(system, payload)
    if answer:
        try:
            start = answer.find("{")
            end = answer.rfind("}") + 1
            return json.loads(answer[start:end])
        except (json.JSONDecodeError, ValueError):
            return {
                "title": "Carrusel DOMO generado",
                "objective": objective,
                "caption": answer,
                "cta": "Comenta que parte te hizo mirar distinto.",
                "slides": [{"number": 1, "text": answer[:180], "note": "Revisar y dividir en slides."}],
            }
    fallback = LOCAL_CAROUSEL.copy()
    fallback["objective"] = objective
    if seed:
        fallback["title"] = seed[:70]
        fallback["slides"][0]["text"] = seed[:90]
    return fallback


def slides_to_json(carousel: dict) -> str:
    return json.dumps(carousel.get("slides", []), ensure_ascii=False, indent=2)
