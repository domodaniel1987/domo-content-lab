from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import streamlit as st

from ideas import load_system_prompt, summarize_context

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> bool:
        return False


def has_ai_key() -> bool:
    load_dotenv()
    return bool(get_secret("OPENAI_API_KEY", ""))


def get_secret(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return value or os.getenv(name, default)


def get_openai_client():
    load_dotenv()
    api_key = get_secret("OPENAI_API_KEY", "")
    if not api_key:
        return None
    try:
        from openai import OpenAI
    except ImportError:
        return None
    return OpenAI(api_key=api_key)


def compact_metrics(posts: pd.DataFrame) -> dict[str, Any]:
    if posts.empty:
        return {}
    top = posts.sort_values(
        ["share_rate", "save_rate", "quality_comment_rate", "profile_visit_rate"],
        ascending=False,
    ).head(6)
    weak = posts.sort_values(
        ["share_rate", "save_rate", "quality_comment_rate"],
        ascending=True,
    ).head(4)
    return {
        "average": posts[["engagement_rate", "share_rate", "save_rate", "quality_comment_rate", "profile_visit_rate"]].mean().round(2).to_dict(),
        "top_posts": top[["title", "platform", "pillar", "format", "share_rate", "save_rate", "quality_comment_rate", "profile_visit_rate"]].to_dict("records"),
        "weak_posts": weak[["title", "platform", "pillar", "format", "share_rate", "save_rate", "quality_comment_rate"]].to_dict("records"),
        "context": summarize_context(posts),
    }


def ai_complete(system_prompt: str, user_payload: dict) -> str | None:
    client = get_openai_client()
    if client is None:
        return None
    try:
        response = client.chat.completions.create(
            model=get_secret("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            temperature=0.75,
        )
        return response.choices[0].message.content
    except Exception as exc:
        st.warning(
            "La IA de OpenAI respondió con límite/cuota o un error temporal. "
            "La app seguirá usando estrategia local por ahora."
        )
        st.caption(f"Detalle técnico: {type(exc).__name__}")
        return None


def answer_as_domo_assistant(question: str, posts: pd.DataFrame) -> str:
    system_prompt = (
        load_system_prompt()
        + "\nActua como asistente privado de redes de DOMO. "
        + "Se directo, ambicioso y estrategico. No prometas fama garantizada; traduce la ambicion en acciones medibles."
    )
    payload = {
        "question": question,
        "metrics": compact_metrics(posts),
        "answer_style": "claro, accionable, en español, con pasos concretos",
    }
    ai_answer = ai_complete(system_prompt, payload)
    if ai_answer:
        return ai_answer

    return (
        "Lectura DOMO: ahora mismo conviene empujar menos volumen y mas piezas con punto de vista. "
        "Para crecer de verdad, convierte cada post en una de estas funciones: que alguien lo comparta por identidad, "
        "lo guarde por criterio, lo comente porque se siente interpelado, o visite tu perfil porque ve una oportunidad de workshop, "
        "consultoria o colaboracion. La siguiente accion: toma tu mejor Reel de cultura visual y conviertelo en carrusel guardable "
        "para Instagram y en mini ensayo para LinkedIn."
    )


def extract_page_text(url: str) -> dict[str, str]:
    try:
        response = requests.get(url, timeout=10, headers={"User-Agent": "DOMOContentLab/1.0"})
        response.raise_for_status()
    except requests.RequestException as exc:
        return {"title": url, "text": f"No pude leer el link automaticamente: {exc}"}

    html = response.text[:120000]
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else url
    clean = re.sub(r"<(script|style).*?</\1>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    clean = re.sub(r"<[^>]+>", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return {"title": title, "text": clean[:6000]}


def analyze_link_for_domo(url: str, notes: str, posts: pd.DataFrame) -> dict[str, str]:
    page = extract_page_text(url)
    system_prompt = load_system_prompt()
    payload = {
        "task": "Analiza este link como inspiracion para DOMO y conviertelo en contenido propio.",
        "url": url,
        "page_title": page["title"],
        "page_text": page["text"],
        "user_notes": notes,
        "metrics": compact_metrics(posts),
        "return": {
            "domo_angle": "angulo creativo propio, nada copiado",
            "suggested_content": "idea concreta con hook, formato, mecanismo de share/save y CTA",
        },
    }
    ai_answer = ai_complete(system_prompt, payload)
    if ai_answer:
        return {
            "title": page["title"],
            "source_notes": notes or page["text"][:600],
            "domo_angle": ai_answer,
            "suggested_content": ai_answer,
        }
    return {
        "title": page["title"],
        "source_notes": notes or page["text"][:600],
        "domo_angle": "Usar el link como detonante, no como molde. Pregunta DOMO: que dice esto sobre cultura visual, calle, criterio o deseo de marca en LATAM.",
        "suggested_content": "Reel: 'Esto se ve cool, pero lo importante es por que funciona'. Muestra el link, extrae una regla visual y traducela a Cuenca, grafica popular o direccion de arte comercial.",
    }


def analyze_screenshot_for_domo(image_path: str, notes: str, posts: pd.DataFrame) -> str:
    client = get_openai_client()
    if client is None:
        return (
            "Captura guardada. Para lectura con IA visual, agrega OPENAI_API_KEY en .env. "
            "Mientras tanto, registra manualmente alcance, shares, saves, comentarios de calidad y visitas al perfil."
        )

    image_bytes = Path(image_path).read_bytes()
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    response = client.chat.completions.create(
        model=get_secret("OPENAI_VISION_MODEL", get_secret("OPENAI_MODEL", "gpt-4o-mini")),
        messages=[
            {
                "role": "system",
                "content": load_system_prompt()
                + "\nLee capturas de estadisticas de redes. Extrae metricas visibles y da una recomendacion DOMO.",
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "notes": notes,
                                "metrics_context": compact_metrics(posts),
                                "instruction": "Extrae numeros visibles si puedes y explica que funciono, que no, y que probar despues.",
                            },
                            ensure_ascii=False,
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                    },
                ],
            },
        ],
        temperature=0.4,
    )
    return response.choices[0].message.content or "Captura analizada, pero no se genero una lectura."
