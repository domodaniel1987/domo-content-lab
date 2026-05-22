from __future__ import annotations

import os
import json
import socket
import html
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

import cache as cache_store
from assistant import (
    ai_complete,
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
delete_row = getattr(cache_store, "delete_row", None)
update_row = getattr(cache_store, "update_row", None)


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


def safe_update_record(table: str, item_id: int, values: dict) -> bool:
    if update_row is None:
        st.warning("Actualiza cache.py para poder editar registros.")
        return False
    conn = get_connection()
    update_row(conn, table, int(item_id), values)
    conn.close()
    return True


def safe_delete_record(table: str, item_id: int) -> bool:
    if delete_row is None:
        st.warning("Actualiza cache.py para poder borrar registros.")
        return False
    conn = get_connection()
    delete_row(conn, table, int(item_id))
    conn.close()
    return True


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
            --md-sys-color-primary: #063B2D;
            --md-sys-color-on-primary: #F9F6EE;
            --md-sys-color-primary-container: #DFF36B;
            --md-sys-color-on-primary-container: #063B2D;
            --md-sys-color-secondary: #6C63FF;
            --md-sys-color-tertiary: #00A8C8;
            --md-sys-color-error: #F45B69;
            --md-sys-color-background: #F3F1EA;
            --md-sys-color-surface: #F9F6EE;
            --md-sys-color-surface-container: #ECE9DE;
            --md-sys-color-surface-container-high: #E2DED1;
            --md-sys-color-outline: rgba(6, 59, 45, 0.16);
            --md-sys-color-outline-variant: rgba(6, 59, 45, 0.09);
            --md-sys-elevation-1: 0 1px 0 rgba(6,59,45,.08), 0 10px 24px rgba(6,59,45,.05);
            --md-sys-elevation-2: 0 1px 0 rgba(6,59,45,.10), 0 16px 34px rgba(6,59,45,.08);
            --md-sys-elevation-3: 0 1px 0 rgba(6,59,45,.12), 0 24px 48px rgba(6,59,45,.11);
            --domo-radius-sm: 16px;
            --domo-radius-md: 22px;
            --domo-radius-lg: 32px;
            --domo-ease-out: cubic-bezier(.16, 1, .3, 1);
            --domo-ease-pop: cubic-bezier(.34, 1.56, .64, 1);
            --domo-pink: #FF7AC8;
            --domo-lilac: #9B8CFF;
            --domo-cyan: #38C9E8;
            --domo-orange: #F3A83B;
        }}
        @keyframes domo-enter {{
            from {{
                opacity: 0;
                transform: translateY(18px) scale(.98);
                filter: blur(8px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0) scale(1);
                filter: blur(0);
            }}
        }}
        @keyframes domo-soft-rise {{
            from {{
                opacity: 0;
                transform: translateY(12px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}
        @keyframes domo-stamp {{
            0% {{
                opacity: 0;
                transform: rotate(-4deg) scale(.88);
            }}
            70% {{
                opacity: 1;
                transform: rotate(-1deg) scale(1.04);
            }}
            100% {{
                opacity: 1;
                transform: rotate(0) scale(1);
            }}
        }}
        @keyframes domo-scan {{
            from {{
                transform: translateX(-115%);
            }}
            to {{
                transform: translateX(115%);
            }}
        }}
        .stApp {{
            background:
                radial-gradient(circle at 15% 4%, rgba(223,243,107,.38), transparent 20%),
                radial-gradient(circle at 82% 7%, rgba(56,201,232,.16), transparent 22%),
                linear-gradient(180deg, #F3F1EA 0%, #F8F5ED 48%, #EFECE1 100%);
            color: var(--md-sys-color-primary);
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }}
        .block-container {{
            max-width: 1320px;
            padding-top: 1.7rem;
            padding-bottom: 4rem;
            animation: domo-enter .62s var(--domo-ease-out) both;
        }}
        h1 {{
            letter-spacing: 0 !important;
            font-weight: 850 !important;
            text-transform: none;
            line-height: 1.02 !important;
            font-size: clamp(2.15rem, 4.4vw, 4.4rem) !important;
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
            background: rgba(243,241,234,.72);
            backdrop-filter: blur(18px);
            border-bottom: 1px solid rgba(6,59,45,.08);
        }}
        [data-testid="stToolbar"] {{
            right: 1rem;
        }}
        [data-testid="stMetric"] {{
            background: var(--md-sys-color-surface);
            border: 1px solid var(--md-sys-color-outline-variant);
            border-radius: 28px;
            padding: 18px 20px;
            box-shadow: var(--md-sys-elevation-1);
            animation: domo-soft-rise .48s var(--domo-ease-out) both;
            transition: transform .22s var(--domo-ease-out), box-shadow .22s var(--domo-ease-out);
        }}
        [data-testid="stMetric"]:hover {{
            transform: translateY(-3px);
            box-shadow: var(--md-sys-elevation-2);
        }}
        [data-testid="stMetric"] * {{
            color: var(--md-sys-color-primary) !important;
        }}
        [data-testid="stMetricValue"] {{
            color: #033B2A !important;
            font-weight: 900 !important;
            font-size: clamp(2.2rem, 4vw, 4.2rem) !important;
            letter-spacing: -0.02em !important;
        }}
        div[data-testid="stDataFrame"] {{
            border: 1px solid var(--md-sys-color-outline-variant);
            border-radius: var(--domo-radius-md);
            overflow: hidden;
            box-shadow: var(--md-sys-elevation-1);
        }}
        div[data-testid="stExpander"] {{
            border: 1px solid var(--md-sys-color-outline-variant);
            border-radius: 26px;
            box-shadow: var(--md-sys-elevation-1);
            background: var(--md-sys-color-surface);
            animation: domo-soft-rise .44s var(--domo-ease-out) both;
            transition: transform .22s var(--domo-ease-out), box-shadow .22s var(--domo-ease-out);
        }}
        div[data-testid="stExpander"]:hover {{
            transform: translateY(-2px);
            box-shadow: var(--md-sys-elevation-2);
        }}
        input, textarea, [data-baseweb="select"] > div, [data-baseweb="input"] > div {{
            border-radius: 999px !important;
            background: rgba(249,246,238,.88) !important;
            border-color: rgba(6,59,45,.08) !important;
        }}
        textarea {{
            border-radius: 22px !important;
        }}
        .domo-hero {{
            background:
                linear-gradient(135deg, rgba(249,246,238,.96) 0%, rgba(236,233,222,.94) 100%);
            color: var(--md-sys-color-primary);
            border: 1px solid rgba(6,59,45,.10);
            border-radius: 36px;
            padding: clamp(22px, 4vw, 38px);
            box-shadow: var(--md-sys-elevation-2);
            margin-bottom: 24px;
            position: relative;
            overflow: hidden;
            animation: domo-enter .78s var(--domo-ease-out) both;
        }}
        .domo-hero:after {{
            content: "";
            position: absolute;
            inset: auto -24px -24px auto;
            width: 180px;
            height: 180px;
            border: 2px dashed rgba(6,59,45,.18);
            border-radius: 36px;
            transform: rotate(-8deg);
            animation: domo-stamp .7s var(--domo-ease-pop) .18s both;
        }}
        .domo-hero:before {{
            content: "";
            position: absolute;
            inset: 0;
            background: linear-gradient(90deg, transparent, rgba(223,243,107,.24), transparent);
            animation: domo-scan 1.2s var(--domo-ease-out) .2s both;
            pointer-events: none;
        }}
        .domo-hero h1 {{
            color: var(--md-sys-color-primary) !important;
            margin: 16px 0 16px;
        }}
        .domo-topbar {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            margin-bottom: 18px;
        }}
        .domo-search-pill {{
            background: rgba(255,255,255,.70);
            border: 1px solid rgba(6,59,45,.10);
            border-radius: 999px;
            padding: 10px 16px;
            min-width: min(420px, 100%);
            color: rgba(6,59,45,.56);
            font-size: .92rem;
            box-shadow: var(--md-sys-elevation-1);
        }}
        .domo-avatar {{
            width: 40px;
            height: 40px;
            border-radius: 999px;
            background: var(--md-sys-color-primary);
            color: var(--md-sys-color-on-primary);
            display: grid;
            place-items: center;
            font-weight: 900;
            box-shadow: var(--md-sys-elevation-1);
        }}
        .domo-hero p {{
            color: rgba(6,59,45,.72) !important;
            max-width: 850px;
            font-size: 1.08rem;
            margin: 0;
        }}
        .domo-hero-grid {{
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 10px;
            margin-top: 24px;
            max-width: 880px;
        }}
        .domo-hero-chip {{
            background: rgba(255,255,255,.52);
            border: 1px solid rgba(6,59,45,.10);
            border-radius: 999px;
            color: var(--md-sys-color-primary);
            padding: 10px 14px;
            font-weight: 800;
            text-align: center;
            transition: transform .2s var(--domo-ease-pop), background .2s var(--domo-ease-out), border-color .2s var(--domo-ease-out);
        }}
        .domo-hero-chip:nth-child(1) {{
            background: #DFF36B;
        }}
        .domo-hero-chip:nth-child(2) {{
            background: #FFD36E;
        }}
        .domo-hero-chip:nth-child(3) {{
            background: #FF9EDB;
        }}
        .domo-hero-chip:nth-child(4) {{
            background: #88E7F7;
        }}
        .domo-hero-chip:hover {{
            transform: translateY(-2px) scale(1.02);
            background: rgba(223,243,107,.50);
            border-color: rgba(6,59,45,.16);
        }}
        .domo-label {{
            display: inline-block;
            background: var(--md-sys-color-primary-container);
            color: var(--md-sys-color-on-primary-container);
            border: 1px solid rgba(6,59,45,.12);
            border-radius: 999px;
            padding: 7px 12px;
            font-weight: 900;
            text-transform: none;
            margin-bottom: 8px;
            font-size: .82rem;
            box-shadow: var(--md-sys-elevation-1);
            animation: domo-stamp .45s var(--domo-ease-pop) both;
        }}
        .domo-note {{
            border-left: 7px solid var(--domo-pink);
            background: var(--md-sys-color-surface);
            border-radius: 0 24px 24px 0;
            padding: 16px 18px;
            font-size: 1rem;
            box-shadow: var(--md-sys-elevation-1);
        }}
        .domo-action {{
            background: var(--md-sys-color-surface);
            border: 1px solid var(--md-sys-color-outline-variant);
            border-radius: 30px;
            padding: 18px;
            min-height: 168px;
            box-shadow: var(--md-sys-elevation-1);
            animation: domo-soft-rise .5s var(--domo-ease-out) both;
            transition: transform .22s var(--domo-ease-out), box-shadow .22s var(--domo-ease-out), border-color .22s var(--domo-ease-out);
        }}
        .domo-action:hover {{
            transform: translateY(-4px) scale(1.01);
            box-shadow: var(--md-sys-elevation-2);
            border-color: rgba(6,59,45,.18);
        }}
        .domo-action strong {{
            display: block;
            font-size: 1.05rem;
            margin-top: 10px;
            line-height: 1.2;
        }}
        .domo-action p {{
            margin-bottom: 0;
            color: rgba(6,59,45,.70);
        }}
        .domo-launch {{
            background: var(--md-sys-color-surface);
            color: var(--md-sys-color-primary);
            border-radius: 32px;
            border: 1px solid rgba(6,59,45,.10);
            box-shadow: var(--md-sys-elevation-1);
            padding: 20px;
            min-height: 175px;
            margin-bottom: 12px;
            position: relative;
            overflow: hidden;
            animation: domo-soft-rise .52s var(--domo-ease-out) both;
            transition: transform .24s var(--domo-ease-out), box-shadow .24s var(--domo-ease-out), border-color .24s var(--domo-ease-out);
        }}
        .domo-launch:before {{
            content: "";
            position: absolute;
            inset: 0;
            background: linear-gradient(90deg, transparent, rgba(223,243,107,.32), transparent);
            transform: translateX(-120%);
            transition: transform .62s var(--domo-ease-out);
            pointer-events: none;
        }}
        .domo-launch:hover {{
            transform: translateY(-5px) scale(1.012);
            box-shadow: var(--md-sys-elevation-2);
            border-color: rgba(6,59,45,.18);
        }}
        .domo-launch:hover:before {{
            transform: translateX(120%);
        }}
        .domo-launch h3 {{
            color: var(--md-sys-color-primary) !important;
            margin: 8px 0;
            font-size: 1.15rem;
        }}
        .domo-launch p {{
            color: rgba(6,59,45,.68) !important;
            margin: 0;
        }}
        .domo-launch .domo-badge {{
            background: var(--md-sys-color-primary-container);
            color: var(--md-sys-color-on-primary-container);
        }}
        .domo-pill {{
            display: inline-block;
            background: var(--domo-pink);
            color: #250018;
            border-radius: 999px;
            padding: 4px 9px;
            font-weight: 900;
            margin-right: 5px;
            font-size: .78rem;
        }}
        .domo-output {{
            background: var(--md-sys-color-surface);
            border: 1px solid var(--md-sys-color-outline-variant);
            border-radius: 32px;
            box-shadow: var(--md-sys-elevation-1);
            padding: 22px;
            margin: 18px 0;
            animation: domo-enter .5s var(--domo-ease-out) both;
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
            border: 1px solid rgba(6,59,45,.12);
            background: var(--md-sys-color-primary-container);
            color: var(--md-sys-color-on-primary-container);
            border-radius: 999px;
            padding: 5px 10px;
            font-weight: 900;
            text-transform: none;
            font-size: 0.82rem;
        }}
        .domo-slide {{
            background:
                linear-gradient(160deg, #063B2D 0%, #0C513F 72%, #00A8C8 100%);
            color: var(--md-sys-color-on-primary);
            border-radius: 34px;
            padding: 22px;
            min-height: 230px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            border: 1px solid rgba(255,250,240,.10);
            box-shadow: var(--md-sys-elevation-3);
            margin-bottom: 16px;
            animation: domo-enter .5s var(--domo-ease-out) both;
            transition: transform .24s var(--domo-ease-out), box-shadow .24s var(--domo-ease-out);
        }}
        .domo-slide:hover {{
            transform: translateY(-3px) rotate(-.25deg);
            box-shadow: 0 14px 36px rgba(17,17,17,.22), 0 2px 8px rgba(17,17,17,.12);
        }}
        .domo-slide-number {{
            color: var(--md-sys-color-primary-container);
            font-weight: 900;
            text-transform: none;
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
            border-radius: 28px;
            padding: 18px;
            min-height: 150px;
            box-shadow: var(--md-sys-elevation-1);
            animation: domo-soft-rise .48s var(--domo-ease-out) both;
            transition: transform .22s var(--domo-ease-out), box-shadow .22s var(--domo-ease-out);
        }}
        .domo-step:hover {{
            transform: translateY(-3px);
            box-shadow: var(--md-sys-elevation-2);
        }}
        .domo-step-number {{
            display: inline-block;
            background: var(--md-sys-color-primary-container);
            color: var(--md-sys-color-on-primary-container);
            border-radius: 999px;
            min-width: 28px;
            height: 28px;
            text-align: center;
            line-height: 28px;
            font-weight: 900;
            margin-bottom: 10px;
        }}
        .domo-step:nth-child(1) .domo-step-number {{
            background: #DFF36B;
        }}
        .domo-step:nth-child(2) .domo-step-number {{
            background: #FFD36E;
        }}
        .domo-step:nth-child(3) .domo-step-number {{
            background: #FF9EDB;
        }}
        .domo-step:nth-child(4) .domo-step-number {{
            background: #88E7F7;
        }}
        .domo-step h3 {{
            font-size: 1rem;
            margin: 2px 0 8px;
        }}
        .domo-read {{
            background: var(--md-sys-color-surface);
            border: 1px solid var(--md-sys-color-outline-variant);
            border-radius: 30px;
            padding: 22px;
            box-shadow: var(--md-sys-elevation-1);
            min-height: 170px;
            animation: domo-soft-rise .5s var(--domo-ease-out) both;
            transition: transform .22s var(--domo-ease-out), box-shadow .22s var(--domo-ease-out);
        }}
        .domo-read:hover {{
            transform: translateY(-3px);
            box-shadow: var(--md-sys-elevation-3);
        }}
        .domo-read strong {{
            display: block;
            margin-bottom: 8px;
            font-size: 1.05rem;
        }}
        .domo-callout {{
            background: var(--md-sys-color-primary-container);
            border: 1px solid rgba(6,59,45,.12);
            border-radius: 999px;
            box-shadow: var(--md-sys-elevation-1);
            padding: 20px;
            margin: 12px 0 22px;
            font-weight: 800;
            animation: domo-enter .46s var(--domo-ease-out) both;
        }}
        .domo-chat-shell {{
            background: var(--md-sys-color-surface);
            border: 1px solid var(--md-sys-color-outline-variant);
            border-radius: 34px;
            padding: clamp(16px, 3vw, 26px);
            box-shadow: var(--md-sys-elevation-1);
            margin: 16px 0;
            animation: domo-enter .5s var(--domo-ease-out) both;
        }}
        .domo-chat-user,
        .domo-chat-assistant {{
            border-radius: 22px;
            padding: 14px 16px;
            margin: 10px 0;
            max-width: 88%;
            box-shadow: var(--md-sys-elevation-1);
            animation: domo-soft-rise .32s var(--domo-ease-out) both;
        }}
        .domo-chat-user {{
            margin-left: auto;
            background: var(--md-sys-color-primary);
            color: var(--md-sys-color-on-primary);
        }}
        .domo-chat-assistant {{
            margin-right: auto;
            background: var(--md-sys-color-surface-container);
            color: var(--md-sys-color-primary);
            border: 1px solid var(--md-sys-color-outline-variant);
        }}
        .domo-chat-user strong,
        .domo-chat-assistant strong {{
            display: block;
            font-size: .76rem;
            letter-spacing: .02em;
            text-transform: uppercase;
            margin-bottom: 5px;
            opacity: .75;
        }}
        .domo-chip-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin: 12px 0 6px;
        }}
        .domo-memory-card {{
            background: var(--md-sys-color-surface-container);
            border: 1px solid var(--md-sys-color-outline-variant);
            border-radius: 26px;
            padding: 14px;
            margin: 8px 0;
        }}
        .domo-small {{
            font-size: 0.92rem;
            opacity: 0.86;
        }}
        .domo-section {{
            background: rgba(249,246,238,.74);
            border: 1px solid var(--md-sys-color-outline-variant);
            border-radius: 34px;
            padding: clamp(16px, 3vw, 26px);
            box-shadow: var(--md-sys-elevation-1);
            margin: 18px 0;
        }}
        section[data-testid="stSidebar"] {{
            background: rgba(243,241,234,.94);
            border-right: 1px solid var(--md-sys-color-outline-variant);
            box-shadow: var(--md-sys-elevation-1);
        }}
        section[data-testid="stSidebar"] * {{
            color: var(--md-sys-color-primary) !important;
        }}
        section[data-testid="stSidebar"] code {{
            color: var(--md-sys-color-tertiary) !important;
            background: var(--md-sys-color-primary) !important;
            border-radius: 18px;
            padding: 8px !important;
        }}
        section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 {{
            font-size: .92rem !important;
            text-transform: uppercase;
            letter-spacing: .02em !important;
        }}
        div[role="radiogroup"] label {{
            color: var(--md-sys-color-primary) !important;
            font-weight: 720 !important;
            opacity: 1 !important;
            border-radius: 999px !important;
            padding: 8px 10px !important;
            min-height: 42px;
            transition: transform .18s var(--domo-ease-out), background .18s var(--domo-ease-out);
        }}
        div[role="radiogroup"] label:hover {{
            transform: translateX(3px);
            background: rgba(223,243,107,.30);
        }}
        div[role="radiogroup"] p {{
            color: var(--md-sys-color-primary) !important;
        }}
        .stButton > button {{
            background: var(--md-sys-color-primary) !important;
            color: var(--md-sys-color-on-primary) !important;
            border: 0 !important;
            border-radius: 999px !important;
            font-weight: 800 !important;
            min-height: 42px;
            padding: 0 18px !important;
            box-shadow: var(--md-sys-elevation-1);
            transition: transform .16s var(--domo-ease-pop), box-shadow .16s var(--domo-ease-out), background .16s var(--domo-ease-out);
        }}
        .stButton > button:hover {{
            transform: translateY(-2px) scale(1.015);
            box-shadow: var(--md-sys-elevation-2);
            background: #09513E !important;
        }}
        .stButton > button:active {{
            transform: translateY(0) scale(.98);
        }}
        .stButton > button:focus-visible {{
            outline: 3px solid rgba(223,243,107,.9) !important;
            outline-offset: 3px !important;
        }}
        .stButton > button * {{
            color: var(--md-sys-color-on-primary) !important;
        }}
        button[kind="primary"], .stDownloadButton > button {{
            background: var(--md-sys-color-primary-container) !important;
            color: var(--md-sys-color-on-primary-container) !important;
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
            transition: transform .18s var(--domo-ease-out), background .18s var(--domo-ease-out), box-shadow .18s var(--domo-ease-out);
        }}
        .stTabs [data-baseweb="tab"]:hover {{
            transform: translateY(-1px);
        }}
        .stTabs [aria-selected="true"] {{
            background: var(--md-sys-color-surface);
            box-shadow: var(--md-sys-elevation-1);
        }}
        a {{
            color: var(--md-sys-color-tertiary) !important;
            font-weight: 800;
        }}
        .domo-step:nth-of-type(2),
        .domo-action:nth-of-type(2),
        .domo-launch:nth-of-type(2),
        .domo-slide:nth-of-type(2) {{
            animation-delay: .05s;
        }}
        .domo-step:nth-of-type(3),
        .domo-action:nth-of-type(3),
        .domo-launch:nth-of-type(3),
        .domo-slide:nth-of-type(3) {{
            animation-delay: .1s;
        }}
        .domo-step:nth-of-type(4),
        .domo-action:nth-of-type(4),
        .domo-launch:nth-of-type(4),
        .domo-slide:nth-of-type(4) {{
            animation-delay: .15s;
        }}
        @media (prefers-reduced-motion: reduce) {{
            *,
            *::before,
            *::after {{
                animation-duration: .01ms !important;
                animation-iteration-count: 1 !important;
                scroll-behavior: auto !important;
                transition-duration: .01ms !important;
            }}
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
            .domo-topbar {{
                align-items: stretch;
            }}
            .domo-search-pill {{
                min-width: 0;
                flex: 1;
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
            <div class="domo-topbar">
                <div class="domo-search-pill">Buscar idea, marca, métrica o próximo movimiento</div>
                <div class="domo-avatar">D</div>
            </div>
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
                <div class="domo-hero-chip">Buscar collabs</div>
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
        ("Ideas", "Crear idea", "Reels, carruseles, branding, foto, INHAUS, mockups y LinkedIn."),
        ("Lectura", "Qué pegó", "Diagnóstico claro: qué funcionó, qué no y qué corregir."),
        ("Carruseles", "Hacer slides", "Frases por imagen listas para copiar y diseñar."),
        ("Asistente", "Preguntar", "Dile una duda y responde como estratega DOMO."),
        ("Inspiración", "Pegar link", "Convierte algo que viste en una idea a tu estilo."),
        ("Capturas", "Subir data", "Guarda screenshots y números para crear memoria."),
        ("Collabs", "Buscar marcas", "Encuentra oportunidades y redacta un mensaje de acercamiento."),
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
            if st.button(label, key=f"go_{target}"):
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
        delete_options = {
            f"{row['id']} · {row['title']}": int(row["id"])
            for _, row in action_items.iterrows()
            if "id" in action_items.columns
        }
        if delete_options:
            selected_action = st.selectbox("Borrar acción", ["Selecciona"] + list(delete_options.keys()))
            if selected_action != "Selecciona" and st.button("Borrar acción seleccionada"):
                safe_delete_record("action_items", delete_options[selected_action])
                st.success("Acción borrada.")
                st.rerun()


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
        for _, row in screenshots.head(20).iterrows():
            row_id = row.get("id")
            with st.expander(f"{row.get('date', '')} · {row.get('content_title', 'Captura')}"):
                with st.form(f"edit_screenshot_{row_id}"):
                    edit_date = st.text_input("Fecha", value=str(row.get("date", "")))
                    edit_platform = st.text_input("Plataforma", value=str(row.get("platform", "")))
                    edit_title = st.text_input("Contenido", value=str(row.get("content_title", "")))
                    edit_notes = st.text_area("Observaciones", value=str(row.get("notes", "")), height=100)
                    edit_ai = st.text_area("Lectura IA", value=str(row.get("ai_reading", "")), height=120)
                    save_capture = st.form_submit_button("Guardar cambios")
                if save_capture and row_id is not None:
                    safe_update_record(
                        "screenshots",
                        int(row_id),
                        {
                            "date": edit_date,
                            "platform": edit_platform,
                            "content_title": edit_title,
                            "notes": edit_notes,
                            "ai_reading": edit_ai,
                        },
                    )
                    st.success("Captura actualizada.")
                    st.rerun()
                if st.button("Borrar captura", key=f"delete_capture_{row_id}"):
                    safe_delete_record("screenshots", int(row_id))
                    st.success("Captura borrada.")
                    st.rerun()


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
        for _, row in inspirations.head(20).iterrows():
            row_id = row.get("id")
            with st.expander(f"{row.get('title', 'Link guardado')}"):
                with st.form(f"edit_inspiration_{row_id}"):
                    edit_title = st.text_input("Título", value=str(row.get("title", "")))
                    edit_url = st.text_input("Link", value=str(row.get("url", "")))
                    edit_notes = st.text_area("Observaciones", value=str(row.get("source_notes", "")), height=90)
                    edit_angle = st.text_area("Lectura DOMO", value=str(row.get("domo_angle", "")), height=110)
                    edit_content = st.text_area("Idea de contenido", value=str(row.get("suggested_content", "")), height=110)
                    save_inspiration = st.form_submit_button("Guardar cambios")
                if save_inspiration and row_id is not None:
                    safe_update_record(
                        "inspirations",
                        int(row_id),
                        {
                            "title": edit_title,
                            "url": edit_url,
                            "source_notes": edit_notes,
                            "domo_angle": edit_angle,
                            "suggested_content": edit_content,
                        },
                    )
                    st.success("Inspiración actualizada.")
                    st.rerun()
                col_car, col_delete = st.columns(2)
                with col_car:
                    if st.button("Usar en carrusel", key=f"inspo_carousel_{row_id}"):
                        st.session_state["page"] = "Carruseles"
                        st.session_state["carousel_seed"] = f"{edit_title}\n{edit_angle}\n{edit_content}"
                        st.rerun()
                with col_delete:
                    if st.button("Borrar inspiración", key=f"delete_inspiration_{row_id}"):
                        safe_delete_record("inspirations", int(row_id))
                        st.success("Inspiración borrada.")
                        st.rerun()


def render_trend_lab(posts: pd.DataFrame, trends: pd.DataFrame) -> None:
    st.subheader("Radar de trends")
    st.write("Busca señales web de diseño, cultura visual, marcas y dirección de arte para convertirlas en contenido DOMO.")

    with st.form("trend_form"):
        query = st.selectbox("Búsqueda sugerida", DEFAULT_TREND_QUERIES)
        custom_query = st.text_input("O escribe tu propia búsqueda", placeholder="Ej: marcas cool Ecuador diseño editorial")
        limit = st.slider("Resultados", min_value=3, max_value=10, value=5)
        include_instagram = st.checkbox("Incluir resultados públicos de Instagram si aparecen en la web", value=True)
        submitted = st.form_submit_button("Buscar trends", type="primary")

    if submitted:
        final_query = custom_query.strip() or query
        results = scout_trends(final_query, posts, limit=limit, include_instagram=include_instagram)
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
    st.write("Busca prospectos, guarda marcas y redacta un mensaje con una idea concreta para acercarte.")

    mode = st.radio(
        "Qué quieres hacer",
        ["Buscar marcas", "Agregar manual", "Ver oportunidades"],
        horizontal=True,
    )

    if mode == "Buscar marcas":
        col_a, col_b, col_c = st.columns([2, 1, 1])
        with col_a:
            focus = st.text_input(
                "Búsqueda",
                value="marcas Ecuador Cuenca diseño restaurantes hoteles moda cultura visual",
                help="La app busca en la web. Si Instagram no deja buscar directo, intenta encontrar perfiles públicos indexados.",
            )
        with col_b:
            limit = st.slider("Resultados", 3, 8, 5, key="collab_limit")
        with col_c:
            include_instagram = st.checkbox("Instagram web", value=True)
            search = st.button("Buscar prospectos", type="primary")

        if search:
            results = scout_trends(focus, posts, limit=limit, include_instagram=include_instagram)
            if not results:
                st.warning("No encontré prospectos ahora. Prueba una búsqueda más específica: sector + ciudad + marca.")
            for index, item in enumerate(results):
                title = item.get("title", "Prospecto")
                reading = item.get("domo_reading", "")
                with st.container(border=True):
                    st.markdown(f"### {title}")
                    st.caption(item.get("source", ""))
                    st.write(reading)
                    st.link_button("Abrir fuente", item.get("url", "https://google.com"))
                    if st.button("Guardar como oportunidad", key=f"save_web_collab_{index}_{title}"):
                        conn = get_connection()
                        add_collab_target(
                            conn,
                            title[:120],
                            focus,
                            reading or "Posible oportunidad detectada por búsqueda web.",
                            "Investigar perfil, preparar idea visual y escribir con propuesta concreta.",
                            "Media",
                            item.get("url", ""),
                        )
                        conn.close()
                        st.success("Oportunidad guardada.")

        st.markdown("#### También puedo sugerir tipos de marcas")
        if st.button("Sugerir categorías de collab"):
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

    if mode == "Agregar manual":
        with st.form("manual_collab_form"):
            name = st.text_input("Marca / persona / empresa")
            url = st.text_input("Link web o Instagram", placeholder="https://instagram.com/...")
            category = st.selectbox(
                "Categoría",
                ["Restaurante / café", "Hotel / turismo", "Moda", "Arquitectura / interiorismo", "Cultura / evento", "Marca local", "Agencia / estudio", "Otra"],
            )
            why_fit = st.text_area("Por qué encaja con DOMO")
            idea = st.text_area("Idea de colaboración", placeholder="Ej: mini campaña editorial + reel de proceso + carrusel de lectura visual.")
            priority = st.selectbox("Prioridad", ["Alta", "Media", "Baja"])
            save_manual = st.form_submit_button("Guardar oportunidad", type="primary")
        if save_manual and name:
            conn = get_connection()
            add_collab_target(conn, name, category, why_fit, idea, priority, url)
            conn.close()
            st.success("Oportunidad guardada.")

    st.markdown("#### Oportunidades guardadas")
    if collabs.empty:
        st.info("Todavía no hay collabs guardadas.")
    else:
        for _, row in collabs.head(20).iterrows():
            row_id = row.get("id")
            with st.expander(f"{row.get('name', 'Oportunidad')} · {row.get('status', 'Por investigar')}"):
                with st.form(f"edit_collab_{row_id}"):
                    edit_name = st.text_input("Nombre", value=str(row.get("name", "")))
                    edit_url = st.text_input("Link", value=str(row.get("url", "")))
                    cols = st.columns(3)
                    edit_category = cols[0].text_input("Categoría", value=str(row.get("category", "")))
                    edit_priority = cols[1].selectbox(
                        "Prioridad",
                        ["Alta", "Media", "Baja"],
                        index=["Alta", "Media", "Baja"].index(row.get("priority", "Media"))
                        if row.get("priority", "Media") in ["Alta", "Media", "Baja"]
                        else 1,
                        key=f"collab_priority_{row_id}",
                    )
                    edit_status = cols[2].selectbox(
                        "Estado",
                        ["Por investigar", "Contactar", "Mensaje enviado", "Respondió", "En conversación", "Ganada", "Descartada"],
                        index=["Por investigar", "Contactar", "Mensaje enviado", "Respondió", "En conversación", "Ganada", "Descartada"].index(row.get("status", "Por investigar"))
                        if row.get("status", "Por investigar") in ["Por investigar", "Contactar", "Mensaje enviado", "Respondió", "En conversación", "Ganada", "Descartada"]
                        else 0,
                        key=f"collab_status_{row_id}",
                    )
                    edit_why = st.text_area("Por qué encaja", value=str(row.get("why_fit", "")), height=90)
                    edit_approach = st.text_area("Idea / acercamiento", value=str(row.get("approach", "")), height=110)
                    save_collab = st.form_submit_button("Guardar cambios")

                if save_collab and row_id is not None:
                    safe_update_record(
                        "collab_targets",
                        int(row_id),
                        {
                            "name": edit_name,
                            "url": edit_url,
                            "category": edit_category,
                            "priority": edit_priority,
                            "status": edit_status,
                            "why_fit": edit_why,
                            "approach": edit_approach,
                        },
                    )
                    st.success("Oportunidad actualizada.")
                    st.rerun()

                default_message = (
                    f"Hola, vi el trabajo de {edit_name} y creo que hay una oportunidad visual interesante.\n\n"
                    f"Soy DOMO, director creativo, diseñador y fotógrafo publicitario en Cuenca. "
                    f"Me interesa proponer una colaboración alrededor de: {edit_approach}\n\n"
                    "La idea sería crear una pieza con criterio editorial + calle: contenido que no solo se vea bien, "
                    "sino que cuente por qué la marca tiene mundo, textura e identidad.\n\n"
                    "Si te interesa, te puedo mandar una propuesta corta con concepto, referencias y entregables."
                )
                message = st.text_area("Mensaje sugerido para DM/mail", value=default_message, height=210, key=f"msg_{row_id}")
                st.download_button(
                    "Descargar mensaje",
                    data=message.encode("utf-8"),
                    file_name=f"mensaje_collab_{str(edit_name).lower().replace(' ', '_')}.txt",
                    mime="text/plain",
                    key=f"download_msg_{row_id}",
                )
                col_use, col_delete = st.columns(2)
                with col_use:
                    if st.button("Convertir en acción", key=f"collab_action_{row_id}"):
                        conn = get_connection()
                        add_action_item(conn, f"Contactar a {edit_name}", "Collabs", edit_approach, edit_priority)
                        conn.close()
                        st.success("Acción guardada en Inicio.")
                with col_delete:
                    if st.button("Borrar oportunidad", key=f"delete_collab_{row_id}"):
                        safe_delete_record("collab_targets", int(row_id))
                        st.success("Oportunidad borrada.")
                        st.rerun()


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
    st.subheader("Copiloto DOMO")
    st.write("Tu asistente privado para decidir, crear y convertir contenido en oportunidades reales.")

    reading = build_metric_reading(posts)
    if "assistant_chat" not in st.session_state:
        st.session_state["assistant_chat"] = [
            {
                "role": "assistant",
                "content": (
                    "Estoy listo. Puedo ayudarte a decidir qué publicar hoy, convertir links en ideas, "
                    "armar carruseles, proponer Reels, leer métricas, preparar LinkedIn o buscar collabs."
                ),
            }
        ]

    seeded = st.session_state.pop("assistant_seed", "")
    if seeded:
        st.session_state["assistant_pending_prompt"] = seeded

    st.markdown(
        f"""
        <div class="domo-callout">
            Señal de hoy: {reading["next_move"]}
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("#### Qué necesitas ahora")
    suggestions = [
        "Dime qué publicar hoy para subir shares y saves.",
        "Convierte mi último Reel en un carrusel guardable con frases por imagen.",
        "Dame 5 ideas de Reels sobre branding, foto y cultura visual LATAM.",
        "Propón una idea de LinkedIn para vender workshops sin sonar vendedor.",
        "Busca una forma de conseguir collabs con marcas cool de Cuenca/Ecuador.",
        "Analiza qué pegó, qué no pegó y qué debí hacer distinto.",
    ]
    cols = st.columns(3)
    for index, prompt in enumerate(suggestions):
        with cols[index % 3]:
            if st.button(prompt, key=f"assistant_prompt_{index}"):
                st.session_state["assistant_pending_prompt"] = prompt
                st.rerun()

    st.markdown('<div class="domo-chat-shell">', unsafe_allow_html=True)
    for message in st.session_state["assistant_chat"][-10:]:
        role_class = "domo-chat-user" if message["role"] == "user" else "domo-chat-assistant"
        role_label = "Tú" if message["role"] == "user" else "DOMO AI"
        safe_content = html.escape(str(message["content"])).replace("\n", "<br>")
        st.markdown(
            f"""
            <div class="{role_class}">
                <strong>{role_label}</strong>
                {safe_content}
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

    pending_prompt = st.session_state.pop("assistant_pending_prompt", "")
    typed_prompt = st.chat_input("Escribe aquí: idea, link, duda, marca, métrica o algo que viste...")
    question = pending_prompt or typed_prompt

    if question:
        st.session_state["assistant_chat"].append({"role": "user", "content": question})
        with st.spinner("Pensando como estratega DOMO..."):
            answer = answer_as_domo_assistant(question, posts)
        st.session_state["assistant_chat"].append({"role": "assistant", "content": answer})
        conn = get_connection()
        add_assistant_note(conn, question, answer)
        conn.close()
        st.rerun()

    last_answer = ""
    for message in reversed(st.session_state["assistant_chat"]):
        if message["role"] == "assistant":
            last_answer = message["content"]
            break

    st.markdown("#### Convertir la respuesta en acción")
    action_cols = st.columns(5)
    with action_cols[0]:
        if st.button("Crear idea"):
            st.session_state["page"] = "Ideas"
            st.session_state["assistant_seed"] = f"Usa esta respuesta como contexto para una idea DOMO: {last_answer}"
            st.rerun()
    with action_cols[1]:
        if st.button("Hacer carrusel"):
            st.session_state["page"] = "Carruseles"
            st.session_state["carousel_seed"] = last_answer
            st.rerun()
    with action_cols[2]:
        if st.button("Post LinkedIn"):
            st.session_state["assistant_pending_prompt"] = f"Convierte esto en un post de LinkedIn con tono DOMO: {last_answer}"
            st.rerun()
    with action_cols[3]:
        if st.button("Buscar collab"):
            st.session_state["page"] = "Collabs"
            st.rerun()
    with action_cols[4]:
        if st.button("Guardar acción"):
            conn = get_connection()
            add_action_item(
                conn,
                "Acción desde copiloto DOMO",
                "Asistente",
                last_answer[:900],
                "Alta",
            )
            conn.close()
            st.success("Acción guardada.")

    st.markdown("#### Memoria reciente")
    if assistant_notes.empty:
        st.info("Aún no hay conversaciones guardadas.")
    else:
        for _, row in assistant_notes.head(5).iterrows():
            row_id = row.get("id")
            with st.expander(str(row.get("question", "Conversación"))[:90]):
                st.markdown(f"**Pregunta:** {row.get('question', '')}")
                render_ai_answer(str(row.get("answer", "")))
                st.caption(str(row.get("created_at", "")))
                if row_id and st.button("Borrar de memoria", key=f"delete_assistant_note_{row_id}"):
                    safe_delete_record("assistant_notes", int(row_id))
                    st.success("Conversación borrada.")
                    st.rerun()


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
    st.subheader("Ideas de contenido")
    st.write("Genera, guarda y mejora ideas para Reels, carruseles, LinkedIn, branding, fotografía, mockups, INHAUS y material de marca.")

    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        count = st.slider("Cantidad", min_value=3, max_value=12, value=6)
    with col_b:
        focus = st.selectbox("Objetivo", ["shares", "saves", "comentarios de calidad", "visitas al perfil", "leads"])
    with col_c:
        platform = st.selectbox("Salida", ["Instagram", "LinkedIn", "Ambas"])
    with col_d:
        territory = st.selectbox(
            "Territorio",
            [
                "Reels",
                "Carruseles",
                "LinkedIn",
                "Branding",
                "Fotografía publicitaria",
                "Mockups y material de marca",
                "INHAUS",
                "Cultura visual / Cuenca",
            ],
        )

    context_note = st.text_area(
        "Contexto opcional",
        placeholder="Ej: tengo mockups de una marca, fotos de producto, una campaña de INHAUS, behind the scenes, shots enteros...",
        height=90,
    )

    if st.button("Generar ideas", type="primary"):
        idea_focus = f"{focus}. Territorio: {territory}. Contexto DOMO: {context_note}".strip()
        new_ideas = generate_ideas(posts, focus=idea_focus, platform=platform, count=count)
        st.session_state["generated_ideas"] = new_ideas

    ideas_to_show = st.session_state.get("generated_ideas", [])
    if ideas_to_show:
        st.markdown("#### Ideas nuevas")
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

    st.markdown("#### Ideas guardadas")
    if stored_ideas.empty:
        st.info("Todavía no hay ideas guardadas.")
        return

    for _, row in stored_ideas.head(20).iterrows():
        title = row.get("title", "Idea DOMO")
        with st.expander(f"{title} · {row.get('format', 'Contenido')}"):
            with st.form(f"edit_idea_{row.get('id', title)}"):
                edit_title = st.text_input("Título", value=str(row.get("title", "")))
                cols = st.columns(3)
                edit_pillar = cols[0].selectbox(
                    "Pilar",
                    ["Así pienso yo", "Creatividad para todos", "DOMO ve el mundo"],
                    index=["Así pienso yo", "Creatividad para todos", "DOMO ve el mundo"].index(row.get("pillar", "Así pienso yo"))
                    if row.get("pillar", "Así pienso yo") in ["Así pienso yo", "Creatividad para todos", "DOMO ve el mundo"]
                    else 0,
                    key=f"pillar_{row.get('id', title)}",
                )
                edit_format = cols[1].text_input("Formato", value=str(row.get("format", "")))
                edit_priority = cols[2].selectbox(
                    "Prioridad",
                    ["Alta", "Media", "Baja"],
                    index=["Alta", "Media", "Baja"].index(row.get("priority", "Media"))
                    if row.get("priority", "Media") in ["Alta", "Media", "Baja"]
                    else 1,
                    key=f"priority_{row.get('id', title)}",
                )
                edit_hook = st.text_area("Hook / primer segundo", value=str(row.get("hook", "")), height=80)
                edit_share = st.text_area("Mecanismo de share/save", value=str(row.get("share_save_mechanism", "")), height=90)
                edit_cta = st.text_area("CTA", value=str(row.get("cta", "")), height=80)
                edit_reason = st.text_area(
                    "Observaciones y razón estratégica",
                    value=str(row.get("strategic_reason", "")),
                    height=110,
                    help="Aquí puedes ir actualizando aprendizajes sin crear otra entrada.",
                )
                edit_linkedin = st.text_area("Adaptación LinkedIn", value=str(row.get("linkedin_adaptation", "")), height=100)
                save = st.form_submit_button("Guardar cambios")

            if save and row.get("id") is not None:
                safe_update_record(
                    "content_ideas",
                    int(row["id"]),
                    {
                        "title": edit_title,
                        "pillar": edit_pillar,
                        "format": edit_format,
                        "priority": edit_priority,
                        "hook": edit_hook,
                        "share_save_mechanism": edit_share,
                        "cta": edit_cta,
                        "strategic_reason": edit_reason,
                        "linkedin_adaptation": edit_linkedin,
                    },
                )
                st.success("Idea actualizada.")
                st.rerun()

            col_car, col_link, col_delete = st.columns(3)
            with col_car:
                if st.button("Usar para carrusel", key=f"use_idea_carousel_{row.get('id', title)}"):
                    st.session_state["page"] = "Carruseles"
                    st.session_state["carousel_seed"] = f"{edit_title}\n{edit_hook}\n{edit_share}\n{edit_reason}"
                    st.rerun()
            with col_link:
                if st.button("Usar para LinkedIn", key=f"use_idea_linkedin_{row.get('id', title)}"):
                    st.session_state["page"] = "Asistente"
                    st.session_state["assistant_seed"] = f"Convierte esta idea en post de LinkedIn para DOMO:\n{edit_title}\n{edit_linkedin}\n{edit_reason}"
                    st.rerun()
            with col_delete:
                if st.button("Borrar idea", key=f"delete_idea_{row.get('id', title)}"):
                    safe_delete_record("content_ideas", int(row["id"]))
                    st.success("Idea borrada.")
                    st.rerun()


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
                if st.button("Borrar carrusel", key=f"delete_carousel_{row['id']}"):
                    safe_delete_record("carousel_drafts", int(row["id"]))
                    st.success("Carrusel borrado.")
                    st.rerun()


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
    nav_labels = {
        "Inicio": "Inicio - qué hago hoy",
        "Lectura": "Lectura - qué pegó",
        "Asistente": "Asistente - preguntar",
        "Ideas": "Ideas - crear posts",
        "Carruseles": "Carruseles - slides",
        "Capturas": "Capturas - subir métricas",
        "Trends": "Trends - radar web",
        "Inspiración": "Inspiración - links",
        "Collabs": "Collabs - marcas",
        "Dashboard": "Dashboard - gráficos",
        "Data Center": "Data Center - archivo",
        "Admin": "Admin - conexiones",
    }
    nav_help = {
        "Inicio": "Botones rápidos para decidir tu siguiente movimiento.",
        "Lectura": "La app te dice qué funcionó, qué no y qué deberías ajustar.",
        "Asistente": "Preguntas libres: estrategia, copies, ideas y lectura de decisiones.",
        "Ideas": "Banco vivo de ideas para Reels, carruseles, branding, foto, INHAUS y LinkedIn.",
        "Carruseles": "Frases por imagen, guion y texto listo para copiar a Illustrator.",
        "Capturas": "Sube screenshots de estadísticas para que el sistema aprenda.",
        "Trends": "Busca señales en la web para traducirlas a tu estilo.",
        "Inspiración": "Pega links que te gusten y conviértelos en contenido DOMO.",
        "Collabs": "Busca marcas, guarda oportunidades y redacta mensajes de acercamiento.",
        "Dashboard": "Gráficos completos de métricas y comportamiento.",
        "Data Center": "Archivo de todo lo guardado.",
        "Admin": "Conexiones: OpenAI, Supabase, Instagram y LinkedIn.",
    }
    if "page" not in st.session_state:
        st.session_state["page"] = "Inicio"
    current_page = st.session_state["page"] if st.session_state["page"] in nav_options else "Inicio"
    label_options = [nav_labels[item] for item in nav_options]
    selected_label = st.sidebar.radio(
        "Navegación",
        label_options,
        index=nav_options.index(current_page),
    )
    page = next(key for key, label in nav_labels.items() if label == selected_label)
    st.session_state["page"] = page
    st.sidebar.caption(nav_help.get(page, ""))

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
