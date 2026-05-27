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
            "microcopy": "La referencia sirve solo si vuelve con acento propio.",
            "visual": "Portada bold, alto contraste, textura papel.",
            "note": "Abrir con postura fuerte y fácil de compartir.",
        },
        {
            "number": 2,
            "text": "Una referencia bonita no siempre tiene mundo",
            "microcopy": "Si no conversa con tu calle, es decoración.",
            "visual": "Collage de referencia global vs calle local.",
            "note": "Instalar tensión entre estética y contexto.",
        },
        {
            "number": 3,
            "text": "Antes de copiar una estética, pregúntate: qué cultura sostiene esto?",
            "microcopy": "Color, letra, material, historia: ahí está el sistema.",
            "visual": "Slide educativo guardable con etiquetas y flechas.",
            "note": "Dar criterio aplicable para saves.",
        },
        {
            "number": 4,
            "text": "Lo LATAM no es adorno: es sistema visual",
            "microcopy": "Rótulo, papel, sello y color también son estrategia.",
            "visual": "Rótulo, papel, sello, color popular.",
            "note": "Reforzar posicionamiento visual LATAM.",
        },
        {
            "number": 5,
            "text": "El criterio está en traducir, no en decorar",
            "microcopy": "Una marca viva no copia: interpreta su territorio.",
            "visual": "Frase central tipo manifiesto, mucho aire y grano.",
            "note": "Slide de frase guardable.",
        },
        {
            "number": 6,
            "text": "Si tu marca pudiera hablar desde la calle, cómo sonaría?",
            "microcopy": "Comenta una esquina, un rótulo o un color de tu barrio.",
            "visual": "CTA visual con sticker, sello y pregunta grande.",
            "note": "Cerrar con comentario de calidad.",
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
            "Cada slide debe ser una imagen del carrusel con texto grande exacto, texto pequeno exacto, visual sugerido y nota estrategica.",
            "text = texto grande del post. Maximo 10 palabras, potente, listo para pegar en Illustrator.",
            "microcopy = texto pequeno del post. Maximo 18 palabras, complementa la frase grande sin repetirla.",
            "visual = direccion visual concreta: foto, color, textura, composición, sticker, sello o recurso.",
            "caption = caption completo para Instagram. cta = llamada a accion final del carrusel.",
            "Entrega 6 a 8 slides.",
        ],
        "return_json_shape": {
            "title": "...",
            "objective": objective,
            "caption": "...",
            "cta": "...",
            "slides": [
                {"number": 1, "text": "...", "visual": "...", "microcopy": "...", "note": "..."}
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
                "slides": [
                    {
                        "number": 1,
                        "text": answer[:90],
                        "microcopy": "Revisar esta lectura y dividirla en piezas más cortas.",
                        "visual": "Texto editorial sobre textura de papel.",
                        "note": "Revisar y dividir en slides.",
                    }
                ],
            }
    fallback = json.loads(json.dumps(LOCAL_CAROUSEL, ensure_ascii=False))
    fallback["objective"] = objective
    if seed:
        fallback["title"] = seed[:70]
        fallback["slides"][0]["text"] = seed[:90]
    return fallback


def slides_to_json(carousel: dict) -> str:
    return json.dumps(carousel.get("slides", []), ensure_ascii=False, indent=2)
