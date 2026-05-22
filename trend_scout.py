from __future__ import annotations

import re
import urllib.parse
import xml.etree.ElementTree as ET
from html import unescape

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
    {
        "name": "Estudios de arquitectura e interiorismo con proyectos fotogénicos",
        "category": "Arquitectura / interiorismo",
        "why_fit": "Necesitan fotografía, narrativa visual y contenido que haga que sus espacios se entiendan y se deseen.",
        "approach": "Proponer una colaboración: DOMO lee un espacio como sistema visual y arma una mini campaña editorial.",
        "priority": "Alta",
        "url": "",
    },
    {
        "name": "Marcas de productos premium hechos en Ecuador",
        "category": "Producto / lifestyle",
        "why_fit": "Pueden crecer con dirección de arte, mockups, foto publicitaria y lenguaje visual con raíz LATAM.",
        "approach": "Enviar una idea: transformar un producto en 5 piezas de contenido con foto, frase, contexto y uso real.",
        "priority": "Alta",
        "url": "",
    },
    {
        "name": "Escuelas, universidades y comunidades creativas",
        "category": "Educación / workshops",
        "why_fit": "Son puertas naturales para talleres de criterio visual, branding, fotografía y cultura gráfica.",
        "approach": "Ofrecer un workshop: 'cómo mirar la ciudad para diseñar marcas con identidad'.",
        "priority": "Media",
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


def fetch_web_results(query: str, limit: int = 6) -> list[dict]:
    encoded = urllib.parse.quote_plus(query)
    url = f"https://duckduckgo.com/html/?q={encoded}"
    try:
        response = requests.get(
            url,
            timeout=12,
            headers={"User-Agent": "Mozilla/5.0 DOMOContentLab/1.0"},
        )
        response.raise_for_status()
    except requests.RequestException:
        return []

    items = []
    seen = set()
    pattern = re.compile(
        r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        flags=re.IGNORECASE | re.DOTALL,
    )
    for raw_url, raw_title in pattern.findall(response.text):
        title = clean_text(unescape(raw_title))
        parsed = urllib.parse.urlparse(unescape(raw_url))
        final_url = unescape(raw_url)
        if "duckduckgo.com" in parsed.netloc:
            params = urllib.parse.parse_qs(parsed.query)
            if "uddg" in params:
                final_url = params["uddg"][0]
        source = urllib.parse.urlparse(final_url).netloc.replace("www.", "")
        if title and final_url and final_url not in seen:
            seen.add(final_url)
            items.append({"query": query, "title": title, "url": final_url, "source": source or "web"})
        if len(items) >= limit:
            break
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


def scout_trends(query: str, posts: pd.DataFrame, limit: int = 6, include_instagram: bool = False) -> list[dict]:
    web_query = query
    if include_instagram and "instagram" not in query.lower():
        web_query = f"{query} Instagram OR site:instagram.com"

    results = fetch_web_results(web_query, limit=limit)
    if len(results) < limit:
        existing_urls = {item["url"] for item in results}
        for item in fetch_google_news(query, limit=limit):
            if item["url"] not in existing_urls:
                results.append(item)
            if len(results) >= limit:
                break
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
    focus_text = focus.lower()
    ranked = sorted(
        LOCAL_COLLAB_BANK,
        key=lambda item: (
            3 if item["category"].lower() in focus_text or item["name"].lower() in focus_text else 0,
            2 if "fotograf" in focus_text and "foto" in item["why_fit"].lower() else 0,
            2 if "branding" in focus_text and ("marca" in item["why_fit"].lower() or "branding" in item["approach"].lower()) else 0,
            1 if item["priority"] == "Alta" else 0,
        ),
        reverse=True,
    )
    return ranked
