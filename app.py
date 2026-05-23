from __future__ import annotations

import os
import json
import socket
import html
import re
from datetime import datetime, timedelta
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
        /* DOMO dark mode v2: simpler, readable, no cropped text */
        :root {{
            --md-sys-color-primary: #F3F7EA;
            --md-sys-color-on-primary: #07100D;
            --md-sys-color-primary-container: #CFFF4F;
            --md-sys-color-on-primary-container: #07100D;
            --md-sys-color-secondary: #8FE7FF;
            --md-sys-color-tertiary: #FF84D6;
            --md-sys-color-error: #FF6B7A;
            --md-sys-color-background: #070A08;
            --md-sys-color-surface: #101511;
            --md-sys-color-surface-container: #171D18;
            --md-sys-color-surface-container-high: #202720;
            --md-sys-color-outline: rgba(243,247,234,.20);
            --md-sys-color-outline-variant: rgba(243,247,234,.10);
            --md-sys-elevation-1: 0 1px 0 rgba(255,255,255,.04), 0 12px 26px rgba(0,0,0,.24);
            --md-sys-elevation-2: 0 1px 0 rgba(255,255,255,.06), 0 18px 42px rgba(0,0,0,.34);
            --md-sys-elevation-3: 0 1px 0 rgba(255,255,255,.08), 0 26px 62px rgba(0,0,0,.44);
        }}
        html, body, .stApp {{
            background:
                radial-gradient(circle at 15% 0%, rgba(207,255,79,.12), transparent 30%),
                radial-gradient(circle at 88% 4%, rgba(143,231,255,.10), transparent 28%),
                #070A08 !important;
            color: var(--md-sys-color-primary) !important;
        }}
        .block-container {{
            max-width: 1120px;
            padding-top: 1rem;
            padding-left: clamp(1rem, 3vw, 2rem);
            padding-right: clamp(1rem, 3vw, 2rem);
        }}
        h1 {{
            font-size: clamp(2rem, 4vw, 3.7rem) !important;
            line-height: 1 !important;
            color: #F6FAEF !important;
            max-width: 760px;
        }}
        h2, h3, h4, p, li, label, span, div[data-testid="stMarkdownContainer"] {{
            color: var(--md-sys-color-primary) !important;
        }}
        div[data-testid="stMarkdownContainer"] p,
        .domo-hero p,
        .domo-action p,
        .domo-launch p,
        .domo-read p {{
            color: rgba(243,247,234,.70) !important;
        }}
        [data-testid="stHeader"] {{
            background: rgba(7,10,8,.82) !important;
            border-bottom: 1px solid rgba(243,247,234,.08);
        }}
        .domo-hero {{
            background:
                linear-gradient(135deg, rgba(16,21,17,.96), rgba(23,29,24,.94)) !important;
            border: 1px solid rgba(243,247,234,.10);
            border-radius: 28px;
            padding: clamp(18px, 3vw, 28px);
            margin-bottom: 18px;
            box-shadow: var(--md-sys-elevation-2);
            overflow: hidden;
        }}
        .domo-hero:after {{
            opacity: .35;
            border-color: rgba(207,255,79,.28);
        }}
        .domo-hero h1 {{
            margin: 10px 0 12px;
        }}
        .domo-topbar {{
            margin-bottom: 10px;
        }}
        .domo-search-pill {{
            background: rgba(243,247,234,.07);
            border-color: rgba(243,247,234,.12);
            color: rgba(243,247,234,.62) !important;
            box-shadow: none;
        }}
        .domo-avatar {{
            background: #CFFF4F;
            color: #07100D !important;
        }}
        .domo-label,
        .domo-badge,
        .domo-pill,
        .domo-step-number {{
            color: #07100D !important;
            background: #CFFF4F !important;
            border: 0 !important;
            box-shadow: none !important;
        }}
        .domo-hero-grid {{
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 8px;
            margin-top: 16px;
        }}
        .domo-hero-chip {{
            color: #07100D !important;
            border: 0;
            min-height: 38px;
            display: flex;
            align-items: center;
            justify-content: center;
            white-space: normal;
        }}
        .domo-step,
        .domo-action,
        .domo-launch,
        .domo-read,
        .domo-output,
        .domo-chat-shell,
        .domo-memory-card,
        div[data-testid="stExpander"],
        [data-testid="stMetric"] {{
            background: #101511 !important;
            border: 1px solid rgba(243,247,234,.10) !important;
            border-radius: 24px !important;
            box-shadow: var(--md-sys-elevation-1) !important;
        }}
        .domo-step,
        .domo-action,
        .domo-launch {{
            min-height: auto !important;
            padding: 16px !important;
        }}
        .domo-action strong,
        .domo-launch h3,
        .domo-step h3 {{
            color: #F6FAEF !important;
            font-size: 1.02rem !important;
            line-height: 1.18 !important;
        }}
        .domo-action p,
        .domo-launch p,
        .domo-step p {{
            font-size: .92rem !important;
            line-height: 1.42 !important;
        }}
        .domo-callout {{
            background: #CFFF4F !important;
            color: #07100D !important;
            border-radius: 22px !important;
            padding: 14px 16px !important;
            box-shadow: none !important;
            border: 0 !important;
        }}
        .domo-callout * {{
            color: #07100D !important;
        }}
        input,
        textarea,
        [data-baseweb="input"] > div,
        [data-baseweb="select"] > div,
        [data-baseweb="textarea"] > div {{
            background: #151B16 !important;
            border: 1px solid rgba(243,247,234,.18) !important;
            color: #F6FAEF !important;
            border-radius: 18px !important;
            box-shadow: none !important;
        }}
        input:focus,
        textarea:focus {{
            outline: 2px solid rgba(207,255,79,.65) !important;
            outline-offset: 2px !important;
        }}
        input::placeholder,
        textarea::placeholder {{
            color: rgba(243,247,234,.45) !important;
        }}
        .stTextInput label,
        .stTextArea label,
        .stSelectbox label,
        .stSlider label,
        .stNumberInput label {{
            color: rgba(243,247,234,.76) !important;
            font-size: .9rem !important;
        }}
        .stButton > button,
        .stDownloadButton > button,
        button[kind="primary"] {{
            background: #CFFF4F !important;
            color: #07100D !important;
            border-radius: 999px !important;
            min-height: 40px !important;
            box-shadow: none !important;
            border: 0 !important;
        }}
        .stButton > button *,
        .stDownloadButton > button * {{
            color: #07100D !important;
        }}
        .stButton > button:hover,
        .stDownloadButton > button:hover {{
            background: #E0FF83 !important;
            transform: translateY(-1px) scale(1.01);
        }}
        section[data-testid="stSidebar"] {{
            background: #0B0F0C !important;
            border-right: 1px solid rgba(243,247,234,.08);
            width: 300px !important;
        }}
        section[data-testid="stSidebar"] * {{
            color: rgba(243,247,234,.84) !important;
        }}
        div[role="radiogroup"] label {{
            background: transparent !important;
            color: rgba(243,247,234,.82) !important;
            min-height: 34px !important;
            padding: 5px 8px !important;
        }}
        div[role="radiogroup"] label:hover {{
            background: rgba(207,255,79,.10) !important;
        }}
        .stTabs [data-baseweb="tab-list"] {{
            background: #101511 !important;
            border: 1px solid rgba(243,247,234,.10);
            max-width: 100%;
            overflow-x: auto;
        }}
        .stTabs [data-baseweb="tab"] {{
            color: rgba(243,247,234,.78) !important;
        }}
        .stTabs [aria-selected="true"] {{
            background: #CFFF4F !important;
            color: #07100D !important;
        }}
        div[data-testid="stDataFrame"] {{
            background: #101511 !important;
            border-color: rgba(243,247,234,.10) !important;
        }}
        [data-testid="stMetricLabel"] p {{
            color: rgba(243,247,234,.62) !important;
        }}
        [data-testid="stMetricValue"] {{
            color: #F6FAEF !important;
            font-size: clamp(1.9rem, 3vw, 3.4rem) !important;
        }}
        [data-testid="stAlert"] {{
            background: rgba(207,255,79,.12) !important;
            border: 1px solid rgba(207,255,79,.20) !important;
            color: #F6FAEF !important;
            border-radius: 20px !important;
        }}
        .domo-chat-user {{
            background: #CFFF4F !important;
            color: #07100D !important;
        }}
        .domo-chat-user * {{
            color: #07100D !important;
        }}
        .domo-chat-assistant {{
            background: #171D18 !important;
            color: #F6FAEF !important;
        }}
        a {{
            color: #8FE7FF !important;
        }}
        .domo-slide {{
            background: linear-gradient(160deg, #101511, #1E2A20 70%, #173F3E) !important;
            border-color: rgba(243,247,234,.10) !important;
            box-shadow: var(--md-sys-elevation-2) !important;
        }}
        .domo-slide-text,
        .domo-slide-detail {{
            color: #F6FAEF !important;
        }}
        .domo-slide:hover {{
            box-shadow: var(--md-sys-elevation-3) !important;
        }}
        /* Anime.js inspired layer: stagger, orbit, motion paths, elastic UI */
        @keyframes domo-orbit {{
            from {{ transform: rotate(0deg) translateX(42px) rotate(0deg); }}
            to {{ transform: rotate(360deg) translateX(42px) rotate(-360deg); }}
        }}
        @keyframes domo-orbit-rev {{
            from {{ transform: rotate(360deg) translateX(62px) rotate(-360deg); }}
            to {{ transform: rotate(0deg) translateX(62px) rotate(0deg); }}
        }}
        @keyframes domo-pulse-dot {{
            0%, 100% {{ opacity: .38; transform: scale(.78); }}
            50% {{ opacity: 1; transform: scale(1.14); }}
        }}
        @keyframes domo-draw-line {{
            from {{ stroke-dashoffset: 360; }}
            to {{ stroke-dashoffset: 0; }}
        }}
        @keyframes domo-float-shape {{
            0%, 100% {{ transform: translate3d(0,0,0) rotate(0deg); }}
            33% {{ transform: translate3d(10px,-8px,0) rotate(4deg); }}
            66% {{ transform: translate3d(-8px,6px,0) rotate(-3deg); }}
        }}
        @keyframes domo-stagger-in {{
            0% {{ opacity: 0; transform: translateY(18px) scale(.96); }}
            70% {{ opacity: 1; transform: translateY(-2px) scale(1.012); }}
            100% {{ opacity: 1; transform: translateY(0) scale(1); }}
        }}
        @keyframes domo-word-reveal {{
            0% {{ opacity: 0; transform: translateY(1.05em) rotate(2deg); filter: blur(8px); }}
            62% {{ opacity: 1; transform: translateY(-.05em) rotate(-.5deg); filter: blur(0); }}
            100% {{ opacity: 1; transform: translateY(0) rotate(0deg); filter: blur(0); }}
        }}
        @keyframes domo-scan {{
            0% {{ transform: translateX(-120%) scaleX(.35); opacity: 0; }}
            18% {{ opacity: .9; }}
            72% {{ opacity: .9; }}
            100% {{ transform: translateX(150%) scaleX(1); opacity: 0; }}
        }}
        @keyframes domo-morph-card {{
            0%, 100% {{ border-radius: 38% 62% 54% 46% / 52% 42% 58% 48%; }}
            50% {{ border-radius: 58% 42% 44% 56% / 42% 58% 42% 58%; }}
        }}
        @keyframes domo-path-travel {{
            0% {{ offset-distance: 0%; opacity: 0; }}
            12% {{ opacity: 1; }}
            88% {{ opacity: 1; }}
            100% {{ offset-distance: 100%; opacity: 0; }}
        }}
        @keyframes domo-number-pop {{
            0% {{ opacity: 0; transform: translateY(16px) scale(.72) rotate(-6deg); }}
            58% {{ opacity: 1; transform: translateY(-5px) scale(1.18) rotate(2deg); }}
            100% {{ opacity: 1; transform: translateY(0) scale(1) rotate(0deg); }}
        }}
        @keyframes domo-live-border {{
            0% {{ background-position: 0% 50%; }}
            50% {{ background-position: 100% 50%; }}
            100% {{ background-position: 0% 50%; }}
        }}
        @keyframes domo-grid-drift {{
            from {{ background-position: 0 0, 0 0; }}
            to {{ background-position: 48px 48px, -48px 48px; }}
        }}
        @keyframes domo-text-pulse {{
            0%, 100% {{ color: #F6FAEF; text-shadow: 0 0 0 rgba(207,255,79,0); }}
            50% {{ color: #CFFF4F; text-shadow: 0 0 20px rgba(207,255,79,.18); }}
        }}
        @keyframes domo-arrow-run {{
            from {{ transform: translateX(-14px); opacity: 0; }}
            35% {{ opacity: 1; }}
            to {{ transform: translateX(18px); opacity: 0; }}
        }}
        @keyframes domo-loader {{
            0% {{ transform: translateX(-100%) scaleX(.24); opacity: .25; }}
            50% {{ transform: translateX(20%) scaleX(.72); opacity: 1; }}
            100% {{ transform: translateX(180%) scaleX(.24); opacity: .25; }}
        }}
        @keyframes domo-breathe {{
            0%, 100% {{ transform: scale(1); box-shadow: 0 0 0 0 rgba(207,255,79,.38); }}
            50% {{ transform: scale(1.08); box-shadow: 0 0 0 8px rgba(207,255,79,0); }}
        }}
        @keyframes domo-count-glow {{
            0%, 100% {{ transform: translateY(0) scale(1); text-shadow: 0 0 0 rgba(207,255,79,0); }}
            50% {{ transform: translateY(-3px) scale(1.035); text-shadow: 0 0 24px rgba(207,255,79,.22); }}
        }}
        .main .block-container {{
            padding-top: clamp(1.35rem, 3vw, 2.2rem) !important;
        }}
        .stTextInput,
        .stTextArea,
        .stSelectbox,
        .stNumberInput,
        .stSlider {{
            margin-top: .55rem !important;
            margin-bottom: 1rem !important;
        }}
        .stButton > button,
        .stDownloadButton > button,
        button[kind],
        .stButton > button p,
        .stDownloadButton > button p,
        button[kind] p,
        .stButton > button span,
        .stDownloadButton > button span,
        button[kind] span {{
            color: #07100D !important;
            text-shadow: none !important;
        }}
        .domo-hero {{
            min-height: 310px;
        }}
        .domo-hero::before {{
            background:
                linear-gradient(rgba(243,247,234,.055) 1px, transparent 1px),
                linear-gradient(90deg, rgba(243,247,234,.055) 1px, transparent 1px) !important;
            background-size: 48px 48px !important;
            animation: none !important;
            opacity: .26 !important;
        }}
        .domo-hero-content {{
            position: relative;
            z-index: 2;
            max-width: 780px;
        }}
        .domo-motion-stage {{
            display: none !important;
            position: absolute;
            top: 22px;
            right: 28px;
            width: min(340px, 34vw);
            height: 250px;
            opacity: .92;
            pointer-events: none;
            z-index: 1;
        }}
        .domo-orbit-ring {{
            position: absolute;
            inset: 36px 22px 20px 68px;
            border: 1px dashed rgba(207,255,79,.22);
            border-radius: 999px;
            transform: rotate(-10deg);
        }}
        .domo-orbit-ring:nth-child(2) {{
            inset: 64px 54px 48px 34px;
            border-color: rgba(143,231,255,.20);
            transform: rotate(18deg);
        }}
        .domo-orbit-dot {{
            position: absolute;
            left: 50%;
            top: 50%;
            width: 13px;
            height: 13px;
            border-radius: 999px;
            background: #CFFF4F;
            box-shadow: 0 0 24px rgba(207,255,79,.46);
            animation: domo-orbit 5.8s linear infinite;
        }}
        .domo-orbit-dot:nth-child(4) {{
            background: #8FE7FF;
            box-shadow: 0 0 24px rgba(143,231,255,.42);
            animation: domo-orbit-rev 7.2s linear infinite;
        }}
        .domo-orbit-dot:nth-child(5) {{
            background: #FF84D6;
            box-shadow: 0 0 24px rgba(255,132,214,.42);
            animation: domo-orbit 8.4s linear infinite reverse;
        }}
        .domo-motion-svg {{
            position: absolute;
            inset: 0;
            width: 100%;
            height: 100%;
            overflow: visible;
        }}
        .domo-motion-svg path {{
            fill: none;
            stroke: rgba(243,247,234,.20);
            stroke-width: 1.5;
            stroke-dasharray: 360;
            animation: domo-draw-line 3.8s cubic-bezier(.65,0,.35,1) infinite alternate;
        }}
        .domo-motion-svg circle {{
            fill: rgba(207,255,79,.72);
            animation: domo-pulse-dot 2.4s ease-in-out infinite;
        }}
        .domo-path-dot {{
            position: absolute;
            width: 10px;
            height: 10px;
            border-radius: 999px;
            left: 0;
            top: 0;
            background: #F6FAEF;
            box-shadow: 0 0 22px rgba(246,250,239,.5);
            offset-path: path("M18 188 C86 72, 170 206, 320 48");
            animation: domo-path-travel 4.4s cubic-bezier(.65,0,.35,1) infinite;
        }}
        .domo-shape {{
            position: absolute;
            border-radius: 28px;
            border: 1px solid rgba(243,247,234,.12);
            background: rgba(243,247,234,.035);
            backdrop-filter: blur(6px);
            animation: domo-float-shape 6s ease-in-out infinite;
        }}
        .domo-shape-a {{
            width: 96px;
            height: 66px;
            right: 16px;
            bottom: 16px;
            animation-name: domo-float-shape, domo-morph-card;
            animation-duration: 6s, 7s;
            animation-timing-function: ease-in-out, ease-in-out;
            animation-iteration-count: infinite, infinite;
        }}
        .domo-shape-b {{
            width: 72px;
            height: 72px;
            right: 126px;
            top: 18px;
            border-radius: 999px;
            animation-delay: .8s;
        }}
        .domo-launch,
        .domo-action,
        .domo-step,
        .domo-read,
        [data-testid="stMetric"],
        div[data-testid="stExpander"] {{
            animation-name: domo-stagger-in !important;
            animation-duration: .55s !important;
            animation-timing-function: cubic-bezier(.34,1.56,.64,1) !important;
        }}
        .domo-launch,
        .domo-action {{
            position: relative;
            overflow: hidden;
            background:
                linear-gradient(135deg, rgba(243,247,234,.105), rgba(243,247,234,.045)),
                #101511 !important;
            border-radius: 34px !important;
            min-height: 215px !important;
            padding: 22px !important;
        }}
        .domo-launch::after,
        .domo-action::after {{
            content: "";
            position: absolute;
            inset: 0;
            padding: 1px;
            border-radius: inherit;
            background: linear-gradient(120deg, rgba(207,255,79,.75), rgba(143,231,255,.55), rgba(255,132,214,.55), rgba(207,255,79,.75));
            background-size: 260% 260%;
            opacity: 0;
            -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
            -webkit-mask-composite: xor;
            mask-composite: exclude;
            pointer-events: none;
            animation: domo-live-border 4s ease infinite;
            transition: opacity .18s ease;
        }}
        .domo-launch:hover,
        .domo-action:hover,
        .domo-step:hover,
        .domo-read:hover {{
            transform: translateY(-7px) scale(1.025) !important;
            border-color: rgba(207,255,79,.32) !important;
        }}
        .domo-launch:hover::after,
        .domo-action:hover::after {{
            opacity: 1;
        }}
        .domo-index {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 50px;
            height: 50px;
            margin: 0 0 12px;
            border-radius: 18px;
            background: #CFFF4F;
            color: #07100D !important;
            font-size: 1.45rem;
            font-weight: 950;
            letter-spacing: 0;
            box-shadow: 0 0 0 1px rgba(207,255,79,.18), 0 14px 34px rgba(207,255,79,.13);
            animation: domo-number-pop .72s cubic-bezier(.34,1.56,.64,1) both;
        }}
        .domo-index.is-blue {{
            background: #8FE7FF;
        }}
        .domo-index.is-pink {{
            background: #FF84D6;
        }}
        .domo-index.is-orange {{
            background: #FFC957;
        }}
        .domo-launch h3,
        .domo-action strong {{
            animation: domo-text-pulse 4.8s ease-in-out infinite;
            font-size: clamp(1.25rem, 2vw, 1.75rem) !important;
            line-height: 1.05 !important;
            color: #F6FAEF !important;
            display: block;
            margin-top: 18px;
        }}
        .domo-launch p::after,
        .domo-action p::after {{
            content: "  ->";
            display: inline-block;
            color: #CFFF4F;
            font-weight: 900;
            animation: domo-arrow-run 1.8s ease-in-out infinite;
        }}
        .domo-launch h3::after,
        .domo-action strong::after {{
            content: "";
            display: block;
            width: 32px;
            height: 3px;
            border-radius: 999px;
            margin-top: 10px;
            background: linear-gradient(90deg, #CFFF4F, #8FE7FF, #FF84D6);
            transform-origin: left;
            transform: scaleX(.45);
            transition: transform .24s cubic-bezier(.34,1.56,.64,1);
        }}
        .domo-launch:hover h3::after,
        .domo-action:hover strong::after {{
            transform: scaleX(1);
        }}
        .stButton > button {{
            transition: transform .18s cubic-bezier(.34,1.56,.64,1), background .18s ease !important;
        }}
        .stButton > button:active {{
            transform: translateY(1px) scale(.96) !important;
        }}
        .domo-hero-chip {{
            animation: domo-stagger-in .55s cubic-bezier(.34,1.56,.64,1) both;
        }}
        .domo-hero-chip:nth-child(2) {{ animation-delay: .06s; }}
        .domo-hero-chip:nth-child(3) {{ animation-delay: .12s; }}
        .domo-hero-chip:nth-child(4) {{ animation-delay: .18s; }}
        .domo-hero-chip:hover {{
            transform: translateY(-4px) scale(1.04) !important;
            filter: saturate(1.25);
        }}
        .domo-hero h1 .domo-word {{
            display: inline-block;
            animation: domo-word-reveal .78s cubic-bezier(.34,1.56,.64,1) both;
            transform-origin: 0 100%;
        }}
        .domo-hero h1 .domo-word:nth-child(2) {{ animation-delay: .06s; }}
        .domo-hero h1 .domo-word:nth-child(3) {{ animation-delay: .12s; }}
        .domo-hero h1 .domo-word:nth-child(4) {{ animation-delay: .18s; }}
        .domo-hero h1 .domo-word:nth-child(5) {{ animation-delay: .24s; }}
        .domo-motion-bar {{
            display: none !important;
            position: relative;
            height: 10px;
            width: min(420px, 100%);
            margin: 18px 0 0;
            overflow: hidden;
            border-radius: 999px;
            background: rgba(243,247,234,.08);
            border: 1px solid rgba(243,247,234,.10);
        }}
        .domo-motion-bar::before {{
            content: "";
            position: absolute;
            inset: 1px 0;
            width: 46%;
            border-radius: inherit;
            background: linear-gradient(90deg, #CFFF4F, #8FE7FF, #FF84D6);
            animation: domo-scan 2.8s cubic-bezier(.65,0,.35,1) infinite;
        }}
        .domo-hero-chip,
        .domo-tool-dot,
        .domo-rail-icon,
        .domo-task-pill {{
            text-decoration: none !important;
            cursor: pointer;
        }}
        .domo-tool-dot:hover,
        .domo-rail-icon:hover,
        .domo-task-pill:hover,
        .domo-schedule-day:hover,
        .domo-chip-line span:hover {{
            transform: translateY(-4px) scale(1.045);
            filter: saturate(1.28);
        }}
        .domo-task-pill,
        .domo-schedule-day,
        .domo-tool-dot,
        .domo-rail-icon,
        .domo-chip-line span {{
            transition: transform .22s cubic-bezier(.34,1.56,.64,1), filter .18s ease, box-shadow .18s ease;
        }}
        .domo-task-pill:hover {{
            box-shadow: 0 18px 42px rgba(207,255,79,.10);
        }}
        .domo-chat-shell,
        .domo-output {{
            position: relative;
            overflow: hidden;
        }}
        .domo-chat-shell::after,
        .domo-output::after {{
            content: "";
            position: absolute;
            inset: 0;
            pointer-events: none;
            background: linear-gradient(120deg, transparent 0%, rgba(207,255,79,.06) 44%, transparent 58%);
            transform: translateX(-100%);
            animation: domo-scan 5.5s ease-in-out infinite;
        }}
        [data-testid="stMetric"] [data-testid="stMetricValue"] {{
            animation: domo-count-glow 3.2s ease-in-out infinite;
        }}
        .domo-quick-note {{
            margin: 12px 0 18px;
            color: rgba(243,247,234,.62) !important;
            font-size: .9rem;
        }}
        .domo-sidebar-brand {{
            margin: 8px 0 18px;
            padding: 18px;
            border-radius: 28px;
            background: linear-gradient(145deg, rgba(207,255,79,.18), rgba(143,231,255,.08));
            border: 1px solid rgba(243,247,234,.12);
        }}
        .domo-sidebar-brand strong {{
            display: block;
            color: #F6FAEF !important;
            font-size: 1.05rem;
            line-height: 1.1;
        }}
        .domo-sidebar-brand span {{
            color: rgba(243,247,234,.62) !important;
            font-size: .78rem;
        }}
        .domo-sidebar-ai {{
            margin: 14px 0 18px;
            padding: 16px;
            border-radius: 28px;
            background: #101511;
            border: 1px solid rgba(207,255,79,.22);
            box-shadow: 0 16px 44px rgba(0,0,0,.28);
        }}
        .domo-sidebar-ai-title {{
            display: flex;
            gap: 8px;
            align-items: center;
            color: #F6FAEF !important;
            font-weight: 900;
        }}
        .domo-ai-dot {{
            width: 10px;
            height: 10px;
            border-radius: 999px;
            background: #CFFF4F;
            animation: domo-breathe 1.65s ease-in-out infinite;
        }}
        .domo-sidebar-ai p {{
            color: rgba(243,247,234,.72) !important;
            font-size: .86rem;
            line-height: 1.42;
            margin: 10px 0 0;
        }}
        .domo-sidebar-ai small {{
            display: inline-block;
            margin-top: 10px;
            color: #CFFF4F !important;
            font-weight: 900;
        }}
        div[role="radiogroup"] {{
            display: grid;
            gap: 8px;
        }}
        div[role="radiogroup"] label {{
            min-height: 38px !important;
            padding: 7px 10px !important;
            border: 1px solid rgba(243,247,234,.08) !important;
            border-radius: 999px !important;
            background: rgba(243,247,234,.035) !important;
            transition: transform .18s cubic-bezier(.34,1.56,.64,1), background .18s ease, border-color .18s ease, box-shadow .18s ease !important;
        }}
        div[role="radiogroup"] label:has(input:checked) {{
            background: rgba(207,255,79,.18) !important;
            border-color: rgba(207,255,79,.54) !important;
            box-shadow: 0 0 22px rgba(207,255,79,.10);
            transform: translateX(4px);
        }}
        div[role="radiogroup"] label:hover {{
            transform: translateX(4px) scale(1.015);
            border-color: rgba(207,255,79,.32) !important;
        }}
        .domo-wallet-calendar {{
            margin: 22px 0 26px;
            padding: 20px;
            border-radius: 34px;
            background:
                radial-gradient(circle at 12% 0%, rgba(207,255,79,.18), transparent 35%),
                #101511;
            border: 1px solid rgba(243,247,234,.12);
            box-shadow: var(--md-sys-elevation-2);
        }}
        .domo-wallet-calendar h3 {{
            margin: 0 0 16px;
            color: #F6FAEF !important;
        }}
        .domo-floating-bot {{
            position: fixed;
            right: 22px;
            top: 74px;
            z-index: 999999;
            width: min(310px, calc(100vw - 44px));
            padding: 14px 16px;
            border-radius: 28px;
            background: rgba(16,21,17,.88);
            border: 1px solid rgba(207,255,79,.26);
            box-shadow: 0 24px 70px rgba(0,0,0,.44);
            backdrop-filter: blur(18px);
            animation: domo-stagger-in .55s cubic-bezier(.34,1.56,.64,1) both;
        }}
        .domo-floating-bot strong {{
            display: flex;
            gap: 8px;
            align-items: center;
            color: #F6FAEF !important;
            font-size: .94rem;
        }}
        .domo-floating-bot p {{
            color: rgba(243,247,234,.70) !important;
            margin: 8px 0 0;
            font-size: .82rem;
            line-height: 1.35;
        }}
        .domo-floating-bot a {{
            display: inline-flex;
            margin-top: 10px;
            padding: 7px 12px;
            border-radius: 999px;
            background: #CFFF4F;
            color: #07100D !important;
            font-weight: 950;
            font-size: .78rem;
            text-decoration: none !important;
            transition: transform .18s cubic-bezier(.34,1.56,.64,1), filter .18s ease;
        }}
        .domo-floating-bot a:hover {{
            transform: translateY(-2px) scale(1.04);
            filter: saturate(1.2);
        }}
        .domo-global-copilot {{
            margin: 0 0 18px;
            padding: 16px;
            border-radius: 32px;
            background:
                radial-gradient(circle at 0% 0%, rgba(207,255,79,.22), transparent 32%),
                radial-gradient(circle at 94% 12%, rgba(56,201,232,.16), transparent 28%),
                rgba(13,17,14,.92);
            border: 1px solid rgba(243,247,234,.14);
            backdrop-filter: blur(18px);
        }}
        .domo-global-copilot-head {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            margin-bottom: 12px;
        }}
        .domo-global-copilot-title {{
            color: #F6FAEF !important;
            font-size: clamp(1.05rem, 2vw, 1.35rem);
            font-weight: 950;
            line-height: 1;
        }}
        .domo-global-copilot-tip {{
            color: rgba(243,247,234,.66) !important;
            font-size: .86rem;
            line-height: 1.35;
            margin-top: 4px;
        }}
        .domo-global-copilot .stTextInput > div > div > input {{
            min-height: 52px;
            border-radius: 999px !important;
            background: rgba(246,250,239,.96) !important;
            color: #07100D !important;
            font-weight: 850;
            padding-left: 18px !important;
        }}
        .domo-global-copilot .stButton > button {{
            min-height: 52px;
            border-radius: 999px !important;
        }}
        .domo-global-answer {{
            margin-top: 12px;
            padding: 14px 16px;
            border-radius: 24px;
            background: rgba(246,250,239,.08);
            border: 1px solid rgba(243,247,234,.12);
            color: #F6FAEF !important;
        }}
        .domo-day-row {{
            display: grid;
            grid-template-columns: repeat(7, minmax(0, 1fr));
            gap: 8px;
        }}
        .domo-day {{
            min-height: 86px;
            padding: 12px;
            border-radius: 24px;
            background: rgba(243,247,234,.055);
            border: 1px solid rgba(243,247,234,.10);
            animation: domo-stagger-in .55s cubic-bezier(.34,1.56,.64,1) both;
        }}
        .domo-day strong {{
            display: block;
            color: #F6FAEF !important;
            font-size: 1.25rem;
        }}
        .domo-day span {{
            color: rgba(243,247,234,.56) !important;
            font-size: .76rem;
        }}
        .domo-day.is-hot {{
            background: #CFFF4F;
            border-color: #CFFF4F;
        }}
        .domo-day.is-hot strong,
        .domo-day.is-hot span {{
            color: #07100D !important;
        }}
        .domo-production-board {{
            margin: 22px 0 28px;
            max-width: 1180px;
            border: 1px solid rgba(243,247,234,.12);
            border-radius: 34px;
            background: #070A08;
            box-shadow: var(--md-sys-elevation-3);
            overflow: hidden;
        }}
        .domo-board-top {{
            display: grid;
            grid-template-columns: 150px 1fr 210px;
            align-items: center;
            gap: 14px;
            padding: 20px 24px;
            border-bottom: 1px solid rgba(243,247,234,.10);
        }}
        .domo-board-brand {{
            color: #CFFF4F !important;
            font-size: 1.45rem;
            font-weight: 950;
            letter-spacing: 0;
        }}
        .domo-board-title {{
            color: #F6FAEF !important;
            font-size: clamp(1.5rem, 3vw, 2.4rem);
            font-weight: 920;
            text-align: center;
            line-height: 1;
        }}
        .domo-board-tools {{
            display: flex;
            justify-content: flex-end;
            gap: 8px;
        }}
        .domo-tool-dot {{
            width: 42px;
            height: 42px;
            border-radius: 999px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background: #F6FAEF;
            color: #07100D !important;
            font-weight: 900;
        }}
        .domo-board-grid {{
            display: grid;
            grid-template-columns: 92px minmax(0, 1fr) 320px;
            min-height: 620px;
        }}
        .domo-board-rail {{
            padding: 24px 18px;
            border-right: 1px solid rgba(243,247,234,.10);
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 16px;
            background: #070A08;
        }}
        .domo-rail-icon {{
            width: 48px;
            height: 48px;
            border-radius: 999px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background: #F6FAEF;
            color: #07100D !important;
            font-weight: 950;
            font-size: .78rem;
            box-shadow: 0 10px 28px rgba(0,0,0,.24);
            animation: domo-number-pop .62s cubic-bezier(.34,1.56,.64,1) both;
        }}
        .domo-rail-icon.is-active {{
            background: #CFFF4F;
            box-shadow: 0 0 30px rgba(207,255,79,.48);
        }}
        .domo-rail-spacer {{
            flex: 1;
        }}
        .domo-board-main {{
            padding: 24px;
            border-right: 1px solid rgba(243,247,234,.10);
        }}
        .domo-board-side {{
            padding: 24px 18px;
            background: #060806;
        }}
        .domo-stat-row {{
            display: grid;
            grid-template-columns: 1.45fr .9fr .9fr;
            gap: 16px;
            margin-bottom: 22px;
        }}
        .domo-stat-card {{
            min-height: 205px;
            border-radius: 34px;
            padding: 22px;
            background: #202320;
            border: 1px solid rgba(243,247,234,.08);
            animation: domo-stagger-in .65s cubic-bezier(.34,1.56,.64,1) both;
        }}
        .domo-stat-card.is-primary {{
            background: #CFFF4F;
        }}
        .domo-stat-card.is-light {{
            background: #F6FAEF;
        }}
        .domo-stat-card.is-primary *,
        .domo-stat-card.is-light * {{
            color: #07100D !important;
        }}
        .domo-stat-card small {{
            display: block;
            color: rgba(243,247,234,.64) !important;
            font-weight: 800;
            margin-top: 10px;
        }}
        .domo-stat-card h3 {{
            margin: 0;
            font-size: clamp(1.28rem, 2vw, 1.75rem);
            line-height: 1.08;
            color: #F6FAEF !important;
        }}
        .domo-stat-value {{
            display: block;
            margin: 28px 0 4px;
            font-size: clamp(2.2rem, 5vw, 4.8rem);
            line-height: .82;
            color: #F6FAEF !important;
            font-weight: 950;
            animation: domo-count-glow 3s ease-in-out infinite;
        }}
        .domo-schedule {{
            margin: 18px 0 26px;
        }}
        .domo-schedule-title {{
            display: flex;
            justify-content: space-between;
            gap: 12px;
            color: #F6FAEF !important;
            font-size: 1.45rem;
            font-weight: 900;
            margin-bottom: 14px;
        }}
        .domo-schedule-row {{
            display: flex;
            align-items: center;
            gap: 0;
            overflow-x: auto;
            padding-bottom: 8px;
        }}
        .domo-schedule-day {{
            min-width: 74px;
            height: 74px;
            display: inline-flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            margin-right: -6px;
            border-radius: 999px;
            background: #F6FAEF;
            color: #07100D !important;
            border: 2px solid #070A08;
            animation: domo-number-pop .68s cubic-bezier(.34,1.56,.64,1) both;
        }}
        .domo-schedule-day.is-hot {{
            min-width: 220px;
            border-radius: 999px;
            background: #CFFF4F;
        }}
        .domo-schedule-day.is-muted {{
            background: #303330;
            color: #F6FAEF !important;
        }}
        .domo-schedule-day strong,
        .domo-schedule-day span {{
            color: inherit !important;
        }}
        .domo-schedule-day strong {{
            font-size: 1.55rem;
            line-height: 1;
        }}
        .domo-schedule-day span {{
            font-size: .7rem;
            font-weight: 800;
        }}
        .domo-work-grid {{
            display: grid;
            grid-template-columns: 1fr 1.05fr;
            gap: 16px;
        }}
        .domo-worker-card,
        .domo-task-pill,
        .domo-side-card {{
            border-radius: 30px;
            padding: 18px;
            background: #1A1D1A;
            border: 1px solid rgba(243,247,234,.10);
            color: #F6FAEF !important;
            animation: domo-stagger-in .65s cubic-bezier(.34,1.56,.64,1) both;
        }}
        .domo-worker-card.is-light {{
            background: #F6FAEF;
        }}
        .domo-worker-card.is-light * {{
            color: #07100D !important;
        }}
        .domo-worker-card p,
        .domo-side-card p {{
            color: rgba(243,247,234,.72) !important;
            line-height: 1.36;
        }}
        .domo-worker-card.is-light p {{
            color: rgba(7,16,13,.72) !important;
        }}
        .domo-avatar-row {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 12px;
        }}
        .domo-mini-avatar {{
            width: 48px;
            height: 48px;
            border-radius: 999px;
            background: linear-gradient(135deg, #CFFF4F, #FF84D6);
        }}
        .domo-progress {{
            height: 22px;
            border-radius: 999px;
            margin-top: 16px;
            overflow: hidden;
            background: rgba(7,10,8,.18);
            border: 1px solid rgba(7,10,8,.20);
        }}
        .domo-progress span {{
            display: block;
            height: 100%;
            width: 70%;
            border-radius: inherit;
            background: #07100D;
        }}
        .domo-task-pill {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 14px;
            min-height: 74px;
            margin-bottom: 12px;
            border-radius: 999px;
            background: #303330;
        }}
        .domo-task-pill strong,
        .domo-task-pill span {{
            color: #F6FAEF !important;
        }}
        .domo-side-card {{
            margin-bottom: 16px;
            background: #101511;
        }}
        .domo-side-card h3 {{
            color: #F6FAEF !important;
            font-size: 1.45rem;
            line-height: 1.08;
            margin: 0 0 10px;
        }}
        .domo-side-profile {{
            display: grid;
            grid-template-columns: 48px 1fr auto;
            align-items: center;
            gap: 12px;
            margin-bottom: 18px;
        }}
        .domo-side-profile strong {{
            color: #F6FAEF !important;
            font-size: 1rem;
        }}
        .domo-side-profile span {{
            color: rgba(243,247,234,.58) !important;
            font-size: .82rem;
        }}
        .domo-side-status {{
            color: #CFFF4F !important;
            font-weight: 950;
        }}
        .domo-side-big {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 12px;
            margin: 16px 0;
        }}
        .domo-side-big strong {{
            display: block;
            color: #F6FAEF !important;
            font-size: 2rem;
            line-height: 1;
        }}
        .domo-side-big span {{
            color: rgba(243,247,234,.56) !important;
            font-size: .72rem;
        }}
        .domo-mini-calendar {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 8px;
            margin-top: 12px;
        }}
        .domo-mini-calendar span {{
            border-radius: 999px;
            min-height: 34px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background: #F6FAEF;
            color: #07100D !important;
            font-weight: 900;
        }}
        .domo-mini-calendar span.is-hot {{
            background: #CFFF4F;
        }}
        .domo-chip-line {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin: 18px 0 8px;
        }}
        .domo-chip-line span {{
            width: 50px;
            height: 20px;
            border-radius: 999px;
            background: #F6FAEF;
            display: inline-block;
        }}
        .domo-chip-line span:nth-child(2) {{
            background: #7A7E78;
        }}
        .domo-chip-line span:nth-child(3) {{
            background: #8C1DD9;
        }}
        .domo-chip-line span:nth-child(4) {{
            background: #CFFF4F;
        }}
        .domo-progress-list {{
            margin-top: 12px;
        }}
        .domo-progress-item {{
            display: grid;
            grid-template-columns: 1fr auto;
            gap: 10px;
            padding: 9px 0;
            border-bottom: 1px solid rgba(243,247,234,.08);
        }}
        .domo-progress-item strong,
        .domo-progress-item span {{
            color: rgba(243,247,234,.76) !important;
            font-size: .82rem;
        }}
        @media (max-width: 760px) {{
            .domo-day-row {{
                grid-template-columns: repeat(3, minmax(0, 1fr));
            }}
            .domo-launch,
            .domo-action {{
                min-height: auto !important;
            }}
            .domo-floating-bot {{
                position: sticky;
                top: 8px;
                width: 100%;
                margin-top: 18px;
            }}
        }}
        @media (max-width: 980px) {{
            .domo-board-top,
            .domo-board-grid,
            .domo-stat-row,
            .domo-work-grid {{
                grid-template-columns: 1fr;
            }}
            .domo-board-rail {{
                display: none;
            }}
            .domo-board-title {{
                text-align: left;
            }}
            .domo-board-main {{
                border-right: 0;
            }}
        }}
        @media (max-width: 900px) {{
            .domo-motion-stage {{
                position: relative;
                top: auto;
                right: auto;
                width: 100%;
                height: 150px;
                margin-top: 14px;
            }}
            .domo-hero {{
                min-height: auto;
            }}
        }}
        .domo-step:nth-of-type(2),
        .domo-action:nth-of-type(2),
        .domo-launch:nth-of-type(2),
        .domo-slide:nth-of-type(2) {{
            animation-delay: .05s;
        }}
        .domo-launch:nth-of-type(2) .domo-index,
        .domo-action:nth-of-type(2) .domo-index {{
            animation-delay: .08s;
        }}
        .domo-step:nth-of-type(3),
        .domo-action:nth-of-type(3),
        .domo-launch:nth-of-type(3),
        .domo-slide:nth-of-type(3) {{
            animation-delay: .1s;
        }}
        .domo-launch:nth-of-type(3) .domo-index,
        .domo-action:nth-of-type(3) .domo-index {{
            animation-delay: .16s;
        }}
        .domo-step:nth-of-type(4),
        .domo-action:nth-of-type(4),
        .domo-launch:nth-of-type(4),
        .domo-slide:nth-of-type(4) {{
            animation-delay: .15s;
        }}
        .domo-launch:nth-of-type(4) .domo-index,
        .domo-action:nth-of-type(4) .domo-index {{
            animation-delay: .24s;
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
                padding-bottom: 7rem;
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
        .domo-os-shell {{
            max-width: 1220px;
            margin: 0 auto 26px;
        }}
        .domo-os-top {{
            display: grid;
            grid-template-columns: 1fr auto;
            gap: 18px;
            align-items: center;
            margin: 8px 0 18px;
        }}
        .domo-os-kicker {{
            color: #CFFF4F !important;
            font-size: .78rem;
            font-weight: 950;
            text-transform: uppercase;
        }}
        .domo-os-title {{
            color: #F6FAEF !important;
            font-size: clamp(2.45rem, 6vw, 5.8rem);
            line-height: .88;
            font-weight: 950;
            letter-spacing: 0;
        }}
        .domo-os-status {{
            min-width: 190px;
            padding: 14px 16px;
            border-radius: 30px;
            background: rgba(243,247,234,.06);
            border: 1px solid rgba(243,247,234,.10);
            color: rgba(243,247,234,.70) !important;
        }}
        .domo-os-status strong {{
            display: block;
            color: #F6FAEF !important;
            font-size: 1.35rem;
        }}
        .domo-os-grid {{
            display: grid;
            grid-template-columns: repeat(12, minmax(0, 1fr));
            gap: 14px;
        }}
        .domo-widget {{
            display: block;
            text-decoration: none !important;
            position: relative;
            min-height: 160px;
            border-radius: 34px;
            padding: 20px;
            background: #101511;
            border: 1px solid rgba(243,247,234,.08);
            overflow: hidden;
            animation: domo-stagger-in .58s cubic-bezier(.34,1.56,.64,1) both;
            transition: transform .22s cubic-bezier(.34,1.56,.64,1), border-color .2s ease, filter .2s ease;
        }}
        .domo-widget:hover {{
            transform: translateY(-5px) scale(1.012);
            border-color: rgba(207,255,79,.30);
            filter: saturate(1.1);
        }}
        .domo-widget.lime {{
            background: #CFFF4F;
        }}
        .domo-widget.paper {{
            background: #F6FAEF;
        }}
        .domo-widget.cyan {{
            background: linear-gradient(145deg, rgba(56,201,232,.95), rgba(56,201,232,.55));
        }}
        .domo-widget.magenta {{
            background: linear-gradient(145deg, rgba(255,132,214,.92), rgba(140,29,217,.62));
        }}
        .domo-widget.orange {{
            background: linear-gradient(145deg, rgba(255,201,87,.96), rgba(244,91,105,.50));
        }}
        .domo-widget.lime *,
        .domo-widget.paper *,
        .domo-widget.cyan *,
        .domo-widget.orange * {{
            color: #07100D !important;
        }}
        .domo-widget-label {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 7px 10px;
            border-radius: 999px;
            background: rgba(243,247,234,.10);
            color: rgba(243,247,234,.78) !important;
            font-size: .78rem;
            font-weight: 900;
        }}
        .domo-widget.lime .domo-widget-label,
        .domo-widget.paper .domo-widget-label,
        .domo-widget.cyan .domo-widget-label,
        .domo-widget.orange .domo-widget-label {{
            background: rgba(7,16,13,.10);
        }}
        .domo-widget-number {{
            display: block;
            margin-top: 20px;
            color: #F6FAEF !important;
            font-size: clamp(3.2rem, 8vw, 7rem);
            line-height: .78;
            font-weight: 950;
            animation: domo-count-glow 3s ease-in-out infinite;
        }}
        .domo-widget-title {{
            margin-top: 18px;
            color: #F6FAEF !important;
            font-size: clamp(1.35rem, 2.2vw, 2.1rem);
            line-height: .98;
            font-weight: 950;
        }}
        .domo-widget-copy {{
            margin: 10px 0 0;
            color: rgba(243,247,234,.68) !important;
            font-size: .9rem;
            line-height: 1.3;
        }}
        .domo-widget-size-xl {{ grid-column: span 6; min-height: 310px; }}
        .domo-widget-size-lg {{ grid-column: span 4; min-height: 250px; }}
        .domo-widget-size-md {{ grid-column: span 3; }}
        .domo-widget-size-wide {{ grid-column: span 8; }}
        .domo-widget-size-side {{ grid-column: span 4; }}
        .domo-live-workspace {{
            max-width: 1420px;
            margin: 0 auto 26px;
        }}
        .domo-workspace-panel {{
            min-height: 620px;
            padding: 18px;
            border-radius: 34px;
            background: rgba(10,14,11,.76);
            border: 1px solid rgba(243,247,234,.10);
            backdrop-filter: blur(18px);
        }}
        .domo-workspace-label {{
            display: inline-flex;
            padding: 7px 11px;
            border-radius: 999px;
            background: rgba(207,255,79,.14);
            color: #CFFF4F !important;
            font-size: .76rem;
            font-weight: 950;
            text-transform: uppercase;
        }}
        .domo-project-card {{
            margin: 10px 0;
            padding: 14px;
            border-radius: 24px;
            background: rgba(246,250,239,.06);
            border: 1px solid rgba(243,247,234,.08);
        }}
        .domo-project-card.active {{
            border-color: rgba(207,255,79,.55);
            background: linear-gradient(145deg, rgba(207,255,79,.18), rgba(246,250,239,.05));
        }}
        .domo-project-thumb {{
            width: 42px;
            height: 42px;
            border-radius: 16px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            margin-right: 10px;
            background: #CFFF4F;
            color: #07100D !important;
            font-weight: 950;
        }}
        .domo-project-title {{
            color: #F6FAEF !important;
            font-weight: 950;
            line-height: 1.05;
            margin-top: 8px;
        }}
        .domo-project-meta {{
            color: rgba(243,247,234,.62) !important;
            font-size: .78rem;
            margin-top: 6px;
        }}
        .domo-project-score {{
            display: inline-flex;
            margin-top: 9px;
            padding: 6px 9px;
            border-radius: 999px;
            background: rgba(243,247,234,.10);
            color: #F6FAEF !important;
            font-weight: 900;
            font-size: .76rem;
        }}
        .domo-canvas-title {{
            color: #F6FAEF !important;
            font-size: clamp(1.8rem, 3vw, 3.4rem);
            line-height: .95;
            font-weight: 950;
            margin: 12px 0 8px;
        }}
        .domo-block-card {{
            margin: 12px 0;
            padding: 16px;
            border-radius: 26px;
            background: rgba(246,250,239,.07);
            border: 1px solid rgba(243,247,234,.09);
        }}
        .domo-block-card.hot {{
            background: linear-gradient(145deg, rgba(207,255,79,.20), rgba(246,250,239,.06));
            border-color: rgba(207,255,79,.26);
        }}
        .domo-block-title {{
            color: #CFFF4F !important;
            font-weight: 950;
            font-size: .82rem;
            text-transform: uppercase;
            margin-bottom: 8px;
        }}
        .domo-live-workspace textarea,
        .domo-live-workspace input {{
            border-radius: 18px !important;
        }}
        .domo-copilot-side {{
            position: sticky;
            top: 82px;
        }}
        .domo-ai-suggestion {{
            margin-top: 12px;
            padding: 14px;
            border-radius: 24px;
            background: rgba(207,255,79,.13);
            border: 1px solid rgba(207,255,79,.25);
            color: #F6FAEF !important;
        }}
        .domo-chat-home {{
            display: grid;
            grid-template-columns: minmax(0, 1.75fr) minmax(260px, .85fr);
            gap: 18px;
            max-width: 1240px;
            margin: 0 auto;
        }}
        .domo-command-panel {{
            padding: clamp(18px, 3vw, 28px);
            border-radius: 36px;
            background: linear-gradient(145deg, rgba(16,21,17,.98), rgba(8,12,9,.98));
            border: 1px solid rgba(243,247,234,.10);
            box-shadow: var(--md-sys-elevation-2);
        }}
        .domo-command-title {{
            color: #F6FAEF !important;
            font-size: clamp(2.4rem, 7vw, 5.8rem);
            line-height: .84;
            font-weight: 950;
            margin: 12px 0 14px;
        }}
        .domo-prompt-chip {{
            display: inline-flex;
            align-items: center;
            min-height: 42px;
            padding: 10px 14px;
            margin: 5px 6px 5px 0;
            border-radius: 999px;
            background: rgba(243,247,234,.08);
            border: 1px solid rgba(243,247,234,.10);
            color: #F6FAEF !important;
            font-weight: 850;
        }}
        .domo-answer-grid {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 14px;
            margin-top: 18px;
        }}
        .domo-live-card {{
            padding: 18px;
            border-radius: 30px;
            background: rgba(246,250,239,.07);
            border: 1px solid rgba(243,247,234,.10);
            min-height: 190px;
            animation: domo-enter .46s var(--domo-ease-out) both;
        }}
        .domo-live-card.lime {{
            background: linear-gradient(145deg, rgba(207,255,79,.92), rgba(207,255,79,.55));
        }}
        .domo-live-card.cyan {{
            background: linear-gradient(145deg, rgba(143,231,255,.30), rgba(246,250,239,.06));
        }}
        .domo-live-card.magenta {{
            background: linear-gradient(145deg, rgba(255,132,214,.26), rgba(246,250,239,.06));
        }}
        .domo-live-card.orange {{
            background: linear-gradient(145deg, rgba(243,168,59,.28), rgba(246,250,239,.06));
        }}
        .domo-live-card.lime,
        .domo-live-card.lime * {{
            color: #07100D !important;
        }}
        .domo-live-card-title {{
            font-size: clamp(1.35rem, 2.4vw, 2.4rem);
            line-height: .95;
            font-weight: 950;
            margin: 14px 0 10px;
            color: #F6FAEF !important;
        }}
        .domo-live-card-meta {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }}
        .domo-live-card-meta span {{
            border-radius: 999px;
            padding: 6px 9px;
            background: rgba(243,247,234,.10);
            color: inherit !important;
            font-size: .74rem;
            font-weight: 900;
        }}
        .domo-card-actions {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 8px;
            margin-top: 10px;
        }}
        .domo-side-signal {{
            position: sticky;
            top: 88px;
            padding: 18px;
            border-radius: 32px;
            background: rgba(16,21,17,.90);
            border: 1px solid rgba(243,247,234,.10);
        }}
        .domo-chat-input-wrap {{
            margin-top: 16px;
            padding: 10px;
            border-radius: 28px;
            background: rgba(243,247,234,.07);
            border: 1px solid rgba(243,247,234,.10);
        }}
        @media (max-width: 900px) {{
            .domo-chat-home {{
                grid-template-columns: 1fr;
            }}
            .domo-answer-grid {{
                grid-template-columns: 1fr;
            }}
            .domo-side-signal {{
                position: relative;
                top: 0;
            }}
        }}
        .domo-os-pills {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin: 16px 0 0;
        }}
        .domo-os-pill {{
            display: inline-flex;
            min-height: 42px;
            align-items: center;
            justify-content: center;
            padding: 10px 16px;
            border-radius: 999px;
            background: rgba(243,247,234,.08);
            color: #F6FAEF !important;
            font-weight: 900;
            text-decoration: none !important;
            border: 1px solid rgba(243,247,234,.09);
            transition: transform .2s cubic-bezier(.34,1.56,.64,1), background .2s ease;
        }}
        .domo-os-pill.is-hot {{
            background: #CFFF4F;
            color: #07100D !important;
        }}
        .domo-os-pill:hover {{
            transform: translateY(-3px) scale(1.04);
        }}
        .domo-os-calendar {{
            display: grid;
            grid-template-columns: repeat(7, minmax(0, 1fr));
            gap: 8px;
            margin-top: 16px;
        }}
        .domo-os-day {{
            min-height: 78px;
            border-radius: 24px;
            background: #F6FAEF;
            color: #07100D !important;
            display: grid;
            place-items: center;
            font-weight: 950;
            animation: domo-number-pop .7s cubic-bezier(.34,1.56,.64,1) both;
        }}
        .domo-os-day.hot {{
            background: #CFFF4F;
            box-shadow: 0 0 34px rgba(207,255,79,.22);
        }}
        .domo-os-card-list {{
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 14px;
        }}
        .domo-content-tile {{
            min-height: 220px;
            border-radius: 34px;
            padding: 18px;
            background: #101511;
            border: 1px solid rgba(243,247,234,.08);
            animation: domo-stagger-in .56s cubic-bezier(.34,1.56,.64,1) both;
        }}
        .domo-content-tile strong {{
            display: block;
            color: #F6FAEF !important;
            font-size: 1.28rem;
            line-height: 1.02;
            margin-top: 22px;
        }}
        .domo-content-tile span {{
            color: rgba(243,247,234,.62) !important;
            font-size: .8rem;
            font-weight: 900;
        }}
        .domo-bottom-nav {{
            position: fixed;
            left: 50%;
            bottom: 18px;
            transform: translateX(-50%);
            z-index: 999998;
            display: flex;
            gap: 8px;
            padding: 8px;
            border-radius: 999px;
            background: rgba(7,10,8,.78);
            border: 1px solid rgba(243,247,234,.12);
            backdrop-filter: blur(18px);
            box-shadow: 0 18px 56px rgba(0,0,0,.34);
        }}
        .domo-bottom-nav a {{
            min-width: 76px;
            min-height: 48px;
            padding: 8px 13px;
            border-radius: 999px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            color: rgba(243,247,234,.72) !important;
            text-decoration: none !important;
            font-weight: 950;
            font-size: .78rem;
        }}
        .domo-bottom-nav a.active {{
            background: #CFFF4F;
            color: #07100D !important;
        }}
        @media (max-width: 980px) {{
            section[data-testid="stSidebar"] {{
                display: none !important;
            }}
            .domo-floating-bot {{
                right: 12px;
                top: auto;
                bottom: 86px;
                width: min(300px, calc(100vw - 24px));
            }}
            .domo-os-top {{
                grid-template-columns: 1fr;
            }}
            .domo-os-grid,
            .domo-os-card-list {{
                grid-template-columns: 1fr;
            }}
            .domo-widget-size-xl,
            .domo-widget-size-lg,
            .domo-widget-size-md,
            .domo-widget-size-wide,
            .domo-widget-size-side {{
                grid-column: span 1;
            }}
            .domo-os-calendar {{
                grid-template-columns: repeat(4, minmax(0, 1fr));
            }}
            .domo-bottom-nav {{
                width: calc(100vw - 22px);
                justify-content: space-between;
                bottom: 10px;
            }}
            .domo-bottom-nav a {{
                min-width: 0;
                flex: 1;
                font-size: .72rem;
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


def get_query_value(name: str, default: str = "") -> str:
    value = st.query_params.get(name, default)
    if isinstance(value, list):
        return str(value[0]) if value else default
    return str(value or default)


def nav_url(page: str, tool: str = "") -> str:
    params = [f"page={page}"]
    if tool:
        params.append(f"tool={tool}")
    if st.session_state.get("authenticated"):
        params.append("domo_auth=ok")
    return "?" + "&".join(params)


def require_login() -> bool:
    password = get_secret("APP_PASSWORD", "")
    if not password:
        return True

    if get_query_value("domo_auth") == "ok":
        st.session_state["authenticated"] = True

    if st.session_state.get("authenticated"):
        return True

    st.markdown('<span class="domo-label">DOMO Content Lab</span>', unsafe_allow_html=True)
    st.title("Acceso privado")
    st.write("Este sistema guarda estrategia, datos y oportunidades. Entra con la clave privada.")
    attempt = st.text_input("Clave", type="password")
    if st.button("Entrar", type="primary"):
        if attempt == password:
            st.session_state["authenticated"] = True
            st.query_params["domo_auth"] = "ok"
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
            <div class="domo-hero-content">
                <div class="domo-topbar">
                    <div class="domo-search-pill">Buscar idea, marca, métrica o próximo movimiento</div>
                    <div class="domo-avatar">D</div>
                </div>
                <span class="domo-label">DOMO Content Lab</span>
                <h1>
                    <span class="domo-word">Asistente</span>
                    <span class="domo-word">de</span>
                    <span class="domo-word">crecimiento</span>
                    <span class="domo-word">visual</span>
                </h1>
                <p>
                Tu centro de decisiones para Instagram y LinkedIn: entiende qué pegó,
                qué corregir y qué contenido crear para mover shares, guardados,
                comentarios buenos, perfil y oportunidades comerciales.
                </p>
                <div class="domo-hero-grid">
                    <a class="domo-hero-chip" href="?page=Lectura" target="_self">Leer métricas</a>
                    <a class="domo-hero-chip" href="?page=Ideas" target="_self">Crear contenido</a>
                    <a class="domo-hero-chip" href="?page=Collabs" target="_self">Buscar collabs</a>
                    <a class="domo-hero-chip" href="?page=Capturas" target="_self">Guardar aprendizaje</a>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_header_actions() -> None:
    st.markdown(
        '<div class="domo-quick-note">Accesos rápidos reales: toca uno y la app te lleva directo.</div>',
        unsafe_allow_html=True,
    )
    actions = [
        ("Leer métricas", "Lectura"),
        ("Crear contenido", "Ideas"),
        ("Buscar collabs", "Collabs"),
        ("Guardar aprendizaje", "Capturas"),
    ]
    cols = st.columns(4)
    for col, (label, target) in zip(cols, actions):
        with col:
            if st.button(label, key=f"hero_go_{target}", use_container_width=True):
                st.session_state["page"] = target
                st.rerun()


def render_mobile_hint() -> None:
    db_mode = get_supabase_status()["mode"]
    st.sidebar.markdown(
        """
        <div class="domo-sidebar-brand">
            <strong>DOMO Content Lab</strong>
            <span>Asistente de crecimiento visual</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
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


def page_tip(page: str, posts: pd.DataFrame) -> str:
    reading = build_metric_reading(posts)
    tips = {
        "TODAY": f"Hoy prioriza esto: {reading['next_move']}",
        "COPILOT": "Pregúntame como estratega: objetivo, canal y material disponible.",
        "CONTENT": "Crea desde una señal: Reel para atención, carrusel para saves, LinkedIn para autoridad.",
        "METRICS": f"Lee primero esto: {reading['what_failed']}",
        "Inicio": f"Hoy prioriza esto: {reading['next_move']}",
        "Lectura": f"Lee primero la señal débil. {reading['what_failed']}",
        "Asistente": "Pregúntame como si fuera tu estratega: dame contexto, objetivo y canal.",
        "Ideas": "Pide ideas por formato: Reel, carrusel, foto, branding, mockup, INHAUS o LinkedIn.",
        "Carruseles": "Para saves, cada slide debe resolver una idea. Menos adorno, más frase copiable.",
        "Capturas": "Sube métricas de los últimos posts para que el sistema aprenda qué repetir.",
        "Trends": "Busca señales de diseño, cultura visual y marcas; luego tradúcelas a Cuenca/LATAM.",
        "Inspiración": "Pega links que te gusten. La IA debe convertir referencia en criterio DOMO.",
        "Collabs": "Busca marcas con estética compatible y guarda un mensaje con una idea concreta.",
        "Dashboard": "Mira patrones, no likes sueltos: shares, saves, comentarios y perfil.",
        "Data Center": "Limpia registros viejos y conserva lo que enseña una decisión.",
        "Admin": "Si algo falla, revisa primero OpenAI, Supabase, Instagram y LinkedIn.",
    }
    return str(tips.get(page, reading["next_move"]))


def render_sidebar_copilot(page: str, posts: pd.DataFrame) -> None:
    reading = build_metric_reading(posts)
    avg_share = safe_mean(posts, "share_rate")
    avg_save = safe_mean(posts, "save_rate")
    tip = page_tip(page, posts)
    st.sidebar.markdown(
        f"""
        <div class="domo-sidebar-ai">
            <div class="domo-sidebar-ai-title"><span class="domo-ai-dot"></span> IA activa</div>
            <p><strong>Estoy mirando:</strong> {html.escape(page)}</p>
            <p>{html.escape(tip)}</p>
            <small>Shares {as_percent(avg_share)} · Saves {as_percent(avg_save)}</small>
        </div>
        """,
        unsafe_allow_html=True,
    )
    quick_question = st.sidebar.text_area(
        "Preguntar al copiloto",
        placeholder="Ej: estoy haciendo un carrusel de branding, qué debería mejorar?",
        height=92,
        key="sidebar_copilot_question",
    )
    if st.sidebar.button("Responder con IA", key="sidebar_copilot_button", use_container_width=True):
        if quick_question.strip():
            with st.spinner("DOMO IA está pensando..."):
                try:
                    answer = answer_as_domo_assistant(quick_question, posts)
                except Exception:
                    answer = (
                        "Modo estrategia local: enfoca la pieza en una sola decisión. "
                        "Si es carrusel, cada slide debe tener una frase copiable, un ejemplo visual "
                        "y un cierre que pida guardar, comentar o escribir por DM."
                    )
            st.sidebar.markdown("#### Respuesta")
            st.sidebar.write(answer)
            conn = get_connection()
            add_assistant_note(conn, quick_question, answer)
            conn.close()
        else:
            st.sidebar.info("Escribe una pregunta rápida primero.")


def render_floating_copilot(page: str, posts: pd.DataFrame) -> None:
    tip = page_tip(page, posts)
    st.markdown(
        f"""
        <div class="domo-floating-bot">
            <strong><span class="domo-ai-dot"></span> Copiloto leyendo esta pantalla</strong>
            <p>{html.escape(tip)}</p>
            <a href="#copiloto" target="_self">Preguntar aquí</a>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_global_copilot(page: str, posts: pd.DataFrame) -> None:
    tip = page_tip(page, posts)
    if "global_copilot_answer" not in st.session_state:
        st.session_state["global_copilot_answer"] = ""

    st.markdown(
        f"""
        <div id="copiloto" class="domo-global-copilot">
            <div class="domo-global-copilot-head">
                <div>
                    <div class="domo-global-copilot-title"><span class="domo-ai-dot"></span> DOMO Copiloto</div>
                    <div class="domo-global-copilot-tip">{html.escape(tip)}</div>
                </div>
                <span class="domo-widget-label">Siempre activo</span>
            </div>
        """,
        unsafe_allow_html=True,
    )
    col_input, col_button = st.columns([5, 1.3])
    with col_input:
        prompt = st.text_input(
            "Pregunta rápida",
            placeholder="Ej: estoy armando un carrusel, qué frase lo hace más guardable?",
            label_visibility="collapsed",
            key=f"global_copilot_prompt_{page}",
        )
    with col_button:
        ask = st.button("Preguntar", key=f"global_copilot_ask_{page}", use_container_width=True)

    if ask and prompt.strip():
        with st.spinner("Copiloto leyendo esta pantalla..."):
            try:
                answer = answer_as_domo_assistant(
                    f"Estoy en la sección {page}. Responde breve, accionable y visual. No devuelvas JSON ni código. "
                    f"Si propones carrusel, escribe tarjetas claras por imagen. Pregunta: {prompt}",
                    posts,
                )
            except Exception:
                answer = (
                    "Hazlo más simple y más compartible: una idea central, una frase fuerte, "
                    "un ejemplo visual claro y un cierre que pida guardar, comentar o escribir por DM."
                )
        st.session_state["global_copilot_answer"] = answer
        conn = get_connection()
        add_assistant_note(conn, prompt, answer)
        conn.close()

    if st.session_state["global_copilot_answer"]:
        st.markdown('<div class="domo-global-answer">', unsafe_allow_html=True)
        render_ai_answer(str(st.session_state["global_copilot_answer"]))
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


def render_publish_calendar(posts: pd.DataFrame) -> None:
    today = datetime.now()
    best_days = []
    if not posts.empty and "published_at" in posts.columns:
        data = posts.copy()
        data["published_at"] = pd.to_datetime(data["published_at"], errors="coerce")
        data = with_strategic_score(data.dropna(subset=["published_at"]))
        if not data.empty:
            data["weekday"] = data["published_at"].dt.weekday
            best_days = data.groupby("weekday")["strategic_score"].mean().sort_values(ascending=False).head(2).index.tolist()
    if not best_days:
        best_days = [1, 3]

    day_names = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
    cards = []
    for offset in range(7):
        date = today + timedelta(days=offset)
        hot = date.weekday() in best_days
        label = "Publicar" if hot else "Observar"
        cards.append(
            f"""
            <div class="domo-day {'is-hot' if hot else ''}">
                <span>{day_names[date.weekday()]}</span>
                <strong>{date.day}</strong>
                <span>{label}</span>
            </div>
            """
        )
    st.markdown(
        f"""
        <div class="domo-wallet-calendar">
            <h3>Calendario inteligente</h3>
            <div class="domo-day-row">{''.join(cards)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_command_center(posts: pd.DataFrame, action_items: pd.DataFrame) -> None:
    reading = build_metric_reading(posts)
    avg_share = safe_mean(posts, "share_rate")
    avg_save = safe_mean(posts, "save_rate")
    avg_comments = safe_mean(posts, "quality_comment_rate")
    scored = with_strategic_score(posts)
    if not scored.empty and "published_at" in scored.columns:
        scored["published_at"] = pd.to_datetime(scored["published_at"], errors="coerce")
        latest = scored.sort_values("published_at", ascending=False).head(1)
    else:
        latest = scored.head(1)
    latest_title = str(latest.iloc[0].get("title", "Sin post reciente")) if not latest.empty else "Sin post reciente"
    best_format = str(reading.get("best_format", "Reel/carrusel"))
    best_pillar = str(reading.get("best_pillar", "DOMO ve el mundo"))
    today = datetime.now()
    hot_days = [1, 3]
    if not scored.empty and "published_at" in scored.columns:
        data = scored.dropna(subset=["published_at"]).copy()
        if not data.empty:
            data["weekday"] = data["published_at"].dt.weekday
            hot_days = data.groupby("weekday")["strategic_score"].mean().sort_values(ascending=False).head(2).index.tolist()

    day_names = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
    schedule_items = []
    mini_days = []
    for offset in range(7):
        date = today + timedelta(days=offset)
        is_hot = date.weekday() in hot_days
        class_name = "is-hot" if is_hot else ("is-muted" if offset < 2 else "")
        label = "Plan fuerte" if is_hot else day_names[date.weekday()]
        schedule_items.append(
            f'<div class="domo-schedule-day {class_name}"><span>{html.escape(label)}</span><strong>{date.day}</strong></div>'
        )
        mini_days.append(f'<span class="{"is-hot" if is_hot else ""}">{date.day}</span>')

    next_move = html.escape(str(reading["next_move"]))
    headline = html.escape(str(reading["headline"]))
    what_worked = html.escape(str(reading["what_worked"]))
    what_failed = html.escape(str(reading["what_failed"]))
    weak_signal = what_failed[:18]
    latest_title = html.escape(latest_title)
    best_format = html.escape(best_format)
    best_pillar = html.escape(best_pillar)

    st.markdown(
        f"""
        <div class="domo-production-board">
            <div class="domo-board-top">
                <div class="domo-board-brand">DOMO</div>
                <div class="domo-board-title">Visual Growth Planning</div>
                <div class="domo-board-tools">
                    <a class="domo-tool-dot" href="?page=Asistente" target="_self">IA</a>
                    <a class="domo-tool-dot" href="?page=Dashboard" target="_self">↗</a>
                    <a class="domo-tool-dot" href="?page=Admin" target="_self">◉</a>
                </div>
            </div>
            <div class="domo-board-grid">
                <div class="domo-board-rail">
                    <a class="domo-rail-icon is-active" href="?page=Inicio" target="_self">01</a>
                    <a class="domo-rail-icon" href="?page=Lectura" target="_self">02</a>
                    <a class="domo-rail-icon" href="?page=Asistente" target="_self">03</a>
                    <a class="domo-rail-icon" href="?page=Ideas" target="_self">04</a>
                    <a class="domo-rail-icon" href="?page=Collabs" target="_self">05</a>
                    <span class="domo-rail-spacer"></span>
                    <a class="domo-rail-icon" href="?page=Asistente" target="_self">IA</a>
                </div>
                <div class="domo-board-main">
                    <div class="domo-stat-row">
                        <div class="domo-stat-card is-primary">
                            <h3>Process Runtime</h3>
                            <span class="domo-stat-value">01</span>
                            <small>{next_move}</small>
                        </div>
                        <div class="domo-stat-card is-light">
                            <h3>Material Content</h3>
                            <span class="domo-stat-value">{best_format[:2].upper()}</span>
                            <small>{best_format}</small>
                        </div>
                        <div class="domo-stat-card">
                            <h3>Brand Signal</h3>
                            <span class="domo-stat-value">92</span>
                            <small>{best_pillar}</small>
                        </div>
                    </div>
                    <div class="domo-schedule">
                        <div class="domo-schedule-title">
                            <span>Content Runtime Schedule</span>
                            <span>Cuenca</span>
                        </div>
                        <div class="domo-schedule-row">{''.join(schedule_items)}</div>
                    </div>
                    <div class="domo-work-grid">
                        <div class="domo-worker-card is-light">
                            <div class="domo-avatar-row">
                                <span class="domo-mini-avatar"></span>
                                <div><strong>Última publicación</strong><br><span>{latest_title}</span></div>
                            </div>
                            <h3>Contenido en progreso</h3>
                            <p>{what_worked}</p>
                            <div class="domo-progress"><span></span></div>
                        </div>
                        <div>
                            <a class="domo-task-pill" href="?page=Carruseles" target="_self"><strong>Carrusel guardable</strong><span>↗</span></a>
                            <a class="domo-task-pill" href="?page=Ideas" target="_self"><strong>Reel con postura</strong><span>↗</span></a>
                            <a class="domo-task-pill" href="?page=Asistente" target="_self"><strong>LinkedIn autoridad</strong><span>↗</span></a>
                        </div>
                    </div>
                </div>
                <div class="domo-board-side">
                    <div class="domo-side-card">
                        <div class="domo-side-profile">
                            <span class="domo-mini-avatar"></span>
                            <div><strong>DOMO Copiloto</strong><br><span>Content Lab</span></div>
                            <span class="domo-side-status">Activo</span>
                        </div>
                        <h3>Visual Growth Mission</h3>
                        <div class="domo-side-big">
                            <div><strong>{as_percent(avg_share)}</strong><span>Shares</span></div>
                            <div><strong>{as_percent(avg_save)}</strong><span>Saves</span></div>
                            <div><strong>{as_percent(avg_comments)}</strong><span>Coments</span></div>
                        </div>
                        <p>{headline}</p>
                        <div class="domo-chip-line"><span></span><span></span><span></span><span></span></div>
                        <div class="domo-progress-list">
                            <div class="domo-progress-item"><strong>Diagnóstico</strong><span>Activo</span></div>
                            <div class="domo-progress-item"><strong>Punto débil</strong><span>{weak_signal}</span></div>
                            <div class="domo-progress-item"><strong>Siguiente</strong><span>Crear</span></div>
                        </div>
                    </div>
                    <div class="domo-side-card">
                        <h3>Cuándo publicar</h3>
                        <div class="domo-mini-calendar">{''.join(mini_days)}</div>
                    </div>
                    <div class="domo-side-card">
                        <h3>Siguiente pieza</h3>
                        <p>{next_move}</p>
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    launchers = [
        ("Asistente", "Copiloto", "Pregunta qué publicar, cómo vender o cómo convertir una idea."),
        ("Ideas", "Ideas", "Reels, carruseles, branding, foto, mockups, INHAUS y LinkedIn."),
        ("Carruseles", "Slides", "Frases por imagen listas para copiar."),
        ("Lectura", "Métricas", "Qué pegó, qué no y qué corregir."),
        ("Collabs", "Collabs", "Buscar marcas y preparar mensajes."),
        ("Capturas", "Data", "Subir números o screenshots."),
    ]

    st.markdown("### Herramientas rápidas")
    cols = st.columns(6)
    for index, (target, label, description) in enumerate(launchers):
        with cols[index % 6]:
            if st.button(label, key=f"go_{target}", use_container_width=True):
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
    for index, (col, item) in enumerate(zip(cols, suggested)):
        with col:
            index_class = ["", "is-blue", "is-pink", "is-orange"][index % 4]
            st.markdown(
                f"""
                <div class="domo-action">
                    <span class="domo-index {index_class}">{index + 1:02d}</span>
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
        carousel_payload = payload.get("carousel_json_shape") or payload.get("carousel") or payload.get("carousel_draft")
        if isinstance(carousel_payload, dict) and isinstance(carousel_payload.get("slides"), list):
            st.markdown("### Carrusel listo")
            if carousel_payload.get("objective"):
                st.markdown(f"**Objetivo:** {carousel_payload['objective']}")
            for slide in carousel_payload["slides"]:
                render_slide_card(slide, key_prefix=f"ai_{carousel_payload.get('title', 'carousel')}")
            if carousel_payload.get("caption"):
                st.markdown("#### Caption")
                st.write(carousel_payload["caption"])
            if carousel_payload.get("cta"):
                st.markdown("#### CTA")
                st.write(carousel_payload["cta"])
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
        if key in {"carousel_json_shape", "carousel", "carousel_draft"} and isinstance(value, dict):
            st.markdown(f"### {value.get('title', 'Carrusel DOMO')}")
            if isinstance(value.get("slides"), list):
                for slide in value["slides"]:
                    render_slide_card(slide, key_prefix=f"payload_{value.get('title', 'carousel')}")
            continue
        pretty_key = key.replace("_", " ").title()
        st.markdown(f"**{pretty_key}:**")
        if isinstance(value, (dict, list)):
            st.write(value)
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


OS_PAGES = ["TODAY", "CONTENT", "METRICS"]


def clean_text(value: object, default: str = "") -> str:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    return str(value)


def project_score(row: dict, project_type: str) -> int:
    priority = clean_text(row.get("priority"), "Media")
    score = {"Alta": 92, "Media": 74, "Baja": 52}.get(priority, 70)
    if project_type == "Carrusel":
        try:
            slides = json.loads(clean_text(row.get("slides_json"), "[]"))
        except json.JSONDecodeError:
            slides = []
        score = min(96, 72 + len(slides) * 3)
    if project_type == "Collab":
        status = clean_text(row.get("status"), "")
        score = 88 if "contact" in status.lower() else 76
    return int(score)


def project_tone(score: int) -> str:
    if score >= 88:
        return "lime"
    if score >= 76:
        return "cyan"
    if score >= 62:
        return "orange"
    return "magenta"


def build_live_projects(
    ideas: pd.DataFrame,
    carousels: pd.DataFrame,
    inspirations: pd.DataFrame,
    trends: pd.DataFrame,
    collabs: pd.DataFrame,
) -> list[dict]:
    projects: list[dict] = []
    for _, row in ideas.iterrows():
        data = row.to_dict()
        score = project_score(data, "Idea")
        projects.append(
            {
                "key": f"idea_{data.get('id')}",
                "table": "content_ideas",
                "type": clean_text(data.get("format"), "Idea"),
                "title": clean_text(data.get("title"), "Idea DOMO"),
                "status": clean_text(data.get("priority"), "Media"),
                "score": score,
                "tone": project_tone(score),
                "row": data,
            }
        )
    for _, row in carousels.iterrows():
        data = row.to_dict()
        score = project_score(data, "Carrusel")
        projects.append(
            {
                "key": f"carousel_{data.get('id')}",
                "table": "carousel_drafts",
                "type": "Carrusel",
                "title": clean_text(data.get("title"), "Carrusel DOMO"),
                "status": clean_text(data.get("objective"), "saves"),
                "score": score,
                "tone": project_tone(score),
                "row": data,
            }
        )
    for _, row in inspirations.head(8).iterrows():
        data = row.to_dict()
        projects.append(
            {
                "key": f"inspiration_{data.get('id')}",
                "table": "inspirations",
                "type": "Inspiración",
                "title": clean_text(data.get("title"), "Link guardado"),
                "status": "Radar",
                "score": 68,
                "tone": "paper",
                "row": data,
            }
        )
    for _, row in trends.head(8).iterrows():
        data = row.to_dict()
        projects.append(
            {
                "key": f"trend_{data.get('id')}",
                "table": "trend_items",
                "type": "Trend",
                "title": clean_text(data.get("title"), "Trend DOMO"),
                "status": clean_text(data.get("query"), "Web"),
                "score": 72,
                "tone": "orange",
                "row": data,
            }
        )
    for _, row in collabs.head(8).iterrows():
        data = row.to_dict()
        score = project_score(data, "Collab")
        projects.append(
            {
                "key": f"collab_{data.get('id')}",
                "table": "collab_targets",
                "type": "Collab",
                "title": clean_text(data.get("name"), "Marca"),
                "status": clean_text(data.get("status"), "Por investigar"),
                "score": score,
                "tone": project_tone(score),
                "row": data,
            }
        )
    return projects


def remember_project_version(project_key: str, label: str, before: str, after: str) -> None:
    history = st.session_state.setdefault("workspace_versions", {})
    items = history.setdefault(project_key, [])
    items.insert(
        0,
        {
            "time": datetime.now().strftime("%H:%M"),
            "label": label,
            "before": before[:260],
            "after": after[:260],
        },
    )
    history[project_key] = items[:8]


def render_project_card(project: dict, active: bool) -> None:
    tone = project.get("tone", "")
    initials = clean_text(project.get("type"), "P")[:2].upper()
    active_class = "active" if active else ""
    st.markdown(
        f"""
        <div class="domo-project-card {active_class}">
            <span class="domo-project-thumb {tone}">{html.escape(initials)}</span>
            <div class="domo-project-title">{html.escape(clean_text(project.get("title"), "Proyecto DOMO"))}</div>
            <div class="domo-project-meta">{html.escape(clean_text(project.get("type"), "Contenido"))} · {html.escape(clean_text(project.get("status"), "Activo"))}</div>
            <span class="domo-project-score">Signal {project.get("score", 70)}%</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Abrir proyecto", key=f"open_{project['key']}", use_container_width=True):
        st.session_state["active_project_key"] = project["key"]
        st.query_params["project"] = project["key"]
        st.rerun()


def render_version_history(project_key: str) -> None:
    history = st.session_state.get("workspace_versions", {}).get(project_key, [])
    if not history:
        st.caption("Aún no hay versiones en esta sesión.")
        return
    for item in history[:5]:
        st.markdown(
            f"""
            <div class="domo-ai-suggestion">
                <strong>{html.escape(item["time"])} · {html.escape(item["label"])}</strong><br>
                {html.escape(item["after"])}
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_generic_project_canvas(project: dict) -> None:
    row = project["row"]
    table = project["table"]
    item_id = row.get("id")
    title = clean_text(row.get("title") or row.get("name"), project["title"])
    st.markdown(f'<div class="domo-canvas-title">{html.escape(title)}</div>', unsafe_allow_html=True)
    with st.form(f"generic_project_{project['key']}"):
        edit_title = st.text_input("Nombre", value=title)
        notes_value = clean_text(row.get("domo_angle") or row.get("why_fit") or row.get("domo_reading") or row.get("source_notes"), "")
        notes = st.text_area("Lectura DOMO / observaciones", value=notes_value, height=150)
        extra = st.text_area(
            "Siguiente movimiento",
            value=clean_text(row.get("suggested_content") or row.get("approach"), ""),
            height=130,
        )
        saved = st.form_submit_button("Guardar proyecto")
    if saved and item_id is not None:
        if table == "inspirations":
            values = {"title": edit_title, "domo_angle": notes, "suggested_content": extra}
        elif table == "trend_items":
            values = {"title": edit_title, "domo_reading": notes}
        elif table == "collab_targets":
            values = {"name": edit_title, "why_fit": notes, "approach": extra}
        else:
            values = {"title": edit_title}
        safe_update_record(table, int(item_id), values)
        remember_project_version(project["key"], "Edición manual", title, edit_title)
        st.success("Proyecto actualizado.")
        st.rerun()


def render_idea_project_canvas(project: dict) -> None:
    row = project["row"]
    item_id = row.get("id")
    st.markdown(
        f"""
        <div class="domo-canvas-title">{html.escape(clean_text(row.get("title"), "Idea DOMO"))}</div>
        <div class="domo-chip-row">
            <span class="domo-widget-label">{html.escape(clean_text(row.get("pillar"), "Pilar"))}</span>
            <span class="domo-widget-label">{html.escape(clean_text(row.get("format"), "Formato"))}</span>
            <span class="domo-widget-label">Signal {project.get("score", 70)}%</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.form(f"idea_canvas_{project['key']}"):
        title = st.text_input("Título", value=clean_text(row.get("title"), ""))
        col_a, col_b, col_c = st.columns(3)
        pillar = col_a.selectbox(
            "Pilar",
            ["Así pienso yo", "Creatividad para todos", "DOMO ve el mundo"],
            index=["Así pienso yo", "Creatividad para todos", "DOMO ve el mundo"].index(clean_text(row.get("pillar"), "Así pienso yo"))
            if clean_text(row.get("pillar"), "Así pienso yo") in ["Así pienso yo", "Creatividad para todos", "DOMO ve el mundo"]
            else 0,
        )
        format_value = col_b.text_input("Formato", value=clean_text(row.get("format"), ""))
        priority = col_c.selectbox(
            "Prioridad",
            ["Alta", "Media", "Baja"],
            index=["Alta", "Media", "Baja"].index(clean_text(row.get("priority"), "Media"))
            if clean_text(row.get("priority"), "Media") in ["Alta", "Media", "Baja"]
            else 1,
        )
        hook = st.text_area("Hook", value=clean_text(row.get("hook"), ""), height=90)
        share = st.text_area("Mecanismo share/save", value=clean_text(row.get("share_save_mechanism"), ""), height=100)
        cta = st.text_area("CTA", value=clean_text(row.get("cta"), ""), height=85)
        reason = st.text_area("Razón / observaciones", value=clean_text(row.get("strategic_reason"), ""), height=130)
        linkedin = st.text_area("Adaptación LinkedIn", value=clean_text(row.get("linkedin_adaptation"), ""), height=110)
        saved = st.form_submit_button("Guardar cambios")
    if saved and item_id is not None:
        safe_update_record(
            "content_ideas",
            int(item_id),
            {
                "title": title,
                "pillar": pillar,
                "format": format_value,
                "priority": priority,
                "hook": hook,
                "share_save_mechanism": share,
                "cta": cta,
                "strategic_reason": reason,
                "linkedin_adaptation": linkedin,
            },
        )
        remember_project_version(project["key"], "Canvas guardado", clean_text(row.get("title"), ""), title)
        st.success("Proyecto actualizado.")
        st.rerun()


def render_carousel_project_canvas(project: dict) -> None:
    row = project["row"]
    item_id = row.get("id")
    try:
        slides = json.loads(clean_text(row.get("slides_json"), "[]"))
    except json.JSONDecodeError:
        slides = []
    st.markdown(
        f"""
        <div class="domo-canvas-title">{html.escape(clean_text(row.get("title"), "Carrusel DOMO"))}</div>
        <div class="domo-chip-row">
            <span class="domo-widget-label">Carrusel</span>
            <span class="domo-widget-label">{len(slides)} slides</span>
            <span class="domo-widget-label">Objetivo: {html.escape(clean_text(row.get("objective"), "saves"))}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.form(f"carousel_canvas_{project['key']}"):
        title = st.text_input("Título", value=clean_text(row.get("title"), ""))
        objective = st.text_input("Objetivo", value=clean_text(row.get("objective"), "saves"))
        edited_slides = []
        for index, slide in enumerate(slides, start=1):
            st.markdown(f'<div class="domo-block-title">Slide {index}</div>', unsafe_allow_html=True)
            text = st.text_area(
                f"Texto slide {index}",
                value=clean_text(slide.get("text") or slide.get("copy") or slide.get("line"), ""),
                height=80,
                key=f"slide_text_{project['key']}_{index}",
            )
            visual = st.text_input(
                f"Visual slide {index}",
                value=clean_text(slide.get("visual"), ""),
                key=f"slide_visual_{project['key']}_{index}",
            )
            edited = dict(slide)
            edited["text"] = text
            edited["visual"] = visual
            edited_slides.append(edited)
        caption = st.text_area("Caption", value=clean_text(row.get("caption"), ""), height=120)
        cta = st.text_area("CTA", value=clean_text(row.get("cta"), ""), height=80)
        saved = st.form_submit_button("Guardar carrusel")
    if saved and item_id is not None:
        safe_update_record(
            "carousel_drafts",
            int(item_id),
            {
                "title": title,
                "objective": objective,
                "slides_json": json.dumps(edited_slides, ensure_ascii=False),
                "caption": caption,
                "cta": cta,
            },
        )
        remember_project_version(project["key"], "Carrusel guardado", clean_text(row.get("title"), ""), title)
        st.success("Carrusel actualizado.")
        st.rerun()


def render_project_canvas(project: dict, posts: pd.DataFrame) -> None:
    st.markdown('<span class="domo-workspace-label">Canvas editable</span>', unsafe_allow_html=True)
    if project["table"] == "content_ideas":
        render_idea_project_canvas(project)
    elif project["table"] == "carousel_drafts":
        render_carousel_project_canvas(project)
    else:
        render_generic_project_canvas(project)
    st.markdown("#### Versiones de esta sesión")
    render_version_history(project["key"])


def get_copilot_blocks(project: dict) -> dict[str, str]:
    row = project["row"]
    if project["table"] == "content_ideas":
        return {
            "Hook": clean_text(row.get("hook"), ""),
            "CTA": clean_text(row.get("cta"), ""),
            "Share/save": clean_text(row.get("share_save_mechanism"), ""),
            "Razón": clean_text(row.get("strategic_reason"), ""),
            "LinkedIn": clean_text(row.get("linkedin_adaptation"), ""),
        }
    if project["table"] == "carousel_drafts":
        try:
            slides = json.loads(clean_text(row.get("slides_json"), "[]"))
        except json.JSONDecodeError:
            slides = []
        blocks = {
            "Caption": clean_text(row.get("caption"), ""),
            "CTA": clean_text(row.get("cta"), ""),
        }
        for index, slide in enumerate(slides, start=1):
            blocks[f"Slide {index}"] = clean_text(slide.get("text") or slide.get("copy") or slide.get("line"), "")
        return blocks
    return {
        "Lectura": clean_text(row.get("domo_angle") or row.get("why_fit") or row.get("domo_reading"), ""),
        "Siguiente": clean_text(row.get("suggested_content") or row.get("approach"), ""),
    }


def apply_copilot_block(project: dict, block: str, text: str) -> None:
    row = project["row"]
    item_id = row.get("id")
    if item_id is None:
        return
    table = project["table"]
    before = get_copilot_blocks(project).get(block, "")
    if table == "content_ideas":
        field_map = {
            "Hook": "hook",
            "CTA": "cta",
            "Share/save": "share_save_mechanism",
            "Razón": "strategic_reason",
            "LinkedIn": "linkedin_adaptation",
        }
        field = field_map.get(block)
        if field:
            safe_update_record(table, int(item_id), {field: text})
    elif table == "carousel_drafts":
        if block in {"Caption", "CTA"}:
            safe_update_record(table, int(item_id), {block.lower(): text})
        elif block.startswith("Slide "):
            try:
                slide_index = int(block.split(" ")[1]) - 1
                slides = json.loads(clean_text(row.get("slides_json"), "[]"))
            except (ValueError, json.JSONDecodeError, IndexError):
                slides = []
            if 0 <= slide_index < len(slides):
                slides[slide_index]["text"] = text
                safe_update_record(table, int(item_id), {"slides_json": json.dumps(slides, ensure_ascii=False)})
    elif table == "inspirations":
        safe_update_record(table, int(item_id), {"domo_angle": text})
    elif table == "trend_items":
        safe_update_record(table, int(item_id), {"domo_reading": text})
    elif table == "collab_targets":
        field = "approach" if block == "Siguiente" else "why_fit"
        safe_update_record(table, int(item_id), {field: text})
    remember_project_version(project["key"], f"IA editó {block}", before, text)


def render_workspace_copilot(project: dict, posts: pd.DataFrame) -> None:
    st.markdown('<span class="domo-workspace-label">Copiloto de proyecto</span>', unsafe_allow_html=True)
    st.markdown(f"### {clean_text(project.get('title'), 'Proyecto')}")
    st.caption("Edita un bloque sin borrar el resto. La IA trabaja encima de esta pieza.")
    blocks = get_copilot_blocks(project)
    block_names = list(blocks.keys()) or ["Bloque"]
    block = st.selectbox("Bloque a mejorar", block_names, key=f"copilot_block_{project['key']}")
    quick_actions = [
        "hazlo más shareable",
        "reduce texto",
        "más LATAM calle",
        "más autoridad internacional",
        "adaptar para LinkedIn",
    ]
    st.markdown('<div class="domo-chip-row">', unsafe_allow_html=True)
    action_cols = st.columns(2)
    for index, action in enumerate(quick_actions):
        with action_cols[index % 2]:
            if st.button(action.capitalize(), key=f"quick_{project['key']}_{index}", use_container_width=True):
                st.session_state[f"copilot_task_{project['key']}"] = action
    st.markdown("</div>", unsafe_allow_html=True)
    task = st.text_area(
        "Qué quieres cambiar",
        value=st.session_state.pop(f"copilot_task_{project['key']}", ""),
        placeholder="Ej: haz slide 3 más corto, más visual y más guardable",
        height=105,
        key=f"copilot_task_input_{project['key']}",
    )
    if st.button("Refinar bloque", key=f"refine_{project['key']}", type="primary", use_container_width=True):
        current = blocks.get(block, "")
        instruction = task.strip() or "mejora este bloque para que sea más claro, más visual y más guardable"
        with st.spinner("Copiloto afinando solo este bloque..."):
            try:
                suggestion = answer_as_domo_assistant(
                    "Actúa como director creativo DOMO. Edita SOLO el bloque indicado. "
                    "Devuelve únicamente el texto final del bloque, sin JSON, sin markdown largo, sin explicación. "
                    "Mantén criterio visual LATAM, calle, editorial, internacional y útil.\n\n"
                    f"Proyecto: {project['title']}\nTipo: {project['type']}\nBloque: {block}\n"
                    f"Texto actual: {current}\nInstrucción: {instruction}",
                    posts,
                )
            except Exception:
                suggestion = f"{current}\n\nAjuste DOMO: una frase más concreta, una imagen más calle y un cierre que invite a guardar o responder."
        st.session_state[f"ai_suggestion_{project['key']}"] = {"block": block, "text": suggestion}
    suggestion = st.session_state.get(f"ai_suggestion_{project['key']}")
    if suggestion:
        st.markdown(
            f"""
            <div class="domo-ai-suggestion">
                <strong>Sugerencia para {html.escape(suggestion["block"])}</strong><br>
                {html.escape(clean_text(suggestion["text"]))}
            </div>
            """,
            unsafe_allow_html=True,
        )
        col_apply, col_clear = st.columns(2)
        with col_apply:
            if st.button("Aplicar", key=f"apply_ai_{project['key']}", use_container_width=True):
                apply_copilot_block(project, suggestion["block"], clean_text(suggestion["text"]))
                st.session_state.pop(f"ai_suggestion_{project['key']}", None)
                st.success("Bloque actualizado.")
                st.rerun()
        with col_clear:
            if st.button("Descartar", key=f"clear_ai_{project['key']}", use_container_width=True):
                st.session_state.pop(f"ai_suggestion_{project['key']}", None)
                st.rerun()


def render_live_workspace(
    posts: pd.DataFrame,
    stored_ideas: pd.DataFrame,
    screenshots: pd.DataFrame,
    inspirations: pd.DataFrame,
    trends: pd.DataFrame,
    collabs: pd.DataFrame,
    carousels: pd.DataFrame,
) -> None:
    projects = build_live_projects(stored_ideas, carousels, inspirations, trends, collabs)
    query_project = get_query_value("project", "")
    if query_project:
        st.session_state["active_project_key"] = query_project
    if projects and st.session_state.get("active_project_key") not in {item["key"] for item in projects}:
        st.session_state["active_project_key"] = projects[0]["key"]
    active_key = st.session_state.get("active_project_key")
    active_project = next((item for item in projects if item["key"] == active_key), projects[0] if projects else None)

    st.markdown('<div class="domo-live-workspace">', unsafe_allow_html=True)
    left, center, right = st.columns([1.05, 2.15, 1.15], gap="medium")
    with left:
        st.markdown('<div class="domo-workspace-panel">', unsafe_allow_html=True)
        st.markdown('<span class="domo-workspace-label">Proyectos vivos</span>', unsafe_allow_html=True)
        st.caption("Abre una pieza. Edita. Pídele al copiloto cambios puntuales.")
        if not projects:
            st.info("Todavía no hay proyectos. Crea una idea o carrusel abajo.")
        for project in projects[:24]:
            render_project_card(project, project["key"] == active_key)
        st.markdown("</div>", unsafe_allow_html=True)
    with center:
        st.markdown('<div class="domo-workspace-panel">', unsafe_allow_html=True)
        if active_project:
            render_project_canvas(active_project, posts)
        else:
            st.markdown('<div class="domo-canvas-title">Crea tu primer proyecto vivo</div>', unsafe_allow_html=True)
            st.write("Genera una idea o carrusel abajo. Luego se abrirá aquí como workspace editable.")
        st.markdown("</div>", unsafe_allow_html=True)
    with right:
        st.markdown('<div class="domo-workspace-panel domo-copilot-side">', unsafe_allow_html=True)
        if active_project:
            render_workspace_copilot(active_project, posts)
        else:
            st.markdown("### Copiloto")
            st.write("Cuando abras un proyecto, aquí podrás pedir mejoras por bloque.")
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    with st.expander("Crear nuevo / herramientas de archivo"):
        tools = ["Ideas", "Carruseles", "Inspiración", "Trends", "Collabs", "Capturas"]
        section = st.radio("Abrir herramienta", tools, horizontal=True, key="content_tool_selector_live")
        if section == "Ideas":
            render_ideas(posts, stored_ideas)
        elif section == "Carruseles":
            render_carousels(posts, inspirations, carousels)
        elif section == "Inspiración":
            render_inspiration_lab(posts, inspirations)
        elif section == "Trends":
            render_trend_lab(posts, trends)
        elif section == "Collabs":
            render_collab_lab(posts, collabs)
        else:
            render_capture_lab(posts, screenshots)


def render_os_nav(current: str) -> None:
    items = [
        ("TODAY", "Chat"),
        ("CONTENT", "Workspace"),
        ("METRICS", "Pulso"),
    ]
    links = []
    for key, label in items:
        active = "active" if key == current else ""
        links.append(f'<a class="{active}" href="{nav_url(key)}" target="_self">{label}</a>')
    st.markdown(f'<nav class="domo-bottom-nav">{"".join(links)}</nav>', unsafe_allow_html=True)


def render_os_header(page: str, subtitle: str, posts: pd.DataFrame) -> None:
    status = "Live" if not posts.empty else "Ready"
    st.markdown(
        f"""
        <div class="domo-os-shell">
            <div class="domo-os-top">
                <div>
                    <div class="domo-os-kicker">DOMO Content OS / {html.escape(page)}</div>
                    <div class="domo-os-title">{html.escape(page)}</div>
                    <p class="domo-widget-copy">{html.escape(subtitle)}</p>
                </div>
                <div class="domo-os-status">
                    <span>Sistema</span>
                    <strong>{status}</strong>
                    <span>{len(posts)} señales leídas</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def os_widget(
    label: str,
    title: str,
    value: str = "",
    body: str = "",
    tone: str = "",
    size: str = "md",
    href: str | None = None,
) -> str:
    tag = "a" if href else "div"
    link = f' href="{href}" target="_self"' if href else ""
    value_html = f'<span class="domo-widget-number">{html.escape(value)}</span>' if value else ""
    body_html = f'<p class="domo-widget-copy">{html.escape(body)}</p>' if body else ""
    return (
        f'<{tag} class="domo-widget domo-widget-size-{size} {tone}"{link}>'
        f'<span class="domo-widget-label">{html.escape(label)}</span>'
        f'{value_html}'
        f'<div class="domo-widget-title">{html.escape(title)}</div>'
        f'{body_html}'
        f'</{tag}>'
    )


def ai_card_from_text(text: str, source_prompt: str = "") -> dict:
    return {
        "title": "Respuesta DOMO",
        "pillar": "Así pienso yo",
        "format": "Nota estratégica",
        "priority": "Alta",
        "hook": clean_text(text)[:420],
        "share_save_mechanism": "Convertir esta lectura en una pieza visual concreta.",
        "cta": "Guardar como proyecto y trabajar el bloque más fuerte.",
        "strategic_reason": source_prompt or "Respuesta conversacional guardable.",
        "linkedin_adaptation": "Expandir como post de criterio creativo.",
        "status": "Draft",
    }


def extract_cards_from_answer(answer: str, source_prompt: str = "") -> list[dict]:
    payload = parse_ai_payload(answer)
    cards: list[dict] = []
    if isinstance(payload, dict):
        if isinstance(payload.get("ideas"), list):
            cards.extend([item for item in payload["ideas"] if isinstance(item, dict)])
        carousel_payload = payload.get("carousel_json_shape") or payload.get("carousel") or payload.get("carousel_draft")
        if isinstance(carousel_payload, dict):
            card = dict(carousel_payload)
            card.setdefault("format", "Carrusel")
            card.setdefault("pillar", "DOMO ve el mundo")
            card.setdefault("priority", "Alta")
            cards.append(card)
        if isinstance(payload.get("slides"), list):
            card = dict(payload)
            card.setdefault("format", "Carrusel")
            card.setdefault("pillar", "DOMO ve el mundo")
            card.setdefault("priority", "Alta")
            cards.append(card)
    if not cards:
        cards = [ai_card_from_text(answer, source_prompt)]
    for index, card in enumerate(cards, start=1):
        card.setdefault("_temp_id", f"{datetime.now().timestamp()}_{index}")
        card.setdefault("status", "Draft")
    return cards


def save_card_as_project(card: dict) -> None:
    conn = get_connection()
    reason = clean_text(card.get("strategic_reason"), "")
    reference = clean_text(card.get("reference_url"), "")
    if reference:
        reason = f"{reason}\nReferencia: {reference}".strip()
    add_content_idea(
        conn,
        {
            "pillar": clean_text(card.get("pillar"), "Así pienso yo"),
            "format": clean_text(card.get("format"), "Idea"),
            "title": clean_text(card.get("title"), "Idea DOMO"),
            "hook": clean_text(card.get("hook"), ""),
            "share_save_mechanism": clean_text(card.get("share_save_mechanism"), ""),
            "cta": clean_text(card.get("cta"), ""),
            "strategic_reason": reason,
            "priority": clean_text(card.get("priority"), "Media"),
            "linkedin_adaptation": clean_text(card.get("linkedin_adaptation"), ""),
        },
    )
    conn.close()


def duplicate_home_card(index: int) -> None:
    cards = st.session_state.setdefault("home_live_cards", [])
    if 0 <= index < len(cards):
        clone = dict(cards[index])
        clone["title"] = f"{clone.get('title', 'Idea DOMO')} / variante"
        clone["_temp_id"] = f"{datetime.now().timestamp()}_{index}_copy"
        cards.insert(index + 1, clone)


def delete_home_card(index: int) -> None:
    cards = st.session_state.setdefault("home_live_cards", [])
    if 0 <= index < len(cards):
        cards.pop(index)


def find_card_index_from_command(command: str) -> int | None:
    lowered = command.lower()
    patterns = [
        r"\b(?:idea|tarjeta|card)\s+(\d+)",
        r"\b(?:la|el)\s+(\d+)\b",
        r"\b(\d+)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if match:
            return int(match.group(1)) - 1
    return None


def apply_home_command(command: str) -> bool:
    match = re.search(r"\bborra(?:r)?\s+(?:la\s+)?(\d+)", command.lower())
    if match:
        delete_home_card(int(match.group(1)) - 1)
        return True
    match = re.search(r"\b(?:duplica|duplicar)\s+(?:la\s+)?(\d+)", command.lower())
    if match:
        duplicate_home_card(int(match.group(1)) - 1)
        return True
    match = re.search(r"\b(?:descarta|descartar)\s+(?:la\s+)?(\d+)", command.lower())
    if match:
        index = int(match.group(1)) - 1
        cards = st.session_state.setdefault("home_live_cards", [])
        if 0 <= index < len(cards):
            cards[index]["status"] = "Descartada"
            return True
    match = re.search(r"\b(?:lista|ready|prepara)\s+(?:la\s+)?(\d+)", command.lower())
    if match:
        index = int(match.group(1)) - 1
        cards = st.session_state.setdefault("home_live_cards", [])
        if 0 <= index < len(cards):
            cards[index]["status"] = "Ready"
            return True
    return False


def should_refine_existing_card(command: str) -> bool:
    if not st.session_state.get("home_live_cards"):
        return False
    if find_card_index_from_command(command) is None:
        return False
    triggers = [
        "mejora", "mejorar", "hazla", "hazlo", "edita", "editar", "cambia", "cambiar",
        "mas ", "más ", "menos ", "fotograf", "calle", "ecuador", "latam", "hook",
        "cta", "copy", "visual", "linkedin", "reel", "carrusel", "remix",
    ]
    lowered = command.lower()
    return any(trigger in lowered for trigger in triggers)


def refine_existing_home_card(command: str, posts: pd.DataFrame) -> bool:
    index = find_card_index_from_command(command)
    cards = st.session_state.setdefault("home_live_cards", [])
    if index is None or index < 0 or index >= len(cards):
        return False
    original = cards[index]
    with st.spinner("Ajustando solo esa tarjeta..."):
        try:
            answer = answer_as_domo_assistant(
                "Actualiza SOLO esta tarjeta de contenido. Devuelve JSON con un objeto 'idea' y conserva lo que ya funciona. "
                "No hagas una lista nueva. Cambia únicamente lo necesario según la instrucción de DOMO. "
                "Campos: title, pillar, format, hook, share_save_mechanism, cta, strategic_reason, priority, linkedin_adaptation.\n\n"
                f"Tarjeta actual:\n{json.dumps(original, ensure_ascii=False)}\n\n"
                f"Instrucción DOMO:\n{command}",
                posts,
            )
            payload = parse_ai_payload(answer)
            refined = None
            if isinstance(payload, dict):
                if isinstance(payload.get("idea"), dict):
                    refined = payload["idea"]
                elif isinstance(payload.get("ideas"), list) and payload["ideas"]:
                    refined = payload["ideas"][0]
            if not isinstance(refined, dict):
                refined = extract_cards_from_answer(answer, command)[0]
        except Exception:
            refined = dict(original)
            refined["strategic_reason"] = (
                clean_text(original.get("strategic_reason"), "") + "\nAjuste pendiente: " + command
            ).strip()
    refined["_temp_id"] = original.get("_temp_id", f"{datetime.now().timestamp()}_{index}")
    refined["status"] = original.get("status", "Draft")
    cards[index] = {**original, **refined}
    conn = get_connection()
    add_assistant_note(conn, command, json.dumps(cards[index], ensure_ascii=False))
    conn.close()
    return True


def render_home_card(card: dict, index: int, posts: pd.DataFrame) -> None:
    tone = project_tone(project_score(card, clean_text(card.get("format"), "Idea")))
    st.markdown(
        f"""
        <div class="domo-live-card {tone}">
            <div class="domo-live-card-meta">
                <span>{html.escape(clean_text(card.get("format"), "Idea"))}</span>
                <span>{html.escape(clean_text(card.get("priority"), "Media"))}</span>
                <span>{html.escape(clean_text(card.get("status"), "Draft"))}</span>
            </div>
            <div class="domo-live-card-title">{html.escape(clean_text(card.get("title"), "Idea DOMO"))}</div>
            <p><strong>Hook:</strong> {html.escape(clean_text(card.get("hook"), ""))}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.expander("Editar esta tarjeta"):
        with st.form(f"home_card_form_{index}_{card.get('_temp_id', index)}"):
            title = st.text_input("Título", value=clean_text(card.get("title"), ""))
            col_a, col_b = st.columns(2)
            format_value = col_a.text_input("Formato", value=clean_text(card.get("format"), ""))
            priority = col_b.selectbox(
                "Estado",
                ["Draft", "Ready", "Descartada"],
                index=["Draft", "Ready", "Descartada"].index(clean_text(card.get("status"), "Draft"))
                if clean_text(card.get("status"), "Draft") in ["Draft", "Ready", "Descartada"]
                else 0,
            )
            hook = st.text_area("Hook", value=clean_text(card.get("hook"), ""), height=80)
            visual = st.text_area("Dirección visual / mecanismo", value=clean_text(card.get("share_save_mechanism"), ""), height=90)
            cta = st.text_area("CTA", value=clean_text(card.get("cta"), ""), height=70)
            reason = st.text_area("Notas / criterio", value=clean_text(card.get("strategic_reason"), ""), height=100)
            reference = st.text_input("Referencia / link", value=clean_text(card.get("reference_url"), ""))
            linkedin = st.text_area("LinkedIn", value=clean_text(card.get("linkedin_adaptation"), ""), height=80)
            saved = st.form_submit_button("Actualizar tarjeta")
        if saved:
            st.session_state["home_live_cards"][index].update(
                {
                    "title": title,
                    "format": format_value,
                    "status": priority,
                    "hook": hook,
                    "share_save_mechanism": visual,
                    "cta": cta,
                    "strategic_reason": reason,
                    "reference_url": reference,
                    "linkedin_adaptation": linkedin,
                }
            )
            st.rerun()
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button("Guardar", key=f"save_home_card_{index}", use_container_width=True):
            save_card_as_project(st.session_state["home_live_cards"][index])
            st.success("Guardado como proyecto.")
    with col_b:
        if st.button("Duplicar", key=f"duplicate_home_card_{index}", use_container_width=True):
            duplicate_home_card(index)
            st.rerun()
    with col_c:
        if st.button("Borrar", key=f"delete_home_card_{index}", use_container_width=True):
            delete_home_card(index)
            st.rerun()
    col_d, col_e, col_f, col_g = st.columns(4)
    with col_d:
        if st.button("Remix", key=f"improve_home_card_{index}", use_container_width=True):
            st.session_state["home_pending_prompt"] = (
                f"Me gusta esta idea pero mejórala sin cambiar su esencia. Hazla más visual, más DOMO, más guardable:\n"
                f"{json.dumps(st.session_state['home_live_cards'][index], ensure_ascii=False)}"
            )
            st.rerun()
    with col_e:
        if st.button("A carrusel", key=f"carousel_home_card_{index}", use_container_width=True):
            st.session_state["page"] = "CONTENT"
            st.session_state["carousel_seed"] = json.dumps(st.session_state["home_live_cards"][index], ensure_ascii=False)
            st.query_params["page"] = "CONTENT"
            st.rerun()
    with col_f:
        if st.button("A Reel", key=f"reel_home_card_{index}", use_container_width=True):
            st.session_state["home_pending_prompt"] = (
                "Convierte esta idea en un Reel de 20-35 segundos. Dame hook de 1.7 segundos, guion por tomas, texto en pantalla, "
                "gesto visual, audio sugerido y CTA. Mantén criterio DOMO, calle, Ecuador/LATAM y cero genérico:\n"
                f"{json.dumps(st.session_state['home_live_cards'][index], ensure_ascii=False)}"
            )
            st.rerun()
    with col_g:
        if st.button("A LinkedIn", key=f"linkedin_home_card_{index}", use_container_width=True):
            st.session_state["home_pending_prompt"] = (
                "Convierte esta idea en un post de LinkedIn para atraer workshops, consultoría o collabs. "
                "No devuelvas JSON, dame una versión lista para editar:\n"
                f"{json.dumps(st.session_state['home_live_cards'][index], ensure_ascii=False)}"
            )
            st.rerun()


def render_chat_home_os(
    posts: pd.DataFrame,
    stored_ideas: pd.DataFrame,
    carousels: pd.DataFrame,
    inspirations: pd.DataFrame,
    trends: pd.DataFrame,
    collabs: pd.DataFrame,
) -> None:
    reading = build_metric_reading(posts)
    if "home_live_cards" not in st.session_state:
        st.session_state["home_live_cards"] = []

    st.markdown('<div class="domo-chat-home">', unsafe_allow_html=True)
    main_col, side_col = st.columns([1.75, .85], gap="medium")
    with main_col:
        st.markdown(
            f"""
            <div class="domo-command-panel">
                <span class="domo-workspace-label">Chat creativo</span>
                <div class="domo-command-title">Habla con tu cerebro visual</div>
                <p class="domo-widget-copy">Pide ideas, borra tarjetas, mejora hooks, convierte piezas y guarda proyectos sin llenar formularios.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        quick_prompts = [
            "qué publico hoy",
            "dame ideas de fotografía",
            "quiero algo sobre lettering",
            "convierte esto en carrusel",
            "dame un Reel sobre cromática popular",
            "qué contenido repito",
        ]
        chip_cols = st.columns(3)
        for index, prompt in enumerate(quick_prompts):
            with chip_cols[index % 3]:
                if st.button(prompt, key=f"home_chip_{index}", use_container_width=True):
                    st.session_state["home_pending_prompt"] = prompt
                    st.rerun()

        default_prompt = st.session_state.pop("home_pending_prompt", "")
        st.markdown('<div class="domo-chat-input-wrap">', unsafe_allow_html=True)
        prompt = st.text_area(
            "Habla con DOMO",
            value=default_prompt,
            placeholder="Ej: me gusta esta idea pero hazla más fotográfica / borra la 3 / dame algo de branding con mockups",
            height=110,
            key="home_chat_prompt",
        )
        ask = st.button("Crear / responder", type="primary", key="home_chat_submit", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

        if ask and prompt.strip():
            if apply_home_command(prompt):
                st.success("Listo. Ajusté las tarjetas.")
                st.rerun()
            if should_refine_existing_card(prompt) and refine_existing_home_card(prompt, posts):
                st.success("Listo. Actualicé solo esa tarjeta.")
                st.rerun()
            with st.spinner("DOMO está pensando como estratega creativo..."):
                try:
                    answer = answer_as_domo_assistant(
                        "Responde como estratega creativo de DOMO. Si el usuario pide ideas, devuelve JSON con una lista 'ideas' "
                        "para que cada idea sea una tarjeta editable. Incluye: title, pillar, format, hook, share_save_mechanism, cta, "
                        "strategic_reason, priority, linkedin_adaptation. Si pide una explicación o análisis, responde breve y accionable, "
                        "sin sonar genérico. Territorios: dirección de arte, foto publicitaria, calle, diseño, branding, lettering, stencil, "
                        "cromática, Ecuador, gráfica popular LATAM, workshops y collabs.\n\n"
                        f"Pregunta DOMO: {prompt}",
                        posts,
                    )
                except Exception:
                    answer = (
                        "Hoy conviene publicar una pieza con postura clara: toma un material real de marca o foto de calle, "
                        "ponle una frase de criterio visual y cierra con una pregunta específica."
                    )
            new_cards = extract_cards_from_answer(answer, prompt)
            st.session_state["home_live_cards"] = new_cards + st.session_state["home_live_cards"]
            conn = get_connection()
            add_assistant_note(conn, prompt, answer)
            conn.close()
            st.rerun()

        cards = st.session_state.get("home_live_cards", [])
        if cards:
            st.markdown("### Tarjetas vivas")
            card_cols = st.columns(2)
            for index, card in enumerate(cards[:12]):
                with card_cols[index % 2]:
                    render_home_card(card, index, posts)
        else:
            st.markdown(
                '<div class="domo-answer-grid">'
                + os_widget("START", "Qué publico hoy", "01", "Pregunta y te devuelve tarjetas editables.", "lime", "lg")
                + os_widget("ITERAR", "No regeneres todo", "↻", "Mejora solo una tarjeta, hook o CTA.", "cyan", "lg")
                + "</div>",
                unsafe_allow_html=True,
            )

    with side_col:
        avg_share = safe_mean(posts, "share_rate")
        avg_save = safe_mean(posts, "save_rate")
        projects = build_live_projects(stored_ideas, carousels, inspirations, trends, collabs)
        st.markdown(
            f"""
            <div class="domo-side-signal">
                <span class="domo-workspace-label">Pulso</span>
                <div class="domo-widget-title">Qué está pasando</div>
                <p class="domo-widget-copy">{html.escape(str(reading["headline"]))}</p>
                <div class="domo-os-pills">
                    <span class="domo-os-pill">Shares {as_percent(avg_share)}</span>
                    <span class="domo-os-pill">Saves {as_percent(avg_save)}</span>
                    <span class="domo-os-pill">{len(projects)} proyectos</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("### Proyectos recientes")
        for project in projects[:5]:
            render_project_card(project, False)
    st.markdown("</div>", unsafe_allow_html=True)


def render_today_os(
    posts: pd.DataFrame,
    action_items: pd.DataFrame,
    stored_ideas: pd.DataFrame,
    carousels: pd.DataFrame,
    inspirations: pd.DataFrame,
    trends: pd.DataFrame,
    collabs: pd.DataFrame,
) -> None:
    render_chat_home_os(posts, stored_ideas, carousels, inspirations, trends, collabs)


def render_dashboard_cockpit(posts: pd.DataFrame, action_items: pd.DataFrame) -> None:
    reading = build_metric_reading(posts)
    avg_share = safe_mean(posts, "share_rate")
    avg_save = safe_mean(posts, "save_rate")
    avg_comments = safe_mean(posts, "quality_comment_rate")
    scored = with_strategic_score(posts)
    best_post = "Sin ganador todavía"
    if not scored.empty:
        best_post = str(scored.sort_values("strategic_score", ascending=False).iloc[0].get("title", best_post))

    weak_label = "Shares"
    weak_value = avg_share
    if avg_save < weak_value:
        weak_label = "Saves"
        weak_value = avg_save
    if avg_comments < weak_value:
        weak_label = "Comments"
        weak_value = avg_comments

    today = datetime.now()
    hot_days = [1, 3]
    if not scored.empty and "published_at" in scored.columns:
        data = scored.copy()
        data["published_at"] = pd.to_datetime(data["published_at"], errors="coerce")
        data = data.dropna(subset=["published_at"])
        if not data.empty:
            data["weekday"] = data["published_at"].dt.weekday
            hot_days = data.groupby("weekday")["strategic_score"].mean().sort_values(ascending=False).head(2).index.tolist()

    days = []
    for offset in range(7):
        date = today + timedelta(days=offset)
        hot = "hot" if date.weekday() in hot_days else ""
        days.append(f'<div class="domo-os-day {hot}">{date.day}</div>')

    st.markdown(
        f"""
        <div class="domo-os-shell">
            <div class="domo-os-grid">
                {os_widget("SIGNAL", "Movimiento de hoy", "01", str(reading["next_move"]), "lime", "xl", nav_url("CONTENT"))}
                {os_widget("BEST", "Contenido con más señal", "★", best_post, "paper", "lg", nav_url("METRICS"))}
                {os_widget("WEAK", f"{weak_label} débil", as_percent(weak_value), "La IA recomienda corregir esta señal primero.", "magenta", "lg", nav_url("METRICS"))}
                {os_widget("AI", "Preguntar al copiloto", "IA", "Qué publicar, cuándo, cómo vender o cómo convertir una idea.", "", "md", "#copiloto")}
                {os_widget("CREATE", "Reel → carrusel", "↗", "Convierte atención en guardados.", "cyan", "md", nav_url("CONTENT"))}
                {os_widget("COLLAB", "Oportunidad de marca", "09", "Busca marcas, redacta pitch y guarda seguimiento.", "orange", "md", nav_url("CONTENT"))}
                <div class="domo-widget domo-widget-size-wide">
                    <span class="domo-widget-label">TIMING</span>
                    <div class="domo-widget-title">Mejores días para publicar esta semana</div>
                    <div class="domo-os-calendar">{"".join(days)}</div>
                </div>
                {os_widget("READING", "Qué está pasando", "", str(reading["headline"]), "", "side", nav_url("METRICS"))}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_copilot_os(posts: pd.DataFrame, assistant_notes: pd.DataFrame) -> None:
    render_os_header("COPILOT", "Chat primero. Pregunta y convierte respuestas en ideas, carruseles, LinkedIn o collabs.", posts)
    prompts = [
        "Qué publico hoy con lo que ya funcionó?",
        "Convierte mi último Reel en carrusel guardable.",
        "Dame una idea de LinkedIn para atraer consultoría.",
        "Qué marca debería buscar para colaborar?",
    ]
    st.markdown(
        '<div class="domo-os-shell"><div class="domo-os-card-list">'
        + "".join(os_widget("PROMPT", prompt, "", "Toca, copia o úsalo como punto de partida.", "paper" if i % 2 else "lime", "md") for i, prompt in enumerate(prompts))
        + "</div></div>",
        unsafe_allow_html=True,
    )
    render_assistant(posts, assistant_notes)


def render_content_os(
    posts: pd.DataFrame,
    stored_ideas: pd.DataFrame,
    screenshots: pd.DataFrame,
    inspirations: pd.DataFrame,
    trends: pd.DataFrame,
    collabs: pd.DataFrame,
    carousels: pd.DataFrame,
) -> None:
    render_os_header(
        "CONTENT",
        "Workspace vivo: cada idea, carrusel, trend o collab se abre como proyecto editable con IA contextual.",
        posts,
    )
    render_live_workspace(posts, stored_ideas, screenshots, inspirations, trends, collabs, carousels)


def render_metrics_os(posts: pd.DataFrame, profile: pd.DataFrame, daily: pd.DataFrame, monetization: pd.DataFrame) -> None:
    render_os_header("METRICS", "Visual analytics: señales claras, explicación simple y siguiente acción.", posts)
    reading = build_metric_reading(posts)
    metric_widgets = [
        ("SHARES", "Share signal", as_percent(safe_mean(posts, "share_rate")), "Representación cultural. Si está bajo, falta frase/postura compartible.", "magenta"),
        ("SAVES", "Save signal", as_percent(safe_mean(posts, "save_rate")), "Valor guardable. Sube con checklists, marcos y referencias.", "lime"),
        ("COMMENTS", "Quality comments", as_percent(safe_mean(posts, "quality_comment_rate")), "Conversación útil. Necesita pregunta específica.", "cyan"),
        ("PROFILE", "Profile visits", as_percent(safe_mean(posts, "profile_visit_rate")), "Intención comercial. Necesita CTA claro.", "orange"),
    ]
    st.markdown(
        '<div class="domo-os-shell"><div class="domo-os-grid">'
        + "".join(os_widget(label, title, value, body, tone, "lg") for label, title, value, body, tone in metric_widgets)
        + os_widget("AI READ", "Qué significa", "", str(reading["headline"]), "", "wide")
        + os_widget("NEXT", "Siguiente ajuste", "→", str(reading["next_move"]), "paper", "side")
        + "</div></div>",
        unsafe_allow_html=True,
    )
    with st.expander("Ver gráficos completos"):
        render_summary(posts, profile)
        render_growth_reading(posts, profile)
        render_trends(posts, daily)
        if not monetization.empty:
            render_monetization(monetization, posts)


def main() -> None:
    inject_styles()
    if not require_login():
        return
    render_mobile_hint()
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

    nav_options = OS_PAGES
    nav_labels = {
        "TODAY": "01 CHAT",
        "CONTENT": "02 WORKSPACE",
        "METRICS": "03 PULSO",
    }
    nav_help = {
        "TODAY": "Habla, crea tarjetas vivas y decide el siguiente movimiento.",
        "CONTENT": "Workspace editable para ideas, carruseles, links, trends y collabs.",
        "METRICS": "Pulso visual: qué pegó, qué está débil y qué corregir.",
    }
    if "page" not in st.session_state:
        st.session_state["page"] = "TODAY"
    query_page = st.query_params.get("page")
    if isinstance(query_page, list):
        query_page = query_page[0] if query_page else None
    aliases = {
        "Inicio": "TODAY",
        "Lectura": "METRICS",
        "Dashboard": "METRICS",
        "Data Center": "METRICS",
        "Admin": "METRICS",
        "COPILOT": "TODAY",
        "Asistente": "TODAY",
        "Ideas": "CONTENT",
        "Carruseles": "CONTENT",
        "Capturas": "CONTENT",
        "Trends": "CONTENT",
        "Inspiración": "CONTENT",
        "Collabs": "CONTENT",
    }
    if st.session_state.get("page") in aliases:
        st.session_state["page"] = aliases[str(st.session_state["page"])]
    if query_page in aliases:
        query_page = aliases[query_page]
    if query_page in nav_options:
        st.session_state["page"] = query_page
    current_page = st.session_state["page"] if st.session_state["page"] in nav_options else "TODAY"
    label_options = [nav_labels[item] for item in nav_options]
    selected_label = st.sidebar.radio(
        "Navegación",
        label_options,
        index=nav_options.index(current_page),
    )
    page = next(key for key, label in nav_labels.items() if label == selected_label)
    st.session_state["page"] = page
    st.query_params["page"] = page
    if st.session_state.get("authenticated"):
        st.query_params["domo_auth"] = "ok"
    st.sidebar.caption(nav_help.get(page, ""))
    render_sidebar_copilot(page, posts)
    render_os_nav(page)

    if page == "TODAY":
        render_today_os(posts, action_items, stored_ideas, carousels, inspirations, trends, collabs)
    elif page == "CONTENT":
        render_content_os(posts, stored_ideas, screenshots, inspirations, trends, collabs, carousels)
    elif page == "METRICS":
        render_metrics_os(posts, profile, daily, monetization)
        with st.expander("Conexiones y archivo avanzado"):
            render_admin()
            render_data_center(posts, daily, profile, screenshots, inspirations, trends, collabs)
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
