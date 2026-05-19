from __future__ import annotations

import os
import json
import socket
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

import cache as cache_store
from assistant import (
    analyze_link_for_domo,
    analyze_screenshot_for_domo,
    answer_as_domo_assistant,
    has_ai_key,
)
from carousel import generate_carousel, slides_to_json
from ideas import generate_ideas
from instagram_api import InstagramAPIError, get_instagram_status, refresh_instagram_to_cache
from linkedin_api import LinkedInAPIError, get_linkedin_status, refresh_linkedin_to_cache
from trend_scout import DEFAULT_TREND_QUERIES, scout_trends, suggest_collabs


DATA_DIR = getattr(cache_store, "DATA_DIR", Path("data.nosync"))
add_action_item = cache_store.add_action_item
add_assistant_note = cache_store.add_assistant_note
add_carousel_draft = cache_store.add_carousel_draft
add_collab_target = cache_store.add_collab_target
add_inspiration = cache_store.add_inspiration
add_manual_post = cache_store.add_manual_post
add_screenshot = cache_store.add_screenshot
add_trend_item = cache_store.add_trend_item
get_connection = cache_store.get_connection
get_action_items = cache_store.get_action_items
get_assistant_notes = cache_store.get_assistant_notes
get_carousel_drafts = cache_store.get_carousel_drafts
get_collab_targets = cache_store.get_collab_targets
get_content_ideas = cache_store.get_content_ideas
get_daily_metrics = cache_store.get_daily_metrics
get_inspirations = cache_store.get_inspirations
get_monetization_signals = cache_store.get_monetization_signals
get_posts = cache_store.get_posts
get_profile_metrics = cache_store.get_profile_metrics
get_screenshots = cache_store.get_screenshots
get_trend_items = cache_store.get_trend_items
initialize_database = cache_store.initialize_database
update_action_status = cache_store.update_action_status


def add_content_idea(conn, idea: dict) -> None:
    """Compatibility layer for older cache.py deployments."""
    if hasattr(cache_store, "add_content_idea"):
        cache_store.add_content_idea(conn, idea)
        return
    add_action_item(
        conn,
        idea.get("title", "Idea DOMO"),
        "Ideas",
        idea.get("strategic_reason", idea.get("hook", "")),
        idea.get("priority", "Media"),
    )


def get_database_mode() -> str:
    if hasattr(cache_store, "get_database_mode"):
        return cache_store.get_database_mode()
    return "SQLite local"


def get_supabase_status() -> dict[str, str]:
    if hasattr(cache_store, "get_supabase_status"):
        return cache_store.get_supabase_status()
    return {
        "mode": "SQLite local",
        "url": "No diagnosticado",
        "key": "No diagnosticado",
        "package": "No diagnosticado",
        "schema": "No diagnosticado",
        "message": "cache.py antiguo: sube el cache.py nuevo para ver diagnóstico completo.",
    }


st.set_page_config(
    page_title="DOMO Content Lab",
    page_icon="D",
    layout="wide",
)


BRAND_COLORS = {
    "ink": "#111111",
    "paper": "#F5F0E8",
    "red": "#E53935",
    "yellow": "#F4C430",
    "blue": "#145C9E",
    "green": "#1B998B",
}


def inject_styles() -> None:
    st.markdown(
        f"""
        <style>
        :root {{
            --md-sys-color-primary: #111111;
            --md-sys-color-on-primary: #fffaf0;
            --md-sys-color-primary-container: #F4C430;
            --md-sys-color-on-primary-container: #111111;
            --md-sys-color-secondary: #145C9E;
            --md-sys-color-tertiary: #1B998B;
            --md-sys-color-error: #E53935;
            --md-sys-color-background: #F5F0E8;
            --md-sys-color-surface: #fffaf0;
            --md-sys-color-surface-container: #F8F2E7;
            --md-sys-color-surface-container-high: #EFE5D7;
            --md-sys-color-outline: rgba(17, 17, 17, 0.18);
            --md-sys-color-outline-variant: rgba(17, 17, 17, 0.10);
            --md-sys-elevation-1: 0 1px 2px rgba(17,17,17,.16), 0 1px 3px rgba(17,17,17,.10);
            --md-sys-elevation-2: 0 2px 6px rgba(17,17,17,.18), 0 6px 18px rgba(17,17,17,.08);
            --md-sys-elevation-3: 0 8px 24px rgba(17,17,17,.16), 0 2px 8px rgba(17,17,17,.10);
            --domo-radius-sm: 10px;
            --domo-radius-md: 16px;
            --domo-radius-lg: 24px;
        }}
        .stApp {{
            background:
                radial-gradient(circle at 18% 0%, rgba(244,196,48,.18), transparent 28%),
                linear-gradient(180deg, #F5F0E8 0%, #FBF7EE 52%, #F5F0E8 100%);
            color: var(--md-sys-color-primary);
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }}
        .block-container {{
            max-width: 1240px;
            padding-top: 2.3rem;
            padding-bottom: 4rem;
        }}
        h1 {{
            letter-spacing: 0 !important;
            font-weight: 900 !important;
            text-transform: uppercase;
            line-height: .96 !important;
            font-size: clamp(2.4rem, 5.4vw, 5.3rem) !important;
            max-width: 980px;
        }}
        h2, h3 {{
            letter-spacing: 0 !important;
            font-weight: 850 !important;
            line-height: 1.05 !important;
        }}
        h2 {{
            font-size: clamp(1.7rem, 3vw, 2.6rem) !important;
        }}
        h3 {{
            font-size: clamp(1.25rem, 2vw, 1.65rem) !important;
        }}
        p, li, label, [data-testid="stMarkdownContainer"] {{
            line-height: 1.55;
        }}
        [data-testid="stHeader"] {{
            background: rgba(17,17,17,.94);
            backdrop-filter: blur(14px);
        }}
        [data-testid="stToolbar"] {{
            right: 1rem;
        }}
        [data-testid="stMetric"] {{
            background: var(--md-sys-color-surface);
            border: 1px solid var(--md-sys-color-outline-variant);
            border-radius: var(--domo-radius-md);
            padding: 16px 18px;
            box-shadow: var(--md-sys-elevation-1);
        }}
        [data-testid="stMetric"] * {{
            color: var(--md-sys-color-primary) !important;
        }}
        [data-testid="stMetricValue"] {{
            color: var(--md-sys-color-primary) !important;
            font-weight: 900 !important;
            font-size: clamp(1.8rem, 3vw, 2.7rem) !important;
        }}
        div[data-testid="stDataFrame"] {{
            border: 1px solid var(--md-sys-color-outline-variant);
            border-radius: var(--domo-radius-md);
            overflow: hidden;
            box-shadow: var(--md-sys-elevation-1);
        }}
        div[data-testid="stExpander"] {{
            border: 1px solid var(--md-sys-color-outline-variant);
            border-radius: var(--domo-radius-md);
            box-shadow: var(--md-sys-elevation-1);
            background: var(--md-sys-color-surface);
        }}
        input, textarea, [data-baseweb="select"] > div, [data-baseweb="input"] > div {{
            border-radius: 14px !important;
        }}
        .domo-hero {{
            background:
                linear-gradient(135deg, rgba(17,17,17,.97) 0%, rgba(17,17,17,.92) 56%, rgba(20,92,158,.92) 100%);
            color: var(--md-sys-color-on-primary);
            border-radius: var(--domo-radius-lg);
            padding: clamp(22px, 4vw, 42px);
            box-shadow: var(--md-sys-elevation-3);
            margin-bottom: 28px;
            position: relative;
            overflow: hidden;
        }}
        .domo-hero:after {{
            content: "";
            position: absolute;
            inset: auto -24px -24px auto;
            width: 180px;
            height: 180px;
            border: 2px solid rgba(244,196,48,.55);
            transform: rotate(-8deg);
        }}
        .domo-hero h1 {{
            color: var(--md-sys-color-on-primary) !important;
            margin: 16px 0 16px;
        }}
        .domo-hero p {{
            color: rgba(255,250,240,.86) !important;
            max-width: 850px;
            font-size: 1.08rem;
            margin: 0;
        }}
        .domo-hero-grid {{
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 10px;
            margin-top: 24px;
            max-width: 880px;
        }}
        .domo-hero-chip {{
            background: rgba(255,250,240,.10);
            border: 1px solid rgba(255,250,240,.16);
            border-radius: 999px;
            color: #fffaf0;
            padding: 10px 14px;
            font-weight: 800;
            text-align: center;
        }}
        .domo-label {{
            display: inline-block;
            background: var(--md-sys-color-primary-container);
            color: var(--md-sys-color-on-primary-container);
            border: 1px solid rgba(17,17,17,.25);
            border-radius: 999px;
            padding: 7px 12px;
            font-weight: 900;
            text-transform: uppercase;
            margin-bottom: 8px;
            font-size: .82rem;
            box-shadow: 0 1px 0 rgba(17,17,17,.22);
        }}
        .domo-note {{
            border-left: 7px solid var(--md-sys-color-error);
            background: var(--md-sys-color-surface);
            border-radius: 0 var(--domo-radius-md) var(--domo-radius-md) 0;
            padding: 16px 18px;
            font-size: 1rem;
            box-shadow: var(--md-sys-elevation-1);
        }}
        .domo-action {{
            background: var(--md-sys-color-surface);
            border: 1px solid var(--md-sys-color-outline-variant);
            border-radius: var(--domo-radius-md);
            padding: 18px;
            min-height: 168px;
            box-shadow: var(--md-sys-elevation-1);
            transition: transform .14s ease, box-shadow .14s ease;
        }}
        .domo-action:hover {{
            transform: translateY(-2px);
            box-shadow: var(--md-sys-elevation-2);
        }}
        .domo-action strong {{
            display: block;
            font-size: 1.05rem;
            margin-top: 10px;
            line-height: 1.2;
        }}
        .domo-action p {{
            margin-bottom: 0;
            color: rgba(17,17,17,.72);
        }}
        .domo-launch {{
            background: var(--md-sys-color-primary);
            color: var(--md-sys-color-on-primary);
            border-radius: var(--domo-radius-lg);
            border: 1px solid rgba(255,250,240,.10);
            box-shadow: var(--md-sys-elevation-2);
            padding: 20px;
            min-height: 175px;
            margin-bottom: 12px;
            transition: transform .14s ease, box-shadow .14s ease;
        }}
        .domo-launch:hover {{
            transform: translateY(-2px);
            box-shadow: var(--md-sys-elevation-3);
        }}
        .domo-launch h3 {{
            color: var(--md-sys-color-on-primary) !important;
            margin: 8px 0;
            font-size: 1.15rem;
        }}
        .domo-launch p {{
            color: rgba(255,250,240,.82) !important;
            margin: 0;
        }}
        .domo-launch .domo-badge {{
            background: var(--md-sys-color-primary-container);
            color: var(--md-sys-color-on-primary-container);
        }}
        .domo-pill {{
            display: inline-block;
            background: var(--md-sys-color-error);
            color: white;
            border-radius: 999px;
            padding: 4px 9px;
            font-weight: 900;
            margin-right: 5px;
            font-size: .78rem;
        }}
        .domo-output {{
            background: var(--md-sys-color-surface);
            border: 1px solid var(--md-sys-color-outline-variant);
            border-radius: var(--domo-radius-lg);
            box-shadow: var(--md-sys-elevation-2);
            padding: 22px;
            margin: 18px 0;
        }}
        .domo-output-top {{
            display: flex;
            justify-content: space-between;
            gap: 10px;
            align-items: flex-start;
            margin-bottom: 12px;
        }}
        .domo-badge {{
            display: inline-block;
            border: 1px solid rgba(17,17,17,.18);
            background: var(--md-sys-color-primary-container);
            color: var(--md-sys-color-on-primary-container);
            border-radius: 999px;
            padding: 5px 10px;
            font-weight: 900;
            text-transform: uppercase;
            font-size: 0.82rem;
        }}
        .domo-slide {{
            background:
                linear-gradient(160deg, #111111 0%, #202124 68%, #145C9E 100%);
            color: var(--md-sys-color-on-primary);
            border-radius: var(--domo-radius-lg);
            padding: 22px;
            min-height: 230px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            border: 1px solid rgba(255,250,240,.10);
            box-shadow: var(--md-sys-elevation-3);
            margin-bottom: 16px;
        }}
        .domo-slide-number {{
            color: var(--md-sys-color-primary-container);
            font-weight: 900;
            text-transform: uppercase;
            font-size: 0.86rem;
        }}
        .domo-slide-text {{
            color: #fffaf0;
            font-weight: 900;
            text-transform: uppercase;
            font-size: 1.65rem;
            line-height: 1.08;
            margin: 14px 0;
        }}
        .domo-slide-detail {{
            color: #fffaf0;
            border-top: 1px solid rgba(255, 250, 240, 0.35);
            padding-top: 10px;
            font-size: 0.96rem;
        }}
        .domo-slide-detail strong {{
            color: var(--md-sys-color-primary-container);
        }}
        .domo-step {{
            background: var(--md-sys-color-surface-container);
            border: 1px solid var(--md-sys-color-outline-variant);
            border-radius: var(--domo-radius-md);
            padding: 18px;
            min-height: 150px;
            box-shadow: var(--md-sys-elevation-1);
        }}
        .domo-step-number {{
            display: inline-block;
            background: var(--md-sys-color-primary);
            color: var(--md-sys-color-on-primary);
            border-radius: 999px;
            min-width: 28px;
            height: 28px;
            text-align: center;
            line-height: 28px;
            font-weight: 900;
            margin-bottom: 10px;
        }}
        .domo-step h3 {{
            font-size: 1rem;
            margin: 2px 0 8px;
        }}
        .domo-read {{
            background: var(--md-sys-color-surface);
            border: 1px solid var(--md-sys-color-outline-variant);
            border-radius: var(--domo-radius-lg);
            padding: 22px;
            box-shadow: var(--md-sys-elevation-2);
            min-height: 170px;
        }}
        .domo-read strong {{
            display: block;
            margin-bottom: 8px;
            font-size: 1.05rem;
        }}
        .domo-callout {{
            background: var(--md-sys-color-primary-container);
            border: 1px solid rgba(17,17,17,.18);
            border-radius: var(--domo-radius-lg);
            box-shadow: var(--md-sys-elevation-2);
            padding: 20px;
            margin: 12px 0 22px;
            font-weight: 800;
        }}
        .domo-small {{
            font-size: 0.92rem;
            opacity: 0.86;
        }}
        .domo-section {{
            background: rgba(255,250,240,.72);
            border: 1px solid var(--md-sys-color-outline-variant);
            border-radius: var(--domo-radius-lg);
            padding: clamp(16px, 3vw, 26px);
            box-shadow: var(--md-sys-elevation-1);
            margin: 18px 0;
        }}
        section[data-testid="stSidebar"] {{
            background: rgba(255,250,240,.96);
            border-right: 1px solid var(--md-sys-color-outline-variant);
            box-shadow: var(--md-sys-elevation-2);
        }}
        section[data-testid="stSidebar"] * {{
            color: var(--md-sys-color-primary) !important;
        }}
        section[data-testid="stSidebar"] code {{
            color: var(--md-sys-color-tertiary) !important;
            background: var(--md-sys-color-primary) !important;
            border-radius: 12px;
            padding: 8px !important;
        }}
        section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 {{
            font-size: .92rem !important;
            text-transform: uppercase;
            letter-spacing: .02em !important;
        }}
        div[role="radiogroup"] label {{
            color: var(--md-sys-color-primary) !important;
            font-weight: 760 !important;
            opacity: 1 !important;
            border-radius: 999px !important;
            padding: 8px 10px !important;
            min-height: 42px;
        }}
        div[role="radiogroup"] p {{
            color: var(--md-sys-color-primary) !important;
        }}
        .stButton > button {{
            background: var(--md-sys-color-primary) !important;
            color: var(--md-sys-color-on-primary) !important;
            border: 0 !important;
            border-radius: 999px !important;
            font-weight: 850 !important;
            min-height: 42px;
            padding: 0 18px !important;
            box-shadow: var(--md-sys-elevation-1);
            transition: transform .12s ease, box-shadow .12s ease, background .12s ease;
        }}
        .stButton > button:hover {{
            transform: translateY(-1px);
            box-shadow: var(--md-sys-elevation-2);
            background: #2B2B2B !important;
        }}
        .stButton > button * {{
            color: var(--md-sys-color-on-primary) !important;
        }}
        button[kind="primary"], .stDownloadButton > button {{
            background: var(--md-sys-color-secondary) !important;
            color: white !important;
        }}
        .stTabs [data-baseweb="tab-list"] {{
            gap: 8px;
            background: var(--md-sys-color-surface-container-high);
            padding: 7px;
            border-radius: 999px;
            width: fit-content;
        }}
        .stTabs [data-baseweb="tab"] {{
            border-radius: 999px;
            padding: 8px 16px;
            font-weight: 800;
        }}
        .stTabs [aria-selected="true"] {{
            background: var(--md-sys-color-surface);
            box-shadow: var(--md-sys-elevation-1);
        }}
        a {{
            color: var(--md-sys-color-secondary) !important;
            font-weight: 800;
        }}
        @media (max-width: 760px) {{
            .block-container {{
                padding-left: 1rem;
                padding-right: 1rem;
                padding-top: 1.3rem;
            }}
            h1 {{
                font-size: 2.35rem !important;
                line-height: 1.02 !important;
            }}
            [data-testid="column"] {{
                width: 100% !important;
                flex: 1 1 100% !important;
            }}
            .domo-action,
            .domo-step,
            .domo-read,
            .domo-launch {{
                min-height: auto;
            }}
            .domo-hero {{
                border-radius: 18px;
                padding: 22px;
            }}
            .domo-hero-grid {{
                grid-template-columns: 1fr;
            }}
            .stTabs [data-baseweb="tab-list"] {{
                width: 100%;
                overflow-x: auto;
                border-radius: 16px;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def get_secret(name: str, default: str = "") -> str:
    try:
        return st.secrets.get(name, os.getenv(name, default))
    except Exception:
        return os.getenv(name, default)


def require_login() -> bool:
    password = get_secret("APP_PASSWORD", "")
    if not password:
        return True

    if st.session_state.get("authenticated"):
        return True

    st.markdown('<span class="domo-label">DOMO Content Lab</span>', unsafe_allow_html=True)
    st.title("Acceso privado")
    st.write("Este sistema guarda estrategia, datos y oportunidades. Entra con la clave privada.")
    attempt = st.text_input("Clave", type="password")
    if st.button("Entrar", type="primary"):
        if attempt == password:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Clave incorrecta.")
    return False


def as_percent(value: float) -> str:
    return f"{value:.1f}%"


def score_health(value: float, target: float) -> str:
    if value >= target:
        return "Fuerte"
    if value >= target * 0.65:
        return "En progreso"
    return "Necesita trabajo"


def safe_mean(frame: pd.DataFrame, column: str) -> float:
    if frame.empty or column not in frame.columns:
        return 0.0
    return float(frame[column].fillna(0).mean())


def with_strategic_score(posts: pd.DataFrame) -> pd.DataFrame:
    if posts.empty:
        return posts.copy()
    scored = posts.copy()
    for column in ["share_rate", "save_rate", "quality_comment_rate", "profile_visit_rate"]:
        if column not in scored.columns:
            scored[column] = 0
    scored["strategic_score"] = (
        scored["share_rate"] * 2.0
        + scored["save_rate"] * 1.8
        + scored["quality_comment_rate"] * 1.6
        + scored["profile_visit_rate"] * 1.4
    ).round(2)
    return scored


def best_group(posts: pd.DataFrame, group: str, metric: str) -> tuple[str, float]:
    if posts.empty or group not in posts.columns or metric not in posts.columns:
        return "Sin datos", 0.0
    grouped = posts.groupby(group, as_index=False)[metric].mean().sort_values(metric, ascending=False)
    if grouped.empty:
        return "Sin datos", 0.0
    row = grouped.iloc[0]
    return str(row[group]), float(row[metric])


def build_metric_reading(posts: pd.DataFrame) -> dict[str, str | float | pd.DataFrame]:
    scored = with_strategic_score(posts)
    if scored.empty:
        return {
            "headline": "Todavía falta data para leer patrones.",
            "what_worked": "Sube capturas o conecta APIs para empezar a comparar.",
            "what_failed": "Sin historial no conviene sacar conclusiones.",
            "next_move": "Registra 5 contenidos recientes y vuelve a esta pantalla.",
            "best_posts": scored,
            "weak_posts": scored,
        }

    avg_share = safe_mean(scored, "share_rate")
    avg_save = safe_mean(scored, "save_rate")
    avg_quality = safe_mean(scored, "quality_comment_rate")
    avg_profile = safe_mean(scored, "profile_visit_rate")
    best_format, best_format_value = best_group(scored, "format", "strategic_score")
    best_pillar, best_pillar_value = best_group(scored, "pillar", "strategic_score")
    top = scored.sort_values("strategic_score", ascending=False).head(5)
    weak = scored.sort_values("strategic_score", ascending=True).head(5)
    top_title = str(top.iloc[0]["title"]) if not top.empty else "Sin ganador claro"

    weak_signals = []
    if avg_share < 1.8:
        weak_signals.append("shares")
    if avg_save < 2.4:
        weak_signals.append("guardados")
    if avg_quality < 1.2:
        weak_signals.append("comentarios de calidad")
    if avg_profile < 3.0:
        weak_signals.append("visitas al perfil")

    if weak_signals:
        what_failed = "La señal débil principal está en: " + ", ".join(weak_signals) + "."
    else:
        what_failed = "No hay una señal crítica rota; el siguiente paso es repetir lo que funciona con más intención."

    if avg_save < avg_share:
        next_move = "Convierte el contenido ganador en carrusel guardable con checklist, frases o marco de criterio."
    elif avg_share < avg_save:
        next_move = "Convierte el contenido útil en una pieza más identitaria: postura fuerte, calle, cultura visual LATAM y frase compartible."
    elif avg_profile < 3.0:
        next_move = "Agrega cierre comercial claro: workshop, consultoría creativa o colaboración con marcas."
    else:
        next_move = "Repite el pilar ganador en dos formatos: Reel para alcance y carrusel/documento para guardados."

    return {
        "headline": f"El sistema está detectando más fuerza en {best_pillar} y formato {best_format}.",
        "what_worked": f"El contenido con mejor señal es: {top_title}. Puntuación estratégica: {float(top.iloc[0]['strategic_score']):.2f}.",
        "what_failed": what_failed,
        "next_move": next_move,
        "best_format": best_format,
        "best_format_value": best_format_value,
        "best_pillar": best_pillar,
        "best_pillar_value": best_pillar_value,
        "best_posts": top,
        "weak_posts": weak,
    }


def load_data():
    initialize_database()
    conn = get_connection()
    posts = get_posts(conn)
    daily = get_daily_metrics(conn)
    profile = get_profile_metrics(conn)
    monetization = get_monetization_signals(conn)
    ideas = get_content_ideas(conn)
    screenshots = get_screenshots(conn)
    inspirations = get_inspirations(conn)
    assistant_notes = get_assistant_notes(conn)
    trends = get_trend_items(conn)
    collabs = get_collab_targets(conn)
    action_items = get_action_items(conn)
    carousels = get_carousel_drafts(conn)
    conn.close()
    return (
        posts,
        daily,
        profile,
        monetization,
        ideas,
        screenshots,
        inspirations,
        assistant_notes,
        trends,
        collabs,
        action_items,
        carousels,
    )


def metric_card(label: str, value: str, help_text: str = "") -> None:
    st.metric(label, value, help=help_text)


def render_header() -> None:
    st.markdown(
        """
        <div class="domo-hero">
            <span class="domo-label">DOMO Content Lab</span>
            <h1>Asistente de crecimiento visual</h1>
            <p>
            Tu centro de decisiones para Instagram y LinkedIn: entiende qué pegó,
            qué corregir y qué contenido crear para mover shares, guardados,
            comentarios buenos, perfil y oportunidades comerciales.
            </p>
            <div class="domo-hero-grid">
                <div class="domo-hero-chip">Leer métricas</div>
                <div class="domo-hero-chip">Crear contenido</div>
                <div class="domo-hero-chip">Guardar aprendizaje</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_mobile_hint() -> None:
    db_mode = get_supabase_status()["mode"]
    if os.getenv("STREAMLIT_SERVER_HEADLESS") or os.getenv("HOSTNAME"):
        st.sidebar.markdown("### App online")
        st.sidebar.write("Abierta desde Streamlit Cloud.")
        st.sidebar.markdown("### IA")
        st.sidebar.write("Key configurada. Si falla, revisa saldo/cuota en OpenAI." if has_ai_key() else "Sin API key: funciona con estrategia local. Con API key analiza mejor capturas y links.")
        st.sidebar.markdown("### Memoria")
        st.sidebar.write("Supabase conectado." if db_mode == "Supabase" else "SQLite local. Conecta Supabase para historial permanente.")
        return

    port = os.getenv("DOMO_STREAMLIT_PORT", "8501")
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
    except OSError:
        local_ip = "TU-IP-LOCAL"
    st.sidebar.markdown("### Abrir en el celular")
    st.sidebar.write("Conecta el celular al mismo Wi-Fi y abre:")
    st.sidebar.code(f"http://{local_ip}:{port}")
    st.sidebar.caption("En iPhone o Android puedes usar 'Agregar a pantalla de inicio' para sentirlo como app.")
    st.sidebar.markdown("### IA")
    st.sidebar.write("Key configurada. Si falla, revisa saldo/cuota en OpenAI." if has_ai_key() else "Sin API key: funciona con estrategia local. Con API key analiza mejor capturas y links.")
    st.sidebar.markdown("### Memoria")
    st.sidebar.write("Supabase conectado." if db_mode == "Supabase" else "SQLite local. Conecta Supabase para historial permanente.")


def render_command_center(posts: pd.DataFrame, action_items: pd.DataFrame) -> None:
    st.subheader("Centro de acción")
    reading = build_metric_reading(posts)
    avg_share = safe_mean(posts, "share_rate")
    avg_save = safe_mean(posts, "save_rate")
    avg_comments = safe_mean(posts, "quality_comment_rate")

    st.markdown(
        f"""
        <div class="domo-callout">
            Hoy: {reading["next_move"]}
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("#### Flujo simple")
    workflow = [
        ("1", "Leer", "Revisa qué está funcionando y qué señal está floja."),
        ("2", "Decidir", "Elige una idea según shares, saves, comentarios o leads."),
        ("3", "Crear", "Genera carrusel, post de LinkedIn o guion de Reel."),
        ("4", "Guardar", "Sube métricas/capturas para que el sistema aprenda."),
    ]
    cols = st.columns(4)
    for col, (number, title, text) in zip(cols, workflow):
        with col:
            st.markdown(
                f"""
                <div class="domo-step">
                    <span class="domo-step-number">{number}</span>
                    <h3>{title}</h3>
                    <p>{text}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    launchers = [
        ("Lectura", "Qué pasó", "Diagnóstico de métricas: pegó, no pegó y próximo movimiento."),
        ("Carruseles", "Frases por imagen", "Convierte una idea o link en slides listos para diseñar."),
        ("Asistente", "Estrategia rápida", "Pregúntale qué publicar, repetir o convertir en negocio."),
        ("Inspiración", "Analizar link", "Pega algo que viste y tradúcelo a estilo DOMO."),
        ("Capturas", "Subir métricas", "Guarda screenshots y números para crear memoria."),
        ("Trends", "Radar web", "Busca señales de tu rama para ideas y oportunidades."),
        ("Collabs", "Marcas cool", "Encuentra con quién acercarte y cómo hacerlo."),
    ]

    cols = st.columns(3)
    for index, (target, label, description) in enumerate(launchers):
        with cols[index % 3]:
            st.markdown(
                f"""
                <div class="domo-launch">
                    <span class="domo-badge">{label}</span>
                    <h3>{target}</h3>
                    <p>{description}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button(f"Ir a {target}", key=f"go_{target}"):
                st.session_state["page"] = target
                st.rerun()

    suggested = [
        {
            "title": "Convertir tu mejor Reel en carrusel guardable",
            "area": "Contenido",
            "reason": "Tus Reels mueven atención; el carrusel puede convertir esa atención en saves.",
            "priority": "Alta",
        },
        {
            "title": "Publicar una lectura de calle con cierre para marcas",
            "area": "Autoridad",
            "reason": "DOMO ve el mundo es el territorio más diferenciador para shares y posicionamiento LATAM.",
            "priority": "Alta",
        },
        {
            "title": "Transformar una idea de Instagram en post de LinkedIn",
            "area": "LinkedIn",
            "reason": "LinkedIn está subutilizado y puede atraer consultoría, workshops y collabs.",
            "priority": "Media",
        },
    ]

    st.subheader("Qué hacemos hoy")
    suggested.insert(
        0,
        {
            "title": str(reading["next_move"]),
            "area": "Lectura",
            "reason": str(reading["headline"]),
            "priority": "Alta",
        },
    )
    cols = st.columns(4)
    for col, item in zip(cols, suggested):
        with col:
            st.markdown(
                f"""
                <div class="domo-action">
                    <span class="domo-pill">{item["priority"]}</span>
                    <strong>{item["title"]}</strong>
                    <p>{item["reason"]}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Guardar acción", key=f"save_{item['title']}"):
                conn = get_connection()
                add_action_item(conn, item["title"], item["area"], item["reason"], item["priority"])
                conn.close()
                st.success("Acción guardada.")

    st.subheader("Pulso de crecimiento")
    cols = st.columns(3)
    cols[0].metric("Share rate", as_percent(avg_share), help="Meta: que la gente lo quiera mandar a alguien.")
    cols[1].metric("Save rate", as_percent(avg_save), help="Meta: que la pieza sea referencia útil.")
    cols[2].metric("Comentarios de calidad", as_percent(avg_comments), help="Meta: conversación real, no solo aplauso.")

    st.subheader("Acciones guardadas")
    if action_items.empty:
        st.info("Todavía no guardas acciones. Empieza con una de arriba.")
    else:
        edited = st.data_editor(
            action_items[["id", "title", "area", "reason", "priority", "status", "created_at"]],
            hide_index=True,
            use_container_width=True,
            disabled=["id", "title", "area", "reason", "priority", "created_at"],
            column_config={
                "status": st.column_config.SelectboxColumn("status", options=["Pendiente", "En proceso", "Hecho", "Descartado"])
            },
        )
        if st.button("Actualizar estados"):
            conn = get_connection()
            for _, row in edited.iterrows():
                update_action_status(conn, int(row["id"]), row["status"])
            conn.close()
            st.success("Estados actualizados.")


def render_summary(posts: pd.DataFrame, profile: pd.DataFrame) -> None:
    st.subheader("Pulso general")
    total_posts = len(posts)
    avg_engagement = posts["engagement_rate"].mean()
    avg_save_rate = posts["save_rate"].mean()
    avg_share_rate = posts["share_rate"].mean()
    profile_visits = int(profile["profile_visits"].sum())

    cols = st.columns(5)
    with cols[0]:
        metric_card("Posts medidos", str(total_posts))
    with cols[1]:
        metric_card("Engagement promedio", as_percent(avg_engagement))
    with cols[2]:
        metric_card("Share rate", as_percent(avg_share_rate), "Señal de recomendación cultural.")
    with cols[3]:
        metric_card("Save rate", as_percent(avg_save_rate), "Señal de valor práctico o referencia.")
    with cols[4]:
        metric_card("Visitas al perfil", f"{profile_visits:,}")

    st.subheader("Diagnóstico rápido")
    diagnosis = pd.DataFrame(
        [
            {"Señal": "Shares", "Estado": score_health(avg_share_rate, 1.8), "Lectura": "Suben cuando una idea representa a la audiencia."},
            {"Señal": "Saves", "Estado": score_health(avg_save_rate, 2.4), "Lectura": "Suben con marcos, checklists, referencias y criterios reutilizables."},
            {"Señal": "Comentarios", "Estado": score_health(posts["quality_comment_rate"].mean(), 1.2), "Lectura": "Importa más la calidad que el volumen."},
            {"Señal": "Perfil", "Estado": score_health(profile["profile_visit_rate"].mean(), 3.0), "Lectura": "Debe conectar con workshops, consultoría y colaboraciones."},
        ]
    )
    st.dataframe(diagnosis, hide_index=True, use_container_width=True)


def render_growth_reading(posts: pd.DataFrame, profile: pd.DataFrame) -> None:
    st.subheader("Lectura de métricas")
    st.write("Aquí la app traduce los números en decisiones: qué pegó, qué no pegó y qué hacer distinto.")

    reading = build_metric_reading(posts)
    cols = st.columns(3)
    with cols[0]:
        st.markdown(
            f"""
            <div class="domo-read">
                <strong>Qué está pasando</strong>
                <p>{reading["headline"]}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with cols[1]:
        st.markdown(
            f"""
            <div class="domo-read">
                <strong>Qué pegó</strong>
                <p>{reading["what_worked"]}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with cols[2]:
        st.markdown(
            f"""
            <div class="domo-read">
                <strong>Qué corregir</strong>
                <p>{reading["what_failed"]}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        f"""
        <div class="domo-callout">
            Próximo movimiento recomendado: {reading["next_move"]}
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("Share rate", as_percent(safe_mean(posts, "share_rate")))
    col_b.metric("Save rate", as_percent(safe_mean(posts, "save_rate")))
    col_c.metric("Comentarios calidad", as_percent(safe_mean(posts, "quality_comment_rate")))
    col_d.metric("Visitas perfil", as_percent(safe_mean(posts, "profile_visit_rate")))

    st.markdown("#### Decisiones para crear contenido")
    decisions = [
        {
            "decision": "Repetir",
            "when": "Si el post tiene score alto",
            "action": "Haz una secuela: mismo criterio, nuevo ejemplo visual.",
        },
        {
            "decision": "Convertir",
            "when": "Si un Reel tiene atención pero pocos guardados",
            "action": "Haz carrusel con frases, checklist o marco de análisis.",
        },
        {
            "decision": "Corregir",
            "when": "Si tiene likes pero no comentarios ni visitas",
            "action": "Cierra con una pregunta específica o una invitación a workshop/collab.",
        },
        {
            "decision": "Llevar a LinkedIn",
            "when": "Si el contenido demuestra criterio profesional",
            "action": "Transforma la idea en mini ensayo o documento con caso aplicado.",
        },
    ]
    st.dataframe(pd.DataFrame(decisions), hide_index=True, use_container_width=True)

    st.markdown("#### Ganadores")
    best_posts = reading["best_posts"]
    if isinstance(best_posts, pd.DataFrame) and not best_posts.empty:
        st.dataframe(
            best_posts[
                [
                    "date",
                    "platform",
                    "title",
                    "pillar",
                    "format",
                    "share_rate",
                    "save_rate",
                    "quality_comment_rate",
                    "profile_visit_rate",
                    "strategic_score",
                ]
            ],
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.info("Todavía no hay suficientes posts para detectar ganadores.")

    st.markdown("#### Piezas para revisar")
    weak_posts = reading["weak_posts"]
    if isinstance(weak_posts, pd.DataFrame) and not weak_posts.empty:
        st.dataframe(
            weak_posts[
                [
                    "date",
                    "platform",
                    "title",
                    "pillar",
                    "format",
                    "share_rate",
                    "save_rate",
                    "quality_comment_rate",
                    "profile_visit_rate",
                    "strategic_score",
                ]
            ],
            hide_index=True,
            use_container_width=True,
        )

    st.markdown("#### Guardar como acción")
    if st.button("Guardar próximo movimiento", type="primary"):
        conn = get_connection()
        add_action_item(
            conn,
            str(reading["next_move"]),
            "Lectura de métricas",
            str(reading["headline"]),
            "Alta",
        )
        conn.close()
        st.success("Acción guardada en Inicio.")


def render_trends(posts: pd.DataFrame, daily: pd.DataFrame) -> None:
    st.subheader("Tendencias por día")
    fig = px.line(
        daily,
        x="date",
        y=["reach", "profile_visits", "website_clicks"],
        markers=True,
        color_discrete_sequence=[BRAND_COLORS["blue"], BRAND_COLORS["red"], BRAND_COLORS["green"]],
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Qué formatos empujan qué señal")
    grouped = posts.groupby("format", as_index=False)[["engagement_rate", "share_rate", "save_rate", "quality_comment_rate"]].mean()
    fig = px.bar(
        grouped,
        x="format",
        y=["engagement_rate", "share_rate", "save_rate", "quality_comment_rate"],
        barmode="group",
        color_discrete_sequence=[BRAND_COLORS["red"], BRAND_COLORS["yellow"], BRAND_COLORS["blue"], BRAND_COLORS["green"]],
    )
    st.plotly_chart(fig, use_container_width=True)


def render_audience(profile: pd.DataFrame) -> None:
    st.subheader("Audiencia y señales de intención")
    profile_by_platform = profile.groupby("platform", as_index=False)[["followers", "profile_visits", "website_clicks", "dm_leads"]].sum()
    st.dataframe(profile_by_platform, hide_index=True, use_container_width=True)

    fig = px.bar(
        profile_by_platform,
        x="platform",
        y=["profile_visits", "website_clicks", "dm_leads"],
        barmode="group",
        color_discrete_sequence=[BRAND_COLORS["red"], BRAND_COLORS["blue"], BRAND_COLORS["green"]],
    )
    st.plotly_chart(fig, use_container_width=True)

    st.info("LinkedIn se trata como espacio de autoridad: menos frecuencia, más criterio y casos aplicados.")


def render_posts(posts: pd.DataFrame) -> None:
    st.subheader("Posts")
    platform = st.multiselect("Plataforma", sorted(posts["platform"].unique()), default=sorted(posts["platform"].unique()))
    pillar = st.multiselect("Pilar", sorted(posts["pillar"].unique()), default=sorted(posts["pillar"].unique()))
    format_filter = st.multiselect("Formato", sorted(posts["format"].unique()), default=sorted(posts["format"].unique()))

    filtered = posts[
        posts["platform"].isin(platform)
        & posts["pillar"].isin(pillar)
        & posts["format"].isin(format_filter)
    ].copy()

    filtered = with_strategic_score(filtered)
    filtered = filtered.sort_values("strategic_score", ascending=False)

    st.dataframe(
        filtered[
            [
                "date",
                "platform",
                "title",
                "pillar",
                "format",
                "engagement_rate",
                "share_rate",
                "save_rate",
                "quality_comment_rate",
                "profile_visit_rate",
                "strategic_score",
            ]
        ],
        hide_index=True,
        use_container_width=True,
    )


def render_capture_lab(posts: pd.DataFrame, screenshots: pd.DataFrame) -> None:
    st.subheader("Capturas y registro de avance")
    st.write("Sube capturas de estadísticas, registra los números principales y deja que el sistema guarde el historial.")

    with st.form("manual_metrics_form"):
        st.markdown("#### Registrar post o captura")
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            date = st.date_input("Fecha")
            platform = st.selectbox("Plataforma", ["Instagram", "LinkedIn", "TikTok", "Otra"])
            title = st.text_input("Nombre del contenido", placeholder="Ej: Reel del rótulo popular")
            pillar = st.selectbox("Pilar", ["Así pienso yo", "Creatividad para todos", "DOMO ve el mundo"])
        with col_b:
            format_name = st.selectbox("Formato", ["Reel", "Carrusel", "Post texto", "Documento", "Historia", "Otro"])
            weekday = st.selectbox("Día", ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"])
            hour = st.number_input("Hora de publicación", min_value=0, max_value=23, value=19)
            reach = st.number_input("Alcance", min_value=1, value=1000)
        with col_c:
            likes = st.number_input("Likes", min_value=0, value=0)
            comments = st.number_input("Comentarios", min_value=0, value=0)
            quality_comments = st.number_input("Comentarios de calidad", min_value=0, value=0)
            shares = st.number_input("Shares", min_value=0, value=0)
            saves = st.number_input("Guardados", min_value=0, value=0)
            profile_visits = st.number_input("Visitas al perfil", min_value=0, value=0)
            website_clicks = st.number_input("Clicks o DMs útiles", min_value=0, value=0)

        notes = st.text_area("Qué viste o sentiste que pasó", placeholder="Ej: mucha gente reaccionó, pero pocos guardaron.")
        uploaded = st.file_uploader("Captura de estadísticas", type=["png", "jpg", "jpeg", "webp"])
        analyze_with_ai = st.checkbox("Pedir lectura IA de la captura", value=False)
        submitted = st.form_submit_button("Guardar registro", type="primary")

    if submitted:
        conn = get_connection()
        add_manual_post(
            conn,
            date.isoformat(),
            platform,
            title or "Contenido sin nombre",
            pillar,
            format_name,
            weekday,
            int(hour),
            int(reach),
            int(likes),
            int(comments),
            int(quality_comments),
            int(shares),
            int(saves),
            int(profile_visits),
            int(website_clicks),
        )
        image_path = ""
        ai_reading = ""
        if uploaded is not None:
            uploads_dir = DATA_DIR / "screenshots"
            uploads_dir.mkdir(parents=True, exist_ok=True)
            safe_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded.name}".replace(" ", "_")
            image_path = str(uploads_dir / safe_name)
            Path(image_path).write_bytes(uploaded.getbuffer())
            if analyze_with_ai:
                ai_reading = analyze_screenshot_for_domo(image_path, notes, posts)
            add_screenshot(conn, date.isoformat(), platform, title or "Contenido sin nombre", image_path, notes, ai_reading)
        conn.close()
        st.success("Registro guardado. Ya entra al historial del dashboard.")
        if ai_reading:
            st.markdown("#### Lectura IA")
            st.write(ai_reading)

    st.markdown("#### Historial de capturas")
    if screenshots.empty:
        st.info("Todavía no hay capturas guardadas.")
    else:
        st.dataframe(
            screenshots[["date", "platform", "content_title", "notes", "ai_reading", "created_at"]],
            hide_index=True,
            use_container_width=True,
        )


def render_inspiration_lab(posts: pd.DataFrame, inspirations: pd.DataFrame) -> None:
    st.subheader("Links e inspiración")
    st.write("Pega algo que te parezca chévere. El asistente lo traduce a una idea DOMO sin copiarlo.")

    with st.form("link_form"):
        url = st.text_input("Link", placeholder="https://...")
        notes = st.text_area("Qué te llamó la atención", placeholder="Ej: me gusta el tono, el ritmo, la estética, la forma de explicar.")
        submitted = st.form_submit_button("Analizar link", type="primary")

    if submitted and url:
        analysis = analyze_link_for_domo(url, notes, posts)
        conn = get_connection()
        add_inspiration(
            conn,
            url,
            analysis["title"],
            analysis["source_notes"],
            analysis["domo_angle"],
            analysis["suggested_content"],
        )
        conn.close()
        st.success("Inspiración guardada.")
        st.markdown("#### Lectura DOMO")
        st.write(analysis["domo_angle"])

    st.markdown("#### Banco de inspiración")
    if inspirations.empty:
        st.info("Todavía no hay links guardados.")
    else:
        st.dataframe(
            inspirations[["title", "url", "domo_angle", "suggested_content", "created_at"]],
            hide_index=True,
            use_container_width=True,
        )


def render_trend_lab(posts: pd.DataFrame, trends: pd.DataFrame) -> None:
    st.subheader("Radar de trends")
    st.write("Busca señales web de diseño, cultura visual, marcas y dirección de arte para convertirlas en contenido DOMO.")

    with st.form("trend_form"):
        query = st.selectbox("Búsqueda sugerida", DEFAULT_TREND_QUERIES)
        custom_query = st.text_input("O escribe tu propia búsqueda", placeholder="Ej: marcas cool Ecuador diseño editorial")
        limit = st.slider("Resultados", min_value=3, max_value=10, value=5)
        submitted = st.form_submit_button("Buscar trends", type="primary")

    if submitted:
        final_query = custom_query.strip() or query
        results = scout_trends(final_query, posts, limit=limit)
        if not results:
            st.warning("No encontré resultados ahora. Prueba con una búsqueda más amplia.")
        conn = get_connection()
        for item in results:
            add_trend_item(
                conn,
                item["query"],
                item["title"],
                item["url"],
                item.get("source", ""),
                item.get("domo_reading", ""),
            )
        conn.close()
        if results:
            st.success("Trends guardados en el radar.")
            for item in results:
                with st.container(border=True):
                    st.markdown(f"### {item['title']}")
                    st.caption(item.get("source", ""))
                    st.write(item.get("domo_reading", ""))
                    st.link_button("Abrir fuente", item["url"])

    st.markdown("#### Historial del radar")
    if trends.empty:
        st.info("Todavía no hay trends guardados.")
    else:
        st.dataframe(
            trends[["query", "title", "source", "domo_reading", "created_at"]],
            hide_index=True,
            use_container_width=True,
        )


def render_collab_lab(posts: pd.DataFrame, collabs: pd.DataFrame) -> None:
    st.subheader("Collabs y marcas")
    st.write("Encuentra tipos de marcas, espacios y personas con las que DOMO debería interactuar.")

    col_a, col_b = st.columns([2, 1])
    with col_a:
        focus = st.text_input("Qué tipo de collab quieres buscar", value="marcas cool de diseño, gastronomía, cultura y lifestyle")
    with col_b:
        generate = st.button("Sugerir collabs", type="primary")

    if generate:
        suggestions = suggest_collabs(focus, posts)
        conn = get_connection()
        for item in suggestions:
            add_collab_target(
                conn,
                item["name"],
                item["category"],
                item["why_fit"],
                item["approach"],
                item["priority"],
                item.get("url", ""),
            )
        conn.close()
        st.success("Sugerencias guardadas.")
        for item in suggestions:
            with st.container(border=True):
                st.markdown(f"### {item['name']}")
                st.markdown(f"**Categoría:** {item['category']}")
                st.markdown(f"**Por qué encaja:** {item['why_fit']}")
                st.markdown(f"**Cómo acercarte:** {item['approach']}")
                st.markdown(f"**Prioridad:** {item['priority']}")

    st.markdown("#### Lista de oportunidades")
    if collabs.empty:
        st.info("Todavía no hay collabs guardadas.")
    else:
        st.dataframe(
            collabs[["name", "category", "why_fit", "approach", "priority", "status", "created_at"]],
            hide_index=True,
            use_container_width=True,
        )


def parse_ai_payload(answer: str):
    if not isinstance(answer, str):
        return None
    cleaned = answer.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.replace("json\n", "", 1).replace("JSON\n", "", 1).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None


def render_idea_card(idea: dict) -> None:
    st.markdown(
        f"""
        <div class="domo-output">
            <div class="domo-output-top">
                <span class="domo-badge">{idea.get('pillar', 'DOMO')}</span>
                <span class="domo-badge">{idea.get('priority', 'Media')}</span>
            </div>
            <h3>{idea.get('title', 'Idea DOMO')}</h3>
            <p><strong>Formato:</strong> {idea.get('format', 'Contenido')}</p>
            <p><strong>Hook:</strong> {idea.get('hook', '')}</p>
            <p><strong>Share/save:</strong> {idea.get('share_save_mechanism', '')}</p>
            <p><strong>CTA:</strong> {idea.get('cta', '')}</p>
            <p><strong>Razón:</strong> {idea.get('strategic_reason', '')}</p>
            <p><strong>LinkedIn:</strong> {idea.get('linkedin_adaptation', '')}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_slide_card(slide: dict, key_prefix: str = "slide") -> None:
    visual = slide.get("visual", "")
    microcopy = slide.get("microcopy", "")
    note = slide.get("note", "")
    text = slide.get("text", "")
    number = slide.get("number", "")
    st.markdown(
        f"""
        <div class="domo-slide">
            <div>
                <div class="domo-slide-number">Imagen {number}</div>
                <div class="domo-slide-text">{text}</div>
            </div>
            <div class="domo-slide-detail">
                <div><strong>Visual:</strong> {visual}</div>
                <div><strong>Texto pequeño:</strong> {microcopy}</div>
                <div><strong>Nota:</strong> {note}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.text_area(
        f"Texto para copiar - Imagen {number}",
        text,
        height=90,
        key=f"{key_prefix}_copy_{number}_{abs(hash(text))}",
    )
    st.download_button(
        f"Descargar texto imagen {number}",
        data=text.encode("utf-8"),
        file_name=f"domo_slide_{number}.txt",
        mime="text/plain",
        key=f"{key_prefix}_download_{number}_{abs(hash(text))}",
    )


def render_ai_answer(answer: str) -> None:
    payload = parse_ai_payload(answer)
    if not payload:
        st.write(answer)
        return

    if isinstance(payload.get("ideas"), list):
        for idea in payload["ideas"]:
            render_idea_card(idea)
            if isinstance(idea.get("slides"), list):
                st.markdown("#### Frases por imagen")
                for slide in idea["slides"]:
                    render_slide_card(slide, key_prefix=f"idea_{idea.get('title', 'idea')}")
        return

    if isinstance(payload.get("slides"), list):
        st.markdown(f"### {payload.get('title', 'Carrusel DOMO')}")
        if payload.get("objective"):
            st.markdown(f"**Objetivo:** {payload['objective']}")
        for slide in payload["slides"]:
            render_slide_card(slide, key_prefix=f"ai_{payload.get('title', 'carousel')}")
        if payload.get("caption"):
            st.markdown("#### Caption")
            st.write(payload["caption"])
        if payload.get("cta"):
            st.markdown("#### CTA")
            st.write(payload["cta"])
        return

    for key, value in payload.items():
        pretty_key = key.replace("_", " ").title()
        st.markdown(f"**{pretty_key}:**")
        if isinstance(value, (dict, list)):
            st.json(value)
        else:
            st.write(value)


def carousel_to_script(carousel: dict) -> str:
    lines = [
        f"TITULO: {carousel.get('title', 'Carrusel DOMO')}",
        f"OBJETIVO: {carousel.get('objective', '')}",
        "",
        "SLIDES",
    ]
    for slide in carousel.get("slides", []):
        lines.extend(
            [
                "",
                f"IMAGEN {slide.get('number', '')}",
                f"FRASE: {slide.get('text', '')}",
                f"VISUAL: {slide.get('visual', '')}",
                f"TEXTO PEQUENO: {slide.get('microcopy', '')}",
                f"NOTA: {slide.get('note', '')}",
            ]
        )
    lines.extend(
        [
            "",
            "CAPTION",
            carousel.get("caption", ""),
            "",
            "CTA",
            carousel.get("cta", ""),
        ]
    )
    return "\n".join(lines)


def render_assistant(posts: pd.DataFrame, assistant_notes: pd.DataFrame) -> None:
    st.subheader("Asistente DOMO")
    st.write("Pregúntale qué publicar, qué repetir, qué dejar de hacer o cómo convertir una idea en contenido que venda.")

    question = st.text_area(
        "Pregunta",
        placeholder="Ej: quiero crecer en shares y conseguir colaboraciones con marcas cool, qué hago esta semana?",
    )
    if st.button("Responder como estratega DOMO", type="primary") and question:
        answer = answer_as_domo_assistant(question, posts)
        conn = get_connection()
        add_assistant_note(conn, question, answer)
        conn.close()
        st.markdown("#### Respuesta")
        render_ai_answer(answer)

    st.markdown("#### Memoria del asistente")
    if assistant_notes.empty:
        st.info("Aún no hay conversaciones guardadas.")
    else:
        st.dataframe(
            assistant_notes[["question", "answer", "created_at"]],
            hide_index=True,
            use_container_width=True,
        )


def render_data_center(
    posts: pd.DataFrame,
    daily: pd.DataFrame,
    profile: pd.DataFrame,
    screenshots: pd.DataFrame,
    inspirations: pd.DataFrame,
    trends: pd.DataFrame,
    collabs: pd.DataFrame,
) -> None:
    st.subheader("Data Center")
    st.write("Este es el archivo vivo de todo lo que el sistema aprende.")

    section = st.selectbox(
        "Qué quieres revisar",
        ["Posts", "Días", "Audiencia", "Capturas", "Inspiración", "Trends", "Collabs"],
    )
    tables = {
        "Posts": posts,
        "Días": daily,
        "Audiencia": profile,
        "Capturas": screenshots,
        "Inspiración": inspirations,
        "Trends": trends,
        "Collabs": collabs,
    }
    selected = tables[section]
    st.dataframe(selected, hide_index=True, use_container_width=True)

    csv = selected.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Descargar CSV",
        data=csv,
        file_name=f"domo_{section.lower()}.csv",
        mime="text/csv",
    )


def render_admin() -> None:
    st.subheader("Admin")
    st.write("Panel de salud del sistema. Aquí ves qué está listo y qué falta para operación 100%.")
    is_cloud = bool(os.getenv("HOSTNAME") or os.getenv("STREAMLIT_SERVER_HEADLESS"))
    instagram_ready = bool(get_secret("INSTAGRAM_ACCESS_TOKEN", "") and get_secret("INSTAGRAM_BUSINESS_ACCOUNT_ID", ""))
    linkedin_ready = bool(get_secret("LINKEDIN_ACCESS_TOKEN", ""))
    supabase_status = get_supabase_status()
    database_mode = supabase_status["mode"]
    persistent_db = database_mode == "Supabase"
    checks = pd.DataFrame(
        [
            {"Área": "App online", "Estado": "Lista" if is_cloud else "Local", "Para qué sirve": "Abrir desde celular/oficina."},
            {"Área": "IA", "Estado": "Lista" if has_ai_key() else "Falta OPENAI_API_KEY", "Para qué sirve": "Ideas, carruseles, links, asistente."},
            {"Área": "Instagram API", "Estado": "Configurada" if instagram_ready else "Pendiente", "Para qué sirve": "Actualizar métricas casi automático."},
            {"Área": "LinkedIn API", "Estado": "Lista para probar" if linkedin_ready else "Opcional/manual", "Para qué sirve": "Traer señales de autoridad y consultoría."},
            {"Área": "Datos persistentes", "Estado": "Supabase conectado" if persistent_db else database_mode, "Para qué sirve": "No perder historial al reiniciar."},
            {"Área": "Capturas", "Estado": "Funciona manual", "Para qué sirve": "Subir screenshots y registrar métricas."},
            {"Área": "Carruseles", "Estado": "Listo", "Para qué sirve": "Generar frases por imagen y guion."},
        ]
    )
    st.dataframe(checks, hide_index=True, use_container_width=True)

    st.markdown("#### Diagnóstico Supabase")
    st.dataframe(
        pd.DataFrame(
            [
                {"Punto": "URL", "Estado": supabase_status["url"]},
                {"Punto": "Service role key", "Estado": supabase_status["key"]},
                {"Punto": "Paquete Python", "Estado": supabase_status["package"]},
                {"Punto": "Tablas SQL", "Estado": supabase_status["schema"]},
            ]
        ),
        hide_index=True,
        use_container_width=True,
    )
    if persistent_db:
        st.success(supabase_status["message"])
    else:
        st.info(supabase_status["message"])

    st.markdown("#### Instagram API")
    ig_status = get_instagram_status(check_api=False)
    st.dataframe(
        pd.DataFrame(
            [
                {"Punto": "Access token", "Estado": ig_status["token"]},
                {"Punto": "Business account ID", "Estado": ig_status["business_account_id"]},
                {"Punto": "API", "Estado": ig_status["api"]},
            ]
        ),
        hide_index=True,
        use_container_width=True,
    )
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Probar conexión Instagram"):
            checked = get_instagram_status(check_api=True)
            if checked["ready"]:
                account = checked.get("account", {})
                st.success(checked["message"])
                st.write(
                    {
                        "usuario": account.get("username", ""),
                        "followers": account.get("followers_count", 0),
                        "media": account.get("media_count", 0),
                    }
                )
            else:
                st.warning(checked["message"])
    with col_b:
        limit = st.number_input("Posts a leer", min_value=5, max_value=50, value=20, step=5)
        if st.button("Actualizar métricas de Instagram", type="primary"):
            with st.spinner("Leyendo Instagram y guardando en Supabase..."):
                try:
                    result = refresh_instagram_to_cache(limit=int(limit))
                except InstagramAPIError as exc:
                    st.error(f"No se pudo actualizar Instagram: {exc}")
                else:
                    st.success(result["message"])
                    if result["unsupported_metrics"]:
                        st.caption(
                            "Algunas métricas no están disponibles para ciertos formatos o permisos: "
                            + ", ".join(result["unsupported_metrics"][:8])
                        )

    st.markdown("#### LinkedIn API")
    linkedin_status = get_linkedin_status(check_api=False)
    st.dataframe(
        pd.DataFrame(
            [
                {"Punto": "Access token", "Estado": linkedin_status["token"]},
                {"Punto": "API version", "Estado": linkedin_status["version"]},
                {"Punto": "API", "Estado": linkedin_status["api"]},
            ]
        ),
        hide_index=True,
        use_container_width=True,
    )
    col_c, col_d = st.columns(2)
    with col_c:
        if st.button("Probar conexión LinkedIn"):
            checked = get_linkedin_status(check_api=True)
            if checked["ready"]:
                st.success(checked["message"])
                profile = checked.get("profile", {})
                if profile:
                    st.write(
                        {
                            "nombre": profile.get("name", ""),
                            "email": profile.get("email", ""),
                        }
                    )
            else:
                st.warning(checked["message"])
    with col_d:
        if st.button("Actualizar métricas de LinkedIn", type="primary"):
            with st.spinner("Leyendo LinkedIn y guardando en Supabase..."):
                try:
                    result = refresh_linkedin_to_cache()
                except LinkedInAPIError as exc:
                    st.error(f"No se pudo actualizar LinkedIn: {exc}")
                else:
                    st.success(result["message"])
                    st.write(result["analytics"])
                    if result["unsupported_metrics"]:
                        st.caption(
                            "LinkedIn no entregó estas métricas con el permiso actual: "
                            + ", ".join(result["unsupported_metrics"][:8])
                        )

    completed = 0
    completed += 1 if is_cloud else 0
    completed += 1 if has_ai_key() else 0
    completed += 1 if instagram_ready else 0
    completed += 1 if linkedin_ready else 0
    completed += 1 if persistent_db else 0
    completed += 1
    completed += 1
    readiness = int((completed / 7) * 100)
    st.metric("Nivel operativo", f"{readiness}%")

    st.markdown("#### Qué significa")
    if readiness >= 100:
        st.success("La base operativa está lista: IA, memoria, Instagram y lectura estratégica funcionando.")
    elif readiness >= 80:
        st.success("La app ya está lista para uso diario. Quedan integraciones opcionales para ampliar el sistema.")
    else:
        st.warning("La app funciona, pero todavía falta conectar datos automáticos o persistencia para llamarla 100% producción.")

    st.markdown("#### Orden para cerrar 100%")
    st.write(
        "1. Usar la app diariamente con carruseles, ideas e inspiración.\n\n"
        "2. Conectar Supabase para que el historial no dependa de archivos temporales de Streamlit.\n\n"
        "3. Conectar Instagram Graph API oficial para traer métricas reales.\n\n"
        "4. Conectar LinkedIn para medir autoridad, visitas e interés de consultoría.\n\n"
        "5. Automatizar refresh diario/semanal de métricas y trends."
    )


def render_publish_time(posts: pd.DataFrame) -> None:
    st.subheader("Cuándo publicar")
    heat = posts.groupby(["weekday", "hour"], as_index=False)[["engagement_rate", "share_rate", "save_rate"]].mean()
    heat["decision_score"] = (heat["engagement_rate"] + heat["share_rate"] * 1.8 + heat["save_rate"] * 1.6).round(2)
    fig = px.density_heatmap(
        heat,
        x="hour",
        y="weekday",
        z="decision_score",
        color_continuous_scale=["#fffaf0", BRAND_COLORS["yellow"], BRAND_COLORS["red"], BRAND_COLORS["ink"]],
    )
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(heat.sort_values("decision_score", ascending=False).head(8), hide_index=True, use_container_width=True)


def render_ideas(posts: pd.DataFrame, stored_ideas: pd.DataFrame) -> None:
    st.subheader("Ideas estratégicas")
    st.write("Genera ideas con criterio DOMO a partir de lo que está funcionando y lo que falta mejorar.")

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        count = st.slider("Cantidad", min_value=3, max_value=12, value=6)
    with col_b:
        focus = st.selectbox("Objetivo", ["shares", "saves", "comentarios de calidad", "visitas al perfil", "leads"])
    with col_c:
        platform = st.selectbox("Plataforma principal", ["Instagram", "LinkedIn", "Ambas"])

    if st.button("Generar ideas", type="primary"):
        new_ideas = generate_ideas(posts, focus=focus, platform=platform, count=count)
        st.session_state["generated_ideas"] = new_ideas

    ideas_to_show = st.session_state.get("generated_ideas", [])
    if ideas_to_show:
        for index, idea in enumerate(ideas_to_show):
            with st.container(border=True):
                st.markdown(f"### {idea['title']}")
                cols = st.columns([1, 1, 1])
                cols[0].markdown(f"**Pilar:** {idea['pillar']}")
                cols[1].markdown(f"**Formato:** {idea['format']}")
                cols[2].markdown(f"**Prioridad:** {idea['priority']}")
                st.markdown(f"**Hook 1.7s:** {idea['hook']}")
                st.markdown(f"**Mecanismo share/save:** {idea['share_save_mechanism']}")
                st.markdown(f"**CTA:** {idea['cta']}")
                st.markdown(f"**Razón estratégica:** {idea['strategic_reason']}")
                st.markdown(f"**Adaptación LinkedIn:** {idea['linkedin_adaptation']}")
                col_save, col_make = st.columns(2)
                with col_save:
                    if st.button("Guardar idea", key=f"save_idea_{index}_{idea['title']}"):
                        conn = get_connection()
                        add_content_idea(conn, idea)
                        conn.close()
                        st.success("Idea guardada en memoria.")
                with col_make:
                    if st.button("Convertir en carrusel", key=f"carousel_from_idea_{index}_{idea['title']}"):
                        st.session_state["page"] = "Carruseles"
                        st.session_state["carousel_seed"] = (
                            f"{idea['title']}\n{idea['hook']}\n{idea['share_save_mechanism']}\n{idea['strategic_reason']}"
                        )
                        st.rerun()
    else:
        st.dataframe(stored_ideas, hide_index=True, use_container_width=True)


def render_carousels(posts: pd.DataFrame, inspirations: pd.DataFrame, carousels: pd.DataFrame) -> None:
    st.subheader("Carruseles")
    st.write("Crea carruseles con frases DOMO, alimentados por tus ideas y los links que vas guardando.")

    source_options = ["Escribir una idea nueva"]
    if not inspirations.empty:
        source_options.extend(inspirations["title"].fillna("Link guardado").head(10).tolist())
    source = st.selectbox("Fuente", source_options)

    seed = ""
    selected_url = ""
    if source == "Escribir una idea nueva":
        default_seed = st.session_state.pop("carousel_seed", "")
        seed = st.text_area(
            "Idea o frase inicial",
            placeholder="Ej: Pinterest no entiende tu barrio / Cuenca no es postal, es sistema visual",
            value=default_seed,
        )
    else:
        selected = inspirations[inspirations["title"].fillna("Link guardado") == source].head(1)
        if not selected.empty:
            row = selected.iloc[0]
            selected_url = row.get("url", "")
            seed = f"{row.get('title', '')}\n{row.get('domo_angle', '')}\n{row.get('suggested_content', '')}"
            st.markdown("#### Fuente guardada")
            st.write(row.get("domo_angle", ""))

    objective = st.selectbox("Objetivo del carrusel", ["saves", "shares", "comentarios de calidad", "leads", "autoridad visual"])
    if st.button("Generar carrusel", type="primary"):
        carousel = generate_carousel(seed, objective, posts, inspirations)
        conn = get_connection()
        add_carousel_draft(
            conn,
            selected_url or source,
            carousel.get("title", "Carrusel DOMO"),
            carousel.get("objective", objective),
            slides_to_json(carousel),
            carousel.get("caption", ""),
            carousel.get("cta", ""),
        )
        conn.close()
        st.session_state["last_carousel"] = carousel
        st.success("Carrusel generado y guardado.")

    carousel = st.session_state.get("last_carousel")
    if carousel:
        st.markdown(f"### {carousel.get('title', 'Carrusel DOMO')}")
        st.markdown(f"**Objetivo:** {carousel.get('objective', objective)}")
        for slide in carousel.get("slides", []):
            render_slide_card(slide, key_prefix=f"last_{carousel.get('title', 'carousel')}")
        script = carousel_to_script(carousel)
        st.markdown("#### Guion completo")
        st.text_area("Listo para copiar", script, height=280)
        st.download_button(
            "Descargar guion TXT",
            data=script.encode("utf-8"),
            file_name="domo_carrusel_guion.txt",
            mime="text/plain",
        )
        st.markdown("#### Caption")
        st.write(carousel.get("caption", ""))
        st.markdown("#### CTA")
        st.write(carousel.get("cta", ""))

    st.markdown("#### Carruseles guardados")
    if carousels.empty:
        st.info("Todavía no hay carruseles guardados.")
    else:
        for _, row in carousels.head(8).iterrows():
            with st.expander(row["title"]):
                st.markdown(f"**Objetivo:** {row['objective']}")
                try:
                    slides = json.loads(row["slides_json"])
                except json.JSONDecodeError:
                    slides = []
                for slide in slides:
                    render_slide_card(slide, key_prefix=f"saved_{row['id']}")
                script = carousel_to_script(
                    {
                        "title": row["title"],
                        "objective": row["objective"],
                        "slides": slides,
                        "caption": row.get("caption", ""),
                        "cta": row.get("cta", ""),
                    }
                )
                st.text_area("Guion", script, height=220, key=f"script_{row['id']}")
                st.markdown(f"**Caption:** {row.get('caption', '')}")
                st.markdown(f"**CTA:** {row.get('cta', '')}")


def render_monetization(monetization: pd.DataFrame, posts: pd.DataFrame) -> None:
    st.subheader("Monetización")
    cols = st.columns(4)
    cols[0].metric("Leads workshop", int(monetization["workshop_leads"].sum()))
    cols[1].metric("Consultoría", int(monetization["consulting_leads"].sum()))
    cols[2].metric("Colaboraciones", int(monetization["collab_leads"].sum()))
    cols[3].metric("Valor estimado", f"${int(monetization['estimated_value_usd'].sum()):,}")

    fig = px.bar(
        monetization,
        x="source",
        y=["workshop_leads", "consulting_leads", "collab_leads"],
        barmode="group",
        color_discrete_sequence=[BRAND_COLORS["yellow"], BRAND_COLORS["red"], BRAND_COLORS["blue"]],
    )
    st.plotly_chart(fig, use_container_width=True)

    top_posts = posts.sort_values("profile_visit_rate", ascending=False).head(5)
    st.markdown("#### Posts que mejor empujan intención")
    st.dataframe(top_posts[["title", "platform", "pillar", "format", "profile_visit_rate", "quality_comment_rate"]], hide_index=True, use_container_width=True)


def main() -> None:
    inject_styles()
    if not require_login():
        return
    render_mobile_hint()
    render_header()
    (
        posts,
        daily,
        profile,
        monetization,
        stored_ideas,
        screenshots,
        inspirations,
        assistant_notes,
        trends,
        collabs,
        action_items,
        carousels,
    ) = load_data()

    nav_options = [
        "Inicio",
        "Lectura",
        "Asistente",
        "Ideas",
        "Carruseles",
        "Capturas",
        "Trends",
        "Inspiración",
        "Collabs",
        "Dashboard",
        "Data Center",
        "Admin",
    ]
    if "page" not in st.session_state:
        st.session_state["page"] = "Inicio"
    page = st.sidebar.radio(
        "Navegación",
        nav_options,
        index=nav_options.index(st.session_state["page"]) if st.session_state["page"] in nav_options else 0,
    )
    st.session_state["page"] = page

    if page == "Inicio":
        render_command_center(posts, action_items)
    elif page == "Lectura":
        render_growth_reading(posts, profile)
    elif page == "Asistente":
        render_assistant(posts, assistant_notes)
    elif page == "Ideas":
        render_ideas(posts, stored_ideas)
    elif page == "Carruseles":
        render_carousels(posts, inspirations, carousels)
    elif page == "Capturas":
        render_capture_lab(posts, screenshots)
    elif page == "Trends":
        render_trend_lab(posts, trends)
    elif page == "Inspiración":
        render_inspiration_lab(posts, inspirations)
    elif page == "Collabs":
        render_collab_lab(posts, collabs)
    elif page == "Data Center":
        render_data_center(posts, daily, profile, screenshots, inspirations, trends, collabs)
    elif page == "Admin":
        render_admin()
    else:
        tabs = st.tabs([
            "Resumen",
            "Lectura",
            "Tendencias",
            "Audiencia",
            "Posts",
            "Cuándo publicar",
            "Monetización",
        ])

        with tabs[0]:
            render_summary(posts, profile)
        with tabs[1]:
            render_growth_reading(posts, profile)
        with tabs[2]:
            render_trends(posts, daily)
        with tabs[3]:
            render_audience(profile)
        with tabs[4]:
            render_posts(posts)
        with tabs[5]:
            render_publish_time(posts)
        with tabs[6]:
            render_monetization(monetization, posts)

    st.caption(f"Última lectura local: {datetime.now().strftime('%Y-%m-%d %H:%M')}. Solo lectura. No publica, no envía mensajes.")


if __name__ == "__main__":
    main()
