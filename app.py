from __future__ import annotations

import html
import json
import os
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components

import cache as cache_store
from assistant import analyze_link_for_domo, answer_as_domo_assistant, has_ai_key
from carousel import generate_carousel, slides_to_json
from ideas import LOCAL_IDEA_BANK


st.set_page_config(
    page_title="DOMO Content Lab",
    page_icon="◉",
    layout="wide",
    initial_sidebar_state="collapsed",
)


DATA_DIR = Path("data.nosync")


def get_secret(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return str(value or os.getenv(name, default) or "")


def clean_text(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def as_percent(value: float | int | None) -> str:
    try:
        return f"{float(value):.1f}%"
    except Exception:
        return "0.0%"


def safe_mean(frame: pd.DataFrame, column: str) -> float:
    if frame.empty or column not in frame.columns:
        return 0.0
    return float(pd.to_numeric(frame[column], errors="coerce").fillna(0).mean())


def init_app() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    cache_store.initialize_database()
    st.session_state.setdefault("page", "home")
    st.session_state.setdefault("draft_cards", [])


def load_data() -> dict[str, pd.DataFrame]:
    conn = cache_store.get_connection()
    data = {
        "posts": cache_store.get_posts(conn),
        "ideas": cache_store.get_content_ideas(conn),
        "carousels": cache_store.get_carousel_drafts(conn),
        "inspirations": cache_store.get_inspirations(conn),
        "trends": cache_store.get_trend_items(conn),
        "collabs": cache_store.get_collab_targets(conn),
        "daily": cache_store.get_daily_metrics(conn),
        "profile": cache_store.get_profile_metrics(conn),
    }
    conn.close()
    return data


def require_login() -> bool:
    password = get_secret("APP_PASSWORD", "")
    if not password:
        st.session_state["authenticated"] = True
        return True
    if st.query_params.get("domo_auth") == "ok":
        st.session_state["authenticated"] = True
    if st.session_state.get("authenticated"):
        st.query_params["domo_auth"] = "ok"
        return True

    inject_styles()
    st.markdown('<main class="domo-login">', unsafe_allow_html=True)
    st.markdown("<h1>DOMO Content Lab</h1>", unsafe_allow_html=True)
    st.write("Tu sistema privado para decidir, crear y aprender de tus redes.")
    entered = st.text_input("Clave privada", type="password", label_visibility="collapsed")
    if st.button("Entrar", type="primary"):
        if entered == password:
            st.session_state["authenticated"] = True
            st.query_params["domo_auth"] = "ok"
            st.rerun()
        st.error("Clave incorrecta.")
    st.markdown("</main>", unsafe_allow_html=True)
    return False


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bg: #050706;
            --panel: #0d120f;
            --panel2: #171d18;
            --text: #f4f7ec;
            --muted: rgba(244,247,236,.66);
            --lime: #c8ff2f;
            --cyan: #67e8f9;
            --pink: #ff67d8;
            --orange: #ffb84d;
            --red: #ff5a5a;
            --line: rgba(244,247,236,.12);
        }
        .stApp {
            background:
                radial-gradient(circle at 18% 10%, rgba(200,255,47,.13), transparent 32%),
                radial-gradient(circle at 92% 20%, rgba(103,232,249,.09), transparent 30%),
                var(--bg);
            color: var(--text);
        }
        [data-testid="stSidebar"] {
            background: rgba(5,7,6,.94);
            border-right: 1px solid var(--line);
        }
        [data-testid="stSidebar"] * { color: var(--text) !important; }
        .block-container {
            max-width: 1320px;
            padding-top: 2.2rem;
            padding-bottom: 6rem;
        }
        h1, h2, h3, p, label, span, div { color: var(--text); }
        h1 {
            font-size: clamp(3rem, 9vw, 7.5rem) !important;
            line-height: .82 !important;
            letter-spacing: -0.04em;
            font-weight: 950 !important;
            margin-bottom: .5rem !important;
        }
        h2 { font-size: clamp(1.8rem, 4vw, 3.3rem) !important; font-weight: 950 !important; }
        h3 { font-weight: 900 !important; }
        .domo-top {
            display: flex;
            justify-content: space-between;
            gap: 18px;
            align-items: flex-start;
            margin-bottom: 24px;
        }
        .domo-kicker {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 8px 12px;
            border: 1px solid rgba(200,255,47,.28);
            border-radius: 999px;
            color: var(--lime) !important;
            font-size: .78rem;
            font-weight: 950;
            text-transform: uppercase;
            background: rgba(200,255,47,.08);
        }
        .domo-status {
            min-width: 180px;
            padding: 18px;
            border-radius: 28px;
            background: rgba(244,247,236,.08);
            border: 1px solid var(--line);
            text-align: right;
        }
        .domo-status strong { display: block; font-size: 2.2rem; color: var(--lime) !important; }
        .domo-path {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 10px;
            margin: -8px 0 22px;
        }
        .domo-path-card {
            display: block;
            min-height: 92px;
            padding: 15px;
            border-radius: 24px;
            background: rgba(244,247,236,.065);
            border: 1px solid rgba(244,247,236,.11);
            text-decoration: none !important;
            transition: transform .16s ease, border-color .16s ease, background .16s ease;
        }
        .domo-path-card:hover {
            transform: translateY(-2px);
            border-color: rgba(200,255,47,.42);
            background: rgba(200,255,47,.10);
        }
        .domo-path-card.active {
            background: var(--lime);
            border-color: var(--lime);
        }
        .domo-path-card.active * { color: #07100d !important; }
        .domo-path-card b {
            display: block;
            font-size: 1rem;
            color: var(--text) !important;
            margin-bottom: 4px;
        }
        .domo-path-card span {
            display: block;
            color: var(--muted) !important;
            font-size: .82rem;
            line-height: 1.25;
        }
        .domo-step-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 12px;
            margin: 14px 0 22px;
        }
        .domo-step-card {
            min-height: 128px;
            padding: 16px;
            border-radius: 26px;
            background: rgba(244,247,236,.07);
            border: 1px solid rgba(244,247,236,.11);
        }
        .domo-step-card strong {
            display: block;
            font-size: 1.15rem;
            margin: 8px 0;
            color: var(--text) !important;
        }
        .domo-step-card p {
            color: var(--muted) !important;
            margin: 0;
            line-height: 1.35;
        }
        .domo-shell {
            display: grid;
            grid-template-columns: minmax(0, 1.65fr) minmax(280px, .85fr);
            gap: 18px;
            align-items: start;
        }
        .domo-panel, .domo-card, .domo-mini, .domo-chat, .domo-metric {
            background: linear-gradient(150deg, rgba(244,247,236,.08), rgba(244,247,236,.035));
            border: 1px solid var(--line);
            border-radius: 30px;
        }
        .domo-panel { padding: 22px; }
        .domo-chat {
            padding: 22px;
            border-color: rgba(200,255,47,.23);
            background: linear-gradient(145deg, rgba(200,255,47,.12), rgba(13,18,15,.92));
        }
        .domo-chat h2 { margin-top: 6px !important; }
        .domo-sub { color: var(--muted) !important; font-size: 1rem; line-height: 1.45; }
        .domo-chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin: 14px 0 12px;
        }
        .domo-chip {
            display: inline-flex;
            padding: 10px 14px;
            border-radius: 999px;
            background: rgba(244,247,236,.10);
            border: 1px solid rgba(244,247,236,.10);
            font-weight: 850;
            color: var(--text) !important;
        }
        div[data-testid="stButton"] > button {
            min-height: 44px;
            border-radius: 999px;
            border: 1px solid rgba(244,247,236,.16);
            background: rgba(244,247,236,.08);
            color: var(--text);
            font-weight: 850;
        }
        div[data-testid="stButton"] > button[kind="primary"],
        .stButton button[kind="primary"] {
            background: var(--lime) !important;
            color: #07100d !important;
            border-color: var(--lime) !important;
        }
        textarea, input, .stTextInput input, .stTextArea textarea {
            border-radius: 22px !important;
            background: rgba(244,247,236,.08) !important;
            color: var(--text) !important;
            border: 1px solid rgba(244,247,236,.16) !important;
        }
        .domo-card {
            padding: 18px;
            margin: 12px 0;
            position: relative;
            overflow: hidden;
        }
        .domo-card:before {
            content: "";
            position: absolute;
            width: 90px;
            height: 90px;
            border-radius: 999px;
            top: -42px;
            right: -30px;
            background: var(--signal, var(--lime));
            opacity: .22;
        }
        .domo-card-title {
            font-size: clamp(1.35rem, 2.5vw, 2.3rem);
            line-height: .98;
            font-weight: 950;
            max-width: 88%;
        }
        .domo-card-meta {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            margin: 12px 0;
        }
        .domo-pill {
            padding: 7px 10px;
            border-radius: 999px;
            background: rgba(244,247,236,.10);
            color: rgba(244,247,236,.78) !important;
            font-size: .76rem;
            font-weight: 900;
            text-transform: uppercase;
        }
        .domo-hook {
            padding: 14px;
            border-radius: 22px;
            background: rgba(5,7,6,.45);
            color: var(--text) !important;
            font-size: 1.02rem;
            line-height: 1.35;
        }
        .domo-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 14px;
        }
        .domo-metric {
            padding: 18px;
            min-height: 160px;
        }
        .domo-metric b {
            display: block;
            font-size: clamp(2.8rem, 7vw, 5.4rem);
            line-height: .85;
            color: var(--metric, var(--lime)) !important;
            font-weight: 950;
        }
        .domo-metric span { color: var(--muted) !important; font-weight: 850; text-transform: uppercase; }
        .domo-note {
            padding: 16px;
            border-radius: 24px;
            background: rgba(200,255,47,.12);
            border: 1px solid rgba(200,255,47,.22);
            color: var(--text) !important;
        }
        .domo-carousel-head {
            display: grid;
            grid-template-columns: minmax(0, 1fr) minmax(220px, .55fr);
            gap: 14px;
            margin: 22px 0 12px;
        }
        .domo-caption-box {
            padding: 18px;
            border-radius: 28px;
            background: rgba(244,247,236,.075);
            border: 1px solid var(--line);
        }
        .domo-slide-card {
            display: grid;
            grid-template-columns: minmax(190px, 270px) minmax(0, 1fr);
            gap: 14px;
            padding: 14px;
            margin: 12px 0;
            border-radius: 26px;
            background: linear-gradient(145deg, rgba(244,247,236,.085), rgba(244,247,236,.035));
            border: 1px solid rgba(244,247,236,.13);
        }
        .domo-post-preview {
            width: 100%;
            max-width: 270px;
            min-height: 300px;
            aspect-ratio: 4 / 5;
            border-radius: 24px;
            padding: 16px;
            position: relative;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            border: 1px solid rgba(244,247,236,.18);
            background:
                radial-gradient(circle at 18% 14%, rgba(200,255,47,.55), transparent 19%),
                linear-gradient(145deg, #101410, #050706 58%, #20251f);
        }
        .domo-post-preview:before {
            content: "";
            position: absolute;
            inset: 0;
            opacity: .18;
            background-image:
                repeating-linear-gradient(135deg, rgba(244,247,236,.22) 0 1px, transparent 1px 12px);
            pointer-events: none;
        }
        .domo-post-preview.street {
            background:
                radial-gradient(circle at 78% 18%, rgba(255,103,216,.35), transparent 24%),
                linear-gradient(145deg, #0b0e0d, #26301f 52%, #090a09);
        }
        .domo-post-preview.paper {
            background:
                radial-gradient(circle at 12% 18%, rgba(255,184,77,.42), transparent 26%),
                linear-gradient(145deg, #efead5, #b6c0a2 52%, #101410);
        }
        .domo-post-preview.photo {
            background:
                radial-gradient(circle at 70% 20%, rgba(103,232,249,.34), transparent 26%),
                linear-gradient(145deg, #050706, #18242b 52%, #101410);
        }
        .domo-post-preview.mockup {
            background:
                radial-gradient(circle at 74% 18%, rgba(255,90,90,.38), transparent 24%),
                linear-gradient(145deg, #111111, #2a2118 54%, #050706);
        }
        .domo-post-top {
            position: relative;
            z-index: 1;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
        }
        .domo-slide-number {
            width: 46px;
            height: 46px;
            border-radius: 16px;
            display: grid;
            place-items: center;
            background: var(--lime);
            color: #07100d !important;
            font-weight: 950;
            font-size: 1rem;
        }
        .domo-post-brand {
            color: var(--text) !important;
            font-weight: 950;
            font-size: .8rem;
            letter-spacing: .04em;
        }
        .domo-post-copy {
            position: relative;
            z-index: 1;
        }
        .domo-slide-label {
            display: inline-flex;
            padding: 5px 9px;
            border-radius: 999px;
            background: rgba(200,255,47,.12);
            color: var(--lime) !important;
            font-size: .72rem;
            font-weight: 950;
            text-transform: uppercase;
            margin-bottom: 7px;
        }
        .domo-slide-big {
            font-size: clamp(1.25rem, 2.2vw, 2.2rem);
            line-height: .98;
            font-weight: 950;
            color: var(--text) !important;
            margin: 0 0 12px;
        }
        .domo-post-preview.paper .domo-slide-big,
        .domo-post-preview.paper .domo-slide-small,
        .domo-post-preview.paper .domo-post-brand {
            color: #07100d !important;
        }
        .domo-post-preview.paper .domo-slide-label {
            color: #07100d !important;
            background: rgba(7,16,13,.13);
        }
        .domo-slide-small {
            font-size: .9rem;
            line-height: 1.35;
            color: rgba(244,247,236,.78) !important;
            margin: 0;
        }
        .domo-slide-detail {
            padding: 4px 0;
            align-self: center;
            width: 100%;
        }
        .domo-visual-pills {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin: 10px 0 12px;
        }
        .domo-visual-pill {
            padding: 8px 10px;
            border-radius: 999px;
            background: rgba(244,247,236,.10);
            border: 1px solid rgba(244,247,236,.12);
            color: rgba(244,247,236,.82) !important;
            font-size: .78rem;
            font-weight: 850;
        }
        .domo-slide-visual {
            margin-top: 12px;
            padding: 12px;
            border-radius: 18px;
            background: rgba(5,7,6,.42);
            color: rgba(244,247,236,.72) !important;
        }
        .domo-bottom-nav {
            position: fixed;
            left: 50%;
            bottom: 18px;
            transform: translateX(-50%);
            z-index: 999;
            display: flex;
            gap: 8px;
            padding: 8px;
            border-radius: 999px;
            background: rgba(5,7,6,.82);
            border: 1px solid rgba(244,247,236,.16);
            backdrop-filter: blur(20px);
        }
        .domo-bottom-nav a {
            padding: 11px 16px;
            border-radius: 999px;
            color: var(--muted) !important;
            text-decoration: none !important;
            font-weight: 900;
            font-size: .84rem;
        }
        .domo-bottom-nav a.active {
            background: var(--lime);
            color: #07100d !important;
        }
        .domo-login {
            max-width: 720px;
            margin: 16vh auto 0;
        }
        .domo-muted { color: var(--muted) !important; }
        .domo-danger { --signal: var(--red); }
        .domo-cyan { --signal: var(--cyan); }
        .domo-pink { --signal: var(--pink); }
        .domo-orange { --signal: var(--orange); }
        div[data-testid="stTabs"] [data-baseweb="tab-list"] {
            gap: 10px;
            padding: 8px;
            margin: 8px 0 18px;
            border-radius: 999px;
            background: rgba(244,247,236,.07);
            border: 1px solid rgba(244,247,236,.12);
        }
        div[data-testid="stTabs"] button[role="tab"] {
            min-height: 52px;
            padding: 0 22px;
            border-radius: 999px;
            color: rgba(244,247,236,.78) !important;
            font-weight: 950;
            letter-spacing: .01em;
        }
        div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
            background: var(--lime) !important;
            color: #07100d !important;
        }
        div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] * {
            color: #07100d !important;
        }
        @media (max-width: 860px) {
            .block-container { padding: 1rem .85rem 6rem; }
            .domo-top { display: block; }
            .domo-status { text-align: left; margin-top: 12px; }
            .domo-shell { grid-template-columns: 1fr; }
            .domo-grid { grid-template-columns: 1fr; }
            .domo-path { grid-template-columns: 1fr; margin-top: 0; }
            .domo-path-card { min-height: auto; padding: 13px 14px; }
            .domo-step-grid { grid-template-columns: 1fr; }
            .domo-step-card { min-height: auto; }
            .domo-carousel-head { grid-template-columns: 1fr; }
            .domo-slide-card { grid-template-columns: 1fr; }
            .domo-post-preview { max-width: 100%; min-height: 300px; }
            .domo-card-title { max-width: 100%; }
            [data-testid="stSidebar"] { display: none; }
            .domo-bottom-nav { width: calc(100% - 22px); justify-content: space-between; }
            .domo-bottom-nav a { flex: 1; text-align: center; padding: 12px 8px; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def nav_url(page: str) -> str:
    auth = "&domo_auth=ok" if st.session_state.get("authenticated") else ""
    return f"?page={page}{auth}"


def bottom_nav(current: str) -> None:
    items = [("home", "Hoy"), ("create", "Crear"), ("learn", "Métricas")]
    links = []
    for key, label in items:
        active = "active" if key == current else ""
        links.append(f'<a class="{active}" href="{nav_url(key)}" target="_self">{label}</a>')
    st.markdown(f'<nav class="domo-bottom-nav">{"".join(links)}</nav>', unsafe_allow_html=True)


def sidebar_status(data: dict[str, pd.DataFrame]) -> None:
    st.sidebar.markdown("### DOMO Content Lab")
    st.sidebar.caption("Flujo simple: Hoy → Crear → Métricas.")
    st.sidebar.write("IA:", "activa" if has_ai_key() else "modo local")
    st.sidebar.write("Memoria:", cache_store.get_database_mode())
    st.sidebar.divider()
    st.sidebar.caption("En celular usa la barra inferior. En desktop usa las tarjetas superiores.")


def header(title: str, subtitle: str, data: dict[str, pd.DataFrame]) -> None:
    posts = data["posts"]
    st.markdown(
        f"""
        <section class="domo-top">
            <div>
                <span class="domo-kicker">DOMO Content Lab</span>
                <h1>{html.escape(title)}</h1>
                <p class="domo-sub">{html.escape(subtitle)}</p>
            </div>
            <div class="domo-status">
                <span class="domo-muted">señales leídas</span>
                <strong>{len(posts)}</strong>
                <span class="domo-muted">solo lectura</span>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def path_nav(current: str) -> None:
    items = [
        ("home", "01 Hoy", "Pregunta qué publicar y guarda ideas."),
        ("create", "02 Crear", "Convierte ideas en carruseles y links útiles."),
        ("learn", "03 Métricas", "Mira qué pegó, qué repetir y qué corregir."),
    ]
    cards = []
    for key, title, subtitle in items:
        active = "active" if key == current else ""
        cards.append(
            f'<a class="domo-path-card {active}" href="{nav_url(key)}" target="_self">'
            f'<b>{html.escape(title)}</b><span>{html.escape(subtitle)}</span></a>'
        )
    st.markdown(f'<nav class="domo-path">{"".join(cards)}</nav>', unsafe_allow_html=True)


def action_guide(items: list[tuple[str, str, str]]) -> None:
    cards = []
    for label, title, copy in items:
        cards.append(
            f'<article class="domo-step-card"><span class="domo-kicker">{html.escape(label)}</span>'
            f'<strong>{html.escape(title)}</strong><p>{html.escape(copy)}</p></article>'
        )
    st.markdown(f'<section class="domo-step-grid">{"".join(cards)}</section>', unsafe_allow_html=True)


def metric_reading(posts: pd.DataFrame) -> dict[str, str]:
    share = safe_mean(posts, "share_rate")
    save = safe_mean(posts, "save_rate")
    comments = safe_mean(posts, "quality_comment_rate")
    profile = safe_mean(posts, "profile_visit_rate")
    best_format = "Reel"
    best_title = "Todavía no hay ganador claro"
    if not posts.empty:
        scored = posts.copy()
        for col in ["share_rate", "save_rate", "quality_comment_rate", "profile_visit_rate"]:
            scored[col] = pd.to_numeric(scored.get(col, 0), errors="coerce").fillna(0)
        scored["score"] = scored["share_rate"] * 2 + scored["save_rate"] * 2 + scored["quality_comment_rate"] + scored["profile_visit_rate"]
        best = scored.sort_values("score", ascending=False).iloc[0]
        best_title = clean_text(best.get("title"), best_title)
        best_format = clean_text(best.get("format"), best_format)
    weak = min(
        [("shares", share), ("saves", save), ("comentarios", comments), ("visitas al perfil", profile)],
        key=lambda item: item[1],
    )[0]
    next_move = {
        "shares": "Publica una lectura de calle con frase compartible y orgullo local.",
        "saves": "Convierte una idea útil en carrusel con checklist visual.",
        "comentarios": "Haz una pregunta con postura: no 'qué opinas', sino una tensión real.",
        "visitas al perfil": "Cierra con oferta clara: workshop, revisión de marca o colaboración.",
    }[weak]
    return {
        "best_title": best_title,
        "best_format": best_format,
        "weak": weak,
        "next_move": next_move,
        "share": as_percent(share),
        "save": as_percent(save),
        "comments": as_percent(comments),
        "profile": as_percent(profile),
    }


def local_cards(question: str, posts: pd.DataFrame) -> list[dict]:
    q = question.lower()
    bank = LOCAL_IDEA_BANK
    keywords = {
        "foto": ["foto", "fotografia", "publicitaria", "shot", "encuadre"],
        "branding": ["branding", "marca", "mockup", "logo", "identidad"],
        "lettering": ["lettering", "rotulo", "tipografia", "letra", "stencil"],
        "cuenca": ["cuenca", "ecuador", "calle", "barrio", "latam"],
        "linkedin": ["linkedin", "consultoria", "workshop"],
        "reel": ["reel", "video"],
        "carrusel": ["carrusel", "save", "guardar"],
    }
    selected = []
    for idea in bank:
        text = " ".join(str(idea.get(k, "")) for k in ["title", "format", "hook", "strategic_reason"]).lower()
        if any(word in q for words in keywords.values() for word in words):
            if any(word in text for words in keywords.values() for word in words if word in q):
                selected.append(dict(idea))
    if not selected:
        selected = [dict(item) for item in bank[:4]]
    reading = metric_reading(posts)
    if "hoy" in q or "publico" in q or "postear" in q:
        selected.insert(
            0,
            {
                "title": "Hoy: una lectura visual de Cuenca con salida comercial",
                "pillar": "DOMO ve el mundo",
                "format": "Reel corto + carrusel derivado",
                "hook": "Esta esquina tiene más identidad que muchas marcas que pagaron branding.",
                "share_save_mechanism": "Share por identidad local; save por lectura en 3 capas: color, jerarquía y memoria.",
                "cta": "Comenta 'calle' y analizo una gráfica de tu barrio.",
                "strategic_reason": reading["next_move"],
                "priority": "Alta",
                "linkedin_adaptation": "Mini ensayo: qué pueden aprender las marcas de la gráfica popular ecuatoriana.",
            },
        )
    return selected[:4]


def parse_ai_cards(answer: str, question: str, posts: pd.DataFrame) -> list[dict]:
    start = answer.find("{")
    end = answer.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            payload = json.loads(answer[start:end])
            if isinstance(payload.get("ideas"), list):
                return [item for item in payload["ideas"] if isinstance(item, dict)]
            if isinstance(payload.get("idea"), dict):
                return [payload["idea"]]
        except Exception:
            pass
    return [
        {
            "title": "Lectura DOMO",
            "pillar": "Así pienso yo",
            "format": "Nota estratégica",
            "hook": answer[:500],
            "share_save_mechanism": "Convertir esta lectura en una pieza visual concreta.",
            "cta": "Guardar y transformarla en carrusel o Reel.",
            "strategic_reason": question,
            "priority": "Media",
            "linkedin_adaptation": "Expandir como post de criterio creativo.",
        }
    ]


def create_cards(question: str, posts: pd.DataFrame) -> list[dict]:
    guardrail = (
        "IMPORTANTE: DOMO vive en Cuenca, Ecuador. Prioriza Ecuador, Cuenca, LATAM, cultura visual local, "
        "fotografia publicitaria, branding, lettering, stencil, mockups, restaurantes, hoteles, marcas creativas, workshops. "
        "No uses noticias de Espana, museos lejanos o tendencias globales si no tienen traduccion directa a DOMO. "
        "Devuelve JSON con 'ideas'. Cada idea debe tener title, pillar, format, hook, share_save_mechanism, cta, "
        "strategic_reason, priority, linkedin_adaptation. Nada de '5 tips' genericos.\n\n"
        f"Pedido: {question}"
    )
    try:
        answer = answer_as_domo_assistant(guardrail, posts)
        cards = parse_ai_cards(answer, question, posts)
        if cards:
            return cards[:4]
    except Exception:
        pass
    return local_cards(question, posts)


def save_idea(card: dict) -> None:
    conn = cache_store.get_connection()
    cache_store.add_content_idea(conn, card)
    conn.close()


def update_idea(item_id: int, values: dict) -> None:
    conn = cache_store.get_connection()
    cache_store.update_row(conn, "content_ideas", item_id, values)
    conn.close()


def delete_idea(item_id: int) -> None:
    conn = cache_store.get_connection()
    cache_store.delete_row(conn, "content_ideas", item_id)
    conn.close()


def update_carousel(item_id: int, values: dict) -> None:
    conn = cache_store.get_connection()
    cache_store.update_row(conn, "carousel_drafts", item_id, values)
    conn.close()


def delete_carousel(item_id: int) -> None:
    conn = cache_store.get_connection()
    cache_store.delete_row(conn, "carousel_drafts", item_id)
    conn.close()


def save_carousel_slides(item_id: int, slides: list[dict]) -> None:
    update_carousel(item_id, {"slides_json": json.dumps(renumber_slides(slides), ensure_ascii=False, indent=2)})


def renumber_slides(slides: list[dict]) -> list[dict]:
    renumbered = []
    for index, slide in enumerate(slides, start=1):
        item = dict(slide)
        item["number"] = index
        renumbered.append(item)
    return renumbered


def copy_button(label: str, text: str, key: str) -> None:
    safe_key = re.sub(r"[^a-zA-Z0-9_-]+", "-", key)
    payload = json.dumps(text or "", ensure_ascii=False)
    safe_label = html.escape(label)
    components.html(
        f"""
        <button id="copy-{safe_key}" class="domo-copy-button">{safe_label}</button>
        <script>
        const btn = document.getElementById("copy-{safe_key}");
        btn.addEventListener("click", async () => {{
            try {{
                await navigator.clipboard.writeText({payload});
                const old = btn.textContent;
                btn.textContent = "Copiado";
                btn.classList.add("done");
                setTimeout(() => {{
                    btn.textContent = old;
                    btn.classList.remove("done");
                }}, 1200);
            }} catch (err) {{
                btn.textContent = "No se pudo copiar";
            }}
        }});
        </script>
        <style>
        body {{ margin: 0; background: transparent; }}
        .domo-copy-button {{
            width: 100%;
            min-height: 46px;
            border: 1px solid rgba(244,247,236,.16);
            border-radius: 999px;
            background: rgba(244,247,236,.08);
            color: #f4f7ec;
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            font-weight: 900;
            cursor: pointer;
        }}
        .domo-copy-button:hover {{ background: rgba(200,255,47,.15); border-color: rgba(200,255,47,.38); }}
        .domo-copy-button.done {{ background: #c8ff2f; color: #07100d; border-color: #c8ff2f; }}
        </style>
        """,
        height=52,
    )


def infer_slide_microcopy(text: str, visual: str, number: int) -> str:
    source = f"{text} {visual}".lower()
    if "pinterest" in source:
        return "La referencia sirve solo si vuelve con acento propio."
    if "mockup" in source:
        return "Muéstralo viviendo en contexto, no flotando en una maqueta perfecta."
    if "foto" in source or "fotograf" in source:
        return "La imagen debe vender criterio, no solo verse bonita."
    if "calle" in source or "barrio" in source or "cuenca" in source:
        return "La calle también es archivo, sistema y estrategia visual."
    if number == 1:
        return "Una postura clara para abrir conversación y guardar."
    if number >= 6:
        return "Cierra con una pregunta que invite a responder con criterio."
    return "Convierte la idea en una señal visual fácil de recordar."


def normalize_carousel_slides(slides: list[dict]) -> tuple[list[dict], bool]:
    normalized: list[dict] = []
    changed = False
    for index, raw in enumerate(slides, start=1):
        if not isinstance(raw, dict):
            changed = True
            continue
        number = int(raw.get("number") or index)
        text = clean_text(raw.get("text"), clean_text(raw.get("title"), f"Slide {number}"))
        visual = clean_text(raw.get("visual"), clean_text(raw.get("note"), "Dirección visual pendiente."))
        microcopy = clean_text(
            raw.get("microcopy"),
            clean_text(raw.get("small_text"), clean_text(raw.get("subtitle"), clean_text(raw.get("support_text"), ""))),
        )
        if not microcopy:
            microcopy = infer_slide_microcopy(text, visual, number)
            changed = True
        item = dict(raw)
        item.update({"number": number, "text": text, "microcopy": microcopy, "visual": visual})
        normalized.append(item)
        if item != raw:
            changed = True
    return normalized, changed


def maybe_backfill_carousel(row: pd.Series, slides: list[dict]) -> None:
    try:
        item_id = int(row.get("id"))
    except Exception:
        return
    conn = cache_store.get_connection()
    cache_store.update_row(
        conn,
        "carousel_drafts",
        item_id,
        {"slides_json": json.dumps(slides, ensure_ascii=False, indent=2)},
    )
    conn.close()


def visual_background_class(visual: str, text: str) -> str:
    source = f"{visual} {text}".lower()
    if any(word in source for word in ["mockup", "marca", "branding", "logo"]):
        return "mockup"
    if any(word in source for word in ["foto", "fotograf", "retrato", "shot", "luz"]):
        return "photo"
    if any(word in source for word in ["papel", "grano", "risograph", "editorial", "textura"]):
        return "paper"
    if any(word in source for word in ["calle", "barrio", "rotulo", "cuenca", "latam", "popular"]):
        return "street"
    return ""


def visual_pills(visual: str) -> list[str]:
    visual_clean = clean_text(visual, "Fondo visual por definir")
    parts = re.split(r"[,.;/]+|\s+y\s+", visual_clean)
    pills = [part.strip().capitalize() for part in parts if len(part.strip()) > 2]
    return pills[:5] or [visual_clean]


def visual_brief(visual: str, text: str) -> list[tuple[str, str]]:
    source = f"{visual} {text}".lower()
    if any(word in source for word in ["mockup", "branding", "marca", "logo"]):
        return [
            ("Fondo", "mockup real sobre muro, vitrina o mesa de trabajo"),
            ("Mood", "editorial callejero, premium pero con textura"),
            ("Detalle", "sello DOMO, sticker lime y sombra dura"),
            ("Paleta", "negro, lima, rojo quemado y papel crudo"),
        ]
    if any(word in source for word in ["foto", "fotograf", "retrato", "shot", "luz"]):
        return [
            ("Fondo", "foto publicitaria con luz lateral y grano fino"),
            ("Mood", "alto contraste, encuadre cerrado, gesto humano"),
            ("Detalle", "recorte editorial, label pequeño y borde imperfecto"),
            ("Paleta", "grafito, lima, cyan frío y piel natural"),
        ]
    if any(word in source for word in ["calle", "barrio", "cuenca", "latam", "popular", "rotulo"]):
        return [
            ("Fondo", "pared de Cuenca, rótulo popular o textura de pintura"),
            ("Mood", "archivo visual LATAM, directo y con orgullo local"),
            ("Detalle", "flecha pintada, sticker, sello rojo o marca de registro"),
            ("Paleta", "verde lima, rojo popular, azul rótulo y negro"),
        ]
    if any(word in source for word in ["papel", "grano", "risograph", "editorial", "textura"]):
        return [
            ("Fondo", "papel escaneado, grano risograph y borde manual"),
            ("Mood", "editorial experimental, simple y coleccionable"),
            ("Detalle", "numeración grande, sello, etiqueta adhesiva"),
            ("Paleta", "papel viejo, negro, naranja y lima"),
        ]
    return [
        ("Fondo", "textura real, no fondo plano genérico"),
        ("Mood", "bold, popular, editorial y calle"),
        ("Detalle", "sticker, sello DOMO, grano y contraste fuerte"),
        ("Paleta", "negro, lima, blanco sucio y un acento caliente"),
    ]


def render_carousel_slide(slide: dict) -> None:
    number = int(slide.get("number") or 1)
    text = clean_text(slide.get("text"), "")
    microcopy = clean_text(slide.get("microcopy"), "")
    visual = clean_text(slide.get("visual") or slide.get("note"), "")
    bg_class = visual_background_class(visual, text)
    pills = "".join(
        f'<span class="domo-visual-pill">{html.escape(label)}: {html.escape(value)}</span>'
        for label, value in visual_brief(visual, text)
    )
    st.markdown(
        f"""
        <article class="domo-slide-card">
            <div class="domo-post-preview {bg_class}">
                <div class="domo-post-top">
                    <div class="domo-slide-number">{number:02d}</div>
                    <span class="domo-post-brand">DOMO</span>
                </div>
                <div class="domo-post-copy">
                    <span class="domo-slide-label">Texto grande</span>
                    <p class="domo-slide-big">{html.escape(text)}</p>
                    <span class="domo-slide-label">Texto pequeño</span>
                    <p class="domo-slide-small">{html.escape(microcopy)}</p>
                </div>
            </div>
            <div class="domo-slide-detail">
                <span class="domo-slide-label">Imagen / fondo ideal</span>
                <div class="domo-visual-pills">{pills}</div>
                <div class="domo-slide-visual">{html.escape(visual)}</div>
            </div>
        </article>
        """,
        unsafe_allow_html=True,
    )


def card_markup(card: dict, signal: str = "") -> None:
    cls = {"Alta": "domo-cyan", "Media": "domo-orange", "Baja": "domo-pink"}.get(clean_text(card.get("priority")), "")
    st.markdown(
        f"""
        <article class="domo-card {cls}">
            <div class="domo-card-title">{html.escape(clean_text(card.get("title"), "Idea DOMO"))}</div>
            <div class="domo-card-meta">
                <span class="domo-pill">{html.escape(clean_text(card.get("format"), "Contenido"))}</span>
                <span class="domo-pill">{html.escape(clean_text(card.get("pillar"), "DOMO"))}</span>
                <span class="domo-pill">{html.escape(clean_text(card.get("priority"), "Media"))}</span>
            </div>
            <div class="domo-hook">{html.escape(clean_text(card.get("hook"), ""))}</div>
            <p class="domo-sub"><b>Por qué sirve:</b> {html.escape(clean_text(card.get("strategic_reason"), ""))}</p>
            <p class="domo-sub"><b>CTA:</b> {html.escape(clean_text(card.get("cta"), ""))}</p>
        </article>
        """,
        unsafe_allow_html=True,
    )


def render_draft_cards(posts: pd.DataFrame) -> None:
    cards = st.session_state.get("draft_cards", [])
    if not cards:
        st.markdown(
            '<div class="domo-note">Escríbeme arriba. Te devuelvo pocas opciones, concretas y accionables.</div>',
            unsafe_allow_html=True,
        )
        return
    st.subheader("Opciones listas para trabajar")
    for index, card in enumerate(cards):
        card_markup(card)
        cols = st.columns(4)
        if cols[0].button("Guardar", key=f"save_draft_{index}", use_container_width=True, type="primary"):
            save_idea(card)
            st.success("Guardada.")
            st.rerun()
        if cols[1].button("Carrusel", key=f"car_draft_{index}", use_container_width=True):
            carousel = generate_carousel(card.get("title", ""), "saves", posts, pd.DataFrame())
            conn = cache_store.get_connection()
            cache_store.add_carousel_draft(
                conn,
                "chat",
                carousel.get("title", card.get("title", "Carrusel DOMO")),
                carousel.get("objective", "saves"),
                slides_to_json(carousel),
                carousel.get("caption", ""),
                carousel.get("cta", ""),
            )
            conn.close()
            st.success("Carrusel guardado.")
            st.rerun()
        if cols[2].button("LinkedIn", key=f"li_draft_{index}", use_container_width=True):
            st.session_state["draft_cards"][index]["format"] = "LinkedIn post"
            st.session_state["draft_cards"][index]["hook"] = card.get("linkedin_adaptation", card.get("hook", ""))
            st.rerun()
        if cols[3].button("Borrar", key=f"del_draft_{index}", use_container_width=True):
            st.session_state["draft_cards"].pop(index)
            st.rerun()


def render_home(data: dict[str, pd.DataFrame]) -> None:
    posts = data["posts"]
    reading = metric_reading(posts)
    header("Qué hago hoy", "Abre la app, pregunta en lenguaje normal y convierte respuestas en piezas guardables.", data)
    path_nav("home")
    action_guide(
        [
            ("Paso 1", "Pregunta normal", "Escribe lo que tienes: fotos, mockups, marca, lettering o una duda concreta."),
            ("Paso 2", "Elige una tarjeta", "Guarda la mejor idea o conviértela directo en carrusel o LinkedIn."),
            ("Paso 3", "Revisa señal", "Usa la lectura rápida para decidir si necesitas shares, saves o comentarios."),
        ]
    )
    left, right = st.columns([1.55, .9], gap="medium")
    with left:
        st.markdown(
            """
            <section class="domo-chat">
                <span class="domo-kicker">chat principal</span>
                <h2>Dime qué necesitas crear</h2>
                <p class="domo-sub">Ej: qué publico hoy, dame un Reel de fotografía, algo de lettering, convierte esta idea en carrusel.</p>
            </section>
            """,
            unsafe_allow_html=True,
        )
        chips = [
            "qué publico hoy",
            "dame ideas de fotografía publicitaria",
            "quiero algo sobre lettering en Cuenca",
            "convierte mi material de mockups en contenido",
            "qué repito de lo que funcionó",
            "dame un post de LinkedIn para vender consultoría",
        ]
        cols = st.columns(3)
        for i, chip in enumerate(chips):
            if cols[i % 3].button(chip, key=f"chip_{i}", use_container_width=True):
                st.session_state["chat_prompt"] = chip
                st.rerun()
        prompt = st.text_area(
            "Pregunta",
            value=st.session_state.pop("chat_prompt", ""),
            placeholder="Escribe como hablas: 'tengo fotos de marca y mockups, qué subo hoy?'",
            height=120,
            label_visibility="collapsed",
        )
        if st.button("Responder con ideas", type="primary", use_container_width=True):
            if prompt.strip():
                with st.spinner("Pensando en DOMO, Cuenca, marca, foto y crecimiento real..."):
                    st.session_state["draft_cards"] = create_cards(prompt, posts)
                conn = cache_store.get_connection()
                cache_store.add_assistant_note(conn, prompt, json.dumps(st.session_state["draft_cards"], ensure_ascii=False))
                conn.close()
                st.rerun()
        render_draft_cards(posts)
    with right:
        st.markdown('<section class="domo-panel">', unsafe_allow_html=True)
        st.subheader("Lectura rápida")
        st.markdown(
            f"""
            <div class="domo-note">
            <b>Siguiente movimiento:</b><br>{html.escape(reading["next_move"])}
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            f"""
            <div class="domo-grid" style="grid-template-columns:1fr 1fr;margin-top:14px">
                <div class="domo-metric" style="--metric:var(--cyan)"><span>shares</span><b>{reading["share"]}</b></div>
                <div class="domo-metric" style="--metric:var(--lime)"><span>saves</span><b>{reading["save"]}</b></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.write("Mejor señal:", reading["best_title"])
        st.write("Formato a mirar:", reading["best_format"])
        st.markdown("</section>", unsafe_allow_html=True)


def render_create(data: dict[str, pd.DataFrame]) -> None:
    posts = data["posts"]
    ideas = data["ideas"]
    inspirations = data["inspirations"]
    header("Crear", "Todo lo guardado se puede editar, borrar o convertir. Sin formularios largos.", data)
    path_nav("create")
    action_guide(
        [
            ("Ideas", "Ordena lo guardado", "Edita, duplica, borra o convierte una idea en carrusel."),
            ("Carruseles", "Diseña slide por slide", "Cada slide tiene texto grande, texto pequeño, fondo ideal y copy para pegar."),
            ("Links", "Alimenta el sistema", "Pega referencias útiles para traducirlas al lenguaje visual DOMO."),
        ]
    )

    tab_ideas, tab_carousel, tab_links = st.tabs(["Ideas", "Carruseles", "Links"])
    with tab_ideas:
        if ideas.empty:
            st.markdown('<div class="domo-note">Aún no hay ideas guardadas. Ve a Hoy, pregunta algo y guarda una tarjeta.</div>', unsafe_allow_html=True)
        for _, row in ideas.iterrows():
            item_id = int(row["id"])
            card_markup(row.to_dict())
            with st.expander("Editar"):
                title = st.text_input("Título", value=clean_text(row.get("title")), key=f"title_{item_id}")
                hook = st.text_area("Hook", value=clean_text(row.get("hook")), key=f"hook_{item_id}")
                cta = st.text_area("CTA", value=clean_text(row.get("cta")), key=f"cta_{item_id}")
                strategic = st.text_area("Criterio", value=clean_text(row.get("strategic_reason")), key=f"reason_{item_id}")
                cols = st.columns(4)
                if cols[0].button("Guardar cambios", key=f"upd_{item_id}", type="primary"):
                    update_idea(item_id, {"title": title, "hook": hook, "cta": cta, "strategic_reason": strategic})
                    st.success("Actualizada.")
                    st.rerun()
                if cols[1].button("Duplicar", key=f"dup_{item_id}"):
                    new_card = row.to_dict()
                    new_card["title"] = f"{title} / variante"
                    save_idea(new_card)
                    st.rerun()
                if cols[2].button("Hacer carrusel", key=f"mkcar_{item_id}"):
                    carousel = generate_carousel(title, "saves", posts, inspirations)
                    conn = cache_store.get_connection()
                    cache_store.add_carousel_draft(
                        conn,
                        "idea",
                        carousel.get("title", title),
                        carousel.get("objective", "saves"),
                        slides_to_json(carousel),
                        carousel.get("caption", ""),
                        carousel.get("cta", ""),
                    )
                    conn.close()
                    st.success("Carrusel creado.")
                if cols[3].button("Borrar", key=f"rm_{item_id}"):
                    delete_idea(item_id)
                    st.rerun()
    with tab_carousel:
        seed = st.text_area("Idea base para carrusel", placeholder="Ej: Pinterest no entiende tu barrio / mockups no son decoración")
        objective = st.selectbox("Objetivo", ["saves", "shares", "comentarios", "leads"])
        if st.button("Crear carrusel slide por slide", type="primary"):
            carousel = generate_carousel(seed, objective, posts, inspirations)
            conn = cache_store.get_connection()
            cache_store.add_carousel_draft(
                conn,
                "manual",
                carousel.get("title", seed or "Carrusel DOMO"),
                carousel.get("objective", objective),
                slides_to_json(carousel),
                carousel.get("caption", ""),
                carousel.get("cta", ""),
            )
            conn.close()
            st.success("Carrusel guardado.")
            st.rerun()
        carousels = data["carousels"]
        if carousels.empty:
            st.markdown(
                '<div class="domo-note">Aún no hay carruseles guardados. Escribe una idea arriba y crea el primero.</div>',
                unsafe_allow_html=True,
            )
        for _, row in carousels.iterrows():
            carousel_id = int(row["id"])
            title = clean_text(row.get("title"), "Carrusel DOMO")
            caption = clean_text(row.get("caption"), "")
            cta = clean_text(row.get("cta"), "")
            objective_saved = clean_text(row.get("objective"), "saves")
            st.markdown(
                f"""
                <section class="domo-carousel-head">
                    <div class="domo-caption-box">
                        <span class="domo-kicker">Carrusel / {html.escape(objective_saved)}</span>
                        <h2>{html.escape(title)}</h2>
                    </div>
                    <div class="domo-caption-box">
                        <span class="domo-slide-label">Caption</span>
                        <p class="domo-sub">{html.escape(caption or "Caption pendiente.")}</p>
                        <span class="domo-slide-label">CTA</span>
                        <p class="domo-sub">{html.escape(cta or "CTA pendiente.")}</p>
                    </div>
                </section>
                """,
                unsafe_allow_html=True,
            )
            top_cols = st.columns([1, 1, 1])
            with top_cols[0]:
                copy_button("Copiar caption + CTA", f"{caption}\n\n{cta}".strip(), f"caption_{carousel_id}")
            if top_cols[1].button("Editar portada/caption", key=f"edit_caption_toggle_{carousel_id}", use_container_width=True):
                st.session_state[f"edit_carousel_{carousel_id}"] = not st.session_state.get(f"edit_carousel_{carousel_id}", False)
            if top_cols[2].button("Borrar carrusel", key=f"delete_carousel_{carousel_id}", use_container_width=True):
                delete_carousel(carousel_id)
                st.success("Carrusel borrado.")
                st.rerun()

            if st.session_state.get(f"edit_carousel_{carousel_id}", False):
                with st.expander("Editar portada, caption y CTA", expanded=True):
                    new_title = st.text_input("Título", value=title, key=f"carousel_title_{carousel_id}")
                    new_caption = st.text_area("Caption", value=caption, key=f"carousel_caption_{carousel_id}", height=120)
                    new_cta = st.text_area("CTA", value=cta, key=f"carousel_cta_{carousel_id}", height=80)
                    new_objective = st.selectbox(
                        "Objetivo",
                        ["saves", "shares", "comentarios", "leads"],
                        index=["saves", "shares", "comentarios", "leads"].index(objective_saved)
                        if objective_saved in ["saves", "shares", "comentarios", "leads"]
                        else 0,
                        key=f"carousel_objective_{carousel_id}",
                    )
                    if st.button("Guardar portada/caption", key=f"save_carousel_{carousel_id}", type="primary"):
                        update_carousel(
                            carousel_id,
                            {"title": new_title, "caption": new_caption, "cta": new_cta, "objective": new_objective},
                        )
                        st.success("Carrusel actualizado.")
                        st.rerun()

            try:
                slides = json.loads(row.get("slides_json") or "[]")
            except Exception:
                slides = []
            normalized_slides, changed = normalize_carousel_slides(slides)
            if changed and normalized_slides:
                maybe_backfill_carousel(row, normalized_slides)
            for slide_index, slide in enumerate(normalized_slides):
                render_carousel_slide(slide)
                slide_number = int(slide.get("number") or slide_index + 1)
                slide_text = clean_text(slide.get("text"), "")
                slide_microcopy = clean_text(slide.get("microcopy"), "")
                slide_visual = clean_text(slide.get("visual"), "")
                action_cols = st.columns([1, 1])
                with action_cols[0]:
                    copy_button(
                        f"Copiar slide {slide_number:02d}",
                        f"{slide_text}\n{slide_microcopy}".strip(),
                        f"slide_{carousel_id}_{slide_index}",
                    )
                if action_cols[1].button(
                    f"Editar slide {slide_number:02d}",
                    key=f"edit_slide_toggle_{carousel_id}_{slide_index}",
                    use_container_width=True,
                ):
                    edit_key = f"edit_slide_{carousel_id}_{slide_index}"
                    st.session_state[edit_key] = not st.session_state.get(edit_key, False)

                if st.session_state.get(f"edit_slide_{carousel_id}_{slide_index}", False):
                    with st.expander(f"Editar contenido del slide {slide_number:02d}", expanded=True):
                        new_big = st.text_area(
                            "Texto grande",
                            value=slide_text,
                            key=f"slide_big_{carousel_id}_{slide_index}",
                            height=90,
                        )
                        new_small = st.text_area(
                            "Texto pequeño",
                            value=slide_microcopy,
                            key=f"slide_small_{carousel_id}_{slide_index}",
                            height=90,
                        )
                        new_visual = st.text_area(
                            "Imagen / fondo ideal",
                            value=slide_visual,
                            key=f"slide_visual_{carousel_id}_{slide_index}",
                            height=90,
                        )
                        edit_cols = st.columns([1, 1])
                        if edit_cols[0].button("Guardar slide", key=f"save_slide_{carousel_id}_{slide_index}", type="primary"):
                            updated = list(normalized_slides)
                            updated[slide_index] = {
                                **slide,
                                "text": new_big,
                                "microcopy": new_small,
                                "visual": new_visual,
                            }
                            save_carousel_slides(carousel_id, updated)
                            st.success("Slide actualizado.")
                            st.rerun()
                        if edit_cols[1].button("Eliminar slide", key=f"remove_slide_{carousel_id}_{slide_index}"):
                            updated = [item for i, item in enumerate(normalized_slides) if i != slide_index]
                            save_carousel_slides(carousel_id, updated)
                            st.success("Slide eliminado.")
                            st.rerun()
    with tab_links:
        url = st.text_input("Pega un link que te parece chévere")
        notes = st.text_area("Qué te llamó la atención", height=80)
        if st.button("Traducir a DOMO", type="primary"):
            if url:
                with st.spinner("Leyendo link y traduciéndolo a DOMO..."):
                    result = analyze_link_for_domo(url, notes, posts)
                conn = cache_store.get_connection()
                cache_store.add_inspiration(
                    conn,
                    url,
                    result.get("title", url),
                    result.get("source_notes", notes),
                    result.get("domo_angle", ""),
                    result.get("suggested_content", ""),
                )
                conn.close()
                st.success("Guardado como inspiración.")
                st.rerun()
        for _, row in inspirations.head(10).iterrows():
            st.markdown(
                f"""
                <article class="domo-card domo-cyan">
                    <div class="domo-card-title">{html.escape(clean_text(row.get("title"), "Inspiración"))}</div>
                    <p class="domo-sub">{html.escape(clean_text(row.get("suggested_content"), ""))}</p>
                </article>
                """,
                unsafe_allow_html=True,
            )


def render_learn(data: dict[str, pd.DataFrame]) -> None:
    posts = data["posts"]
    header("Métricas", "Qué pegó, qué no, qué repetir y qué corregir. Sin tablas eternas.", data)
    path_nav("learn")
    action_guide(
        [
            ("Detectar", "Mira la métrica débil", "Si shares o saves están bajos, la app te dice qué ajustar."),
            ("Repetir", "Encuentra señales fuertes", "No copies el post: repite el criterio con otro ejemplo visual."),
            ("Corregir", "Decide el próximo formato", "Usa la lectura para elegir Reel, carrusel o LinkedIn."),
        ]
    )
    reading = metric_reading(posts)
    st.markdown(
        f"""
        <div class="domo-grid">
            <div class="domo-metric" style="--metric:var(--cyan)"><span>shares</span><b>{reading["share"]}</b><p class="domo-sub">Si está bajo: más frase compartible, postura y orgullo local.</p></div>
            <div class="domo-metric" style="--metric:var(--lime)"><span>saves</span><b>{reading["save"]}</b><p class="domo-sub">Si está bajo: carruseles útiles, checklist y método visual.</p></div>
            <div class="domo-metric" style="--metric:var(--pink)"><span>comentarios</span><b>{reading["comments"]}</b><p class="domo-sub">Si está bajo: pregunta con tensión, no pregunta genérica.</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(f'<div class="domo-note" style="margin-top:16px"><b>Diagnóstico:</b> {html.escape(reading["next_move"])}</div>', unsafe_allow_html=True)

    if not posts.empty:
        top = posts.copy()
        for col in ["share_rate", "save_rate", "quality_comment_rate", "profile_visit_rate"]:
            top[col] = pd.to_numeric(top[col], errors="coerce").fillna(0)
        top["score"] = top["share_rate"] * 2 + top["save_rate"] * 2 + top["quality_comment_rate"] + top["profile_visit_rate"]
        top = top.sort_values("score", ascending=False).head(6)
        st.subheader("Repite esto")
        for _, row in top.iterrows():
            st.markdown(
                f"""
                <article class="domo-card">
                    <div class="domo-card-title">{html.escape(clean_text(row.get("title"), ""))}</div>
                    <div class="domo-card-meta">
                        <span class="domo-pill">{html.escape(clean_text(row.get("format"), ""))}</span>
                        <span class="domo-pill">shares {as_percent(row.get("share_rate"))}</span>
                        <span class="domo-pill">saves {as_percent(row.get("save_rate"))}</span>
                    </div>
                    <p class="domo-sub">Haz una versión nueva cambiando el ejemplo, no el criterio.</p>
                </article>
                """,
                unsafe_allow_html=True,
            )
        chart = px.bar(
            top,
            x="title",
            y=["share_rate", "save_rate", "quality_comment_rate"],
            barmode="group",
            template="plotly_dark",
        )
        chart.update_layout(height=360, margin=dict(l=10, r=10, t=20, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(chart, use_container_width=True)


def main() -> None:
    init_app()
    if not require_login():
        return
    inject_styles()
    data = load_data()
    sidebar_status(data)

    query_page = st.query_params.get("page")
    if isinstance(query_page, list):
        query_page = query_page[0] if query_page else None
    if query_page in {"home", "create", "learn"}:
        st.session_state["page"] = query_page
    page = st.session_state.get("page", "home")
    bottom_nav(page)

    if page == "create":
        render_create(data)
    elif page == "learn":
        render_learn(data)
    else:
        render_home(data)


if __name__ == "__main__":
    main()
