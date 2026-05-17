from __future__ import annotations

import re
import urllib.parse
import xml.etree.ElementTree as ET

import pandas as pd
import requests

from assistant import ai_complete, compact_metrics
from ideas import load_system_prompt


DEFAULT_TREND_QUERIES = [
    "diseño gráfico latinoamérica branding cultura visual",
    "dirección de arte publicidad fotografía Ecuador",
    "gráfica popular latinoamericana diseño",
    "branding restaurantes hoteles Ecuador diseño",
    "tendencias diseño editorial risograph poster latinoamérica",
]


LOCAL_COLLAB_BANK = [
    {
        "name": "Cafés de especialidad y restaurantes de autor en Cuenca",
        "category": "Hospitalidad / gastronomía",
        "why_fit": "Necesitan identidad visual, fotografía, dirección de arte y narrativa local con estándar premium.",
        "approach": "Proponer una mini serie: 'la identidad visual de un lugar se diseña desde el ritual, no desde el logo'.",
        "priority": "Alta",
        "url": "",
    },
    {
        "name": "Hoteles boutique y proyectos turísticos de autor",
        "category": "Turismo / lifestyle",
        "why_fit": "DOMO puede unir Cuenca, cultura visual, fotografía publicitaria y deseo de marca.",
        "approach": "Enviar un concepto visual de campaña editorial: ciudad, textura, objeto, experiencia.",
        "priority": "Alta",
        "url": "",
    },
    {
        "name": "Marcas de moda independiente LATAM",
        "category": "Moda / diseño",
        "why_fit": "La estética editorial + calle puede crear campañas con identidad regional fuerte.",
        "approach": "Crear un Reel análisis de una referencia visual de moda y cerrar con propuesta de colaboración.",
        "priority": "Media",
        "url": "",
    },
    {
        "name": "Festivales, ferias creativas y espacios culturales",
        "category": "Cultura / eventos",
        "why_fit": "Son espacios naturales para workshops, charlas, dirección visual y colaboraciones.",
        "approach": "Preparar un carrusel/ensayo: 'cómo hacer que un evento tenga sistema visual, no solo afiche'.",
        "priority": "Alta",
        "url": "",
    },
]


def clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def fetch_google_news(query: str, limit: int = 6) -> list[dict]:
    encoded = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=es-419&gl=EC&ceid=EC:es-419"
    try:
        response = requests.get(url, timeout=10, headers={"User-Agent": "DOMOContentLab/1.0"})
        response.raise_for_status()
    except requests.RequestException:
        return []

    root = ET.fromstring(response.text)
    items = []
    for item in root.findall(".//item")[:limit]:
        title = clean_text(item.findtext("title") or "")
        link = item.findtext("link") or ""
        source_node = item.find("source")
        source = source_node.text if source_node is not None else ""
        if title and link:
            items.append({"query": query, "title": title, "url": link, "source": source})
    return items


def domo_read_trend(item: dict, posts: pd.DataFrame) -> str:
    prompt = load_system_prompt()
    payload = {
        "task": "Convierte esta noticia o resultado web en oportunidad de contenido DOMO.",
        "trend": item,
        "metrics": compact_metrics(posts),
        "output": "Una lectura corta: oportunidad, idea de contenido y posible marca/collab relacionada.",
    }
    ai_answer = ai_complete(prompt, payload)
    if ai_answer:
        return ai_answer
    return (
        "Oportunidad DOMO: usar este tema como espejo cultural. "
        "Hacer una pieza que traduzca la tendencia a Cuenca/LATAM con criterio visual, "
        "y cerrar con una pregunta que invite a marcas o creativos a conversar."
    )


def scout_trends(query: str, posts: pd.DataFrame, limit: int = 6) -> list[dict]:
    results = fetch_google_news(query, limit=limit)
    for result in results:
        result["domo_reading"] = domo_read_trend(result, posts)
    return results


def suggest_collabs(focus: str, posts: pd.DataFrame) -> list[dict]:
    prompt = load_system_prompt()
    payload = {
        "task": "Sugiere tipos de marcas o colaboradores para DOMO.",
        "focus": focus,
        "metrics": compact_metrics(posts),
        "requirements": [
            "que encaje con direccion creativa, diseno, fotografia publicitaria o arte visual",
            "que pueda generar leads reales",
            "que tenga una accion concreta de acercamiento",
        ],
    }
    ai_answer = ai_complete(prompt, payload)
    if ai_answer:
        return [
            {
                "name": "Sugerencia IA",
                "category": focus,
                "why_fit": ai_answer,
                "approach": ai_answer,
                "priority": "Alta",
                "url": "",
            }
        ]
    return LOCAL_COLLAB_BANK
