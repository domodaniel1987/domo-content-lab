from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import requests

from cache import get_connection, get_secret, initialize_database, upsert_post_record


GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v24.0")
GRAPH_BASE_URL = f"https://graph.facebook.com/{GRAPH_VERSION}"

MEDIA_FIELDS = ",".join(
    [
        "id",
        "caption",
        "media_type",
        "media_product_type",
        "timestamp",
        "permalink",
        "like_count",
        "comments_count",
    ]
)

MEDIA_INSIGHT_METRICS = [
    "reach",
    "saved",
    "shares",
    "likes",
    "comments",
    "total_interactions",
    "profile_activity",
    "profile_visits",
    "follows",
    "views",
    "plays",
    "impressions",
]

WEEKDAYS = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]


class InstagramAPIError(Exception):
    pass


def instagram_config() -> dict[str, str]:
    return {
        "token": get_secret("INSTAGRAM_ACCESS_TOKEN", ""),
        "business_account_id": get_secret("INSTAGRAM_BUSINESS_ACCOUNT_ID", ""),
    }


def get_instagram_status(check_api: bool = False) -> dict[str, Any]:
    config = instagram_config()
    status: dict[str, Any] = {
        "token": "Lista" if config["token"] else "Falta INSTAGRAM_ACCESS_TOKEN",
        "business_account_id": "Lista" if config["business_account_id"] else "Falta INSTAGRAM_BUSINESS_ACCOUNT_ID",
        "api": "No probado",
        "account": {},
        "message": "Pega token e Instagram Business Account ID en Streamlit Secrets.",
        "ready": False,
    }
    if not config["token"] or not config["business_account_id"]:
        return status

    if not check_api:
        status["message"] = "Credenciales presentes. Prueba la conexion o actualiza metricas."
        return status

    try:
        account = graph_get(
            config["business_account_id"],
            {
                "fields": "id,username,followers_count,media_count",
            },
        )
    except InstagramAPIError as exc:
        status["api"] = "Error"
        status["message"] = str(exc)
        return status

    status["api"] = "Lista"
    status["account"] = account
    status["message"] = f"Conectado a @{account.get('username', 'instagram')}."
    status["ready"] = True
    return status


def graph_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    config = instagram_config()
    if not config["token"]:
        raise InstagramAPIError("Falta INSTAGRAM_ACCESS_TOKEN.")

    clean_path = path.strip("/")
    final_params = dict(params or {})
    final_params["access_token"] = config["token"]
    response = requests.get(
        f"{GRAPH_BASE_URL}/{clean_path}",
        params=final_params,
        timeout=20,
        headers={"User-Agent": "DOMOContentLab/1.0"},
    )
    if response.ok:
        return response.json()

    try:
        payload = response.json()
    except ValueError:
        payload = {}
    error = payload.get("error", {})
    message = error.get("message") or f"Instagram API respondio {response.status_code}."
    raise InstagramAPIError(message)


def fetch_instagram_media(limit: int = 20) -> list[dict[str, Any]]:
    account_id = instagram_config()["business_account_id"]
    if not account_id:
        raise InstagramAPIError("Falta INSTAGRAM_BUSINESS_ACCOUNT_ID.")
    payload = graph_get(
        f"{account_id}/media",
        {
            "fields": MEDIA_FIELDS,
            "limit": max(1, min(int(limit), 50)),
        },
    )
    return payload.get("data", [])


def extract_metric_value(item: dict[str, Any]) -> int:
    if "total_value" in item and isinstance(item["total_value"], dict):
        return int(item["total_value"].get("value") or 0)
    values = item.get("values") or []
    if values:
        return int(values[-1].get("value") or 0)
    return 0


def fetch_media_insights(media_id: str) -> tuple[dict[str, int], list[str]]:
    insights: dict[str, int] = {}
    unsupported: list[str] = []
    for metric in MEDIA_INSIGHT_METRICS:
        try:
            payload = graph_get(f"{media_id}/insights", {"metric": metric})
        except InstagramAPIError:
            unsupported.append(metric)
            continue
        for item in payload.get("data", []):
            name = item.get("name", metric)
            insights[name] = extract_metric_value(item)
    return insights, unsupported


def clean_title(caption: str, media_id: str) -> str:
    caption = (caption or "").strip()
    if caption:
        first_line = caption.splitlines()[0].strip()
        return first_line[:90] or f"Post Instagram {media_id[-6:]}"
    return f"Post Instagram {media_id[-6:]}"


def infer_format(media: dict[str, Any]) -> str:
    product = (media.get("media_product_type") or "").upper()
    media_type = (media.get("media_type") or "").upper()
    if product == "REELS":
        return "Reel"
    if media_type == "CAROUSEL_ALBUM":
        return "Carrusel"
    if media_type == "VIDEO":
        return "Video"
    if media_type == "IMAGE":
        return "Imagen"
    return product.title() or media_type.title() or "Post"


def infer_pillar(caption: str) -> str:
    text = (caption or "").lower()
    if any(word in text for word in ["cuenca", "calle", "rotulo", "rótulo", "latam", "barrio", "popular"]):
        return "DOMO ve el mundo"
    if any(word in text for word in ["aprende", "checklist", "guarda", "paso", "como ", "cómo "]):
        return "Creatividad para todos"
    return "Asi pienso yo"


def parse_timestamp(value: str) -> datetime:
    clean = (value or "").replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(clean)
    except ValueError:
        return datetime.now()


def media_to_post_record(media: dict[str, Any], insights: dict[str, int]) -> dict[str, Any]:
    timestamp = parse_timestamp(media.get("timestamp", ""))
    reach = int(insights.get("reach") or insights.get("views") or insights.get("plays") or insights.get("impressions") or 1)
    likes = int(media.get("like_count") or insights.get("likes") or 0)
    comments = int(media.get("comments_count") or insights.get("comments") or 0)
    caption = media.get("caption") or ""

    return {
        "external_id": str(media.get("id", "")),
        "permalink": media.get("permalink", ""),
        "date": timestamp.date().isoformat(),
        "platform": "Instagram",
        "title": clean_title(caption, str(media.get("id", ""))),
        "pillar": infer_pillar(caption),
        "format": infer_format(media),
        "weekday": WEEKDAYS[timestamp.weekday()],
        "hour": int(timestamp.hour),
        "reach": reach,
        "likes": likes,
        "comments": comments,
        "quality_comments": int(round(comments * 0.35)),
        "shares": int(insights.get("shares") or 0),
        "saves": int(insights.get("saved") or insights.get("saves") or 0),
        "profile_visits": int(insights.get("profile_visits") or insights.get("profile_activity") or 0),
        "website_clicks": 0,
    }


def refresh_instagram_to_cache(limit: int = 20) -> dict[str, Any]:
    initialize_database()
    media_items = fetch_instagram_media(limit=limit)
    conn = get_connection()
    imported = 0
    unsupported_metrics: set[str] = set()
    try:
        for media in media_items:
            insights, unsupported = fetch_media_insights(str(media["id"]))
            unsupported_metrics.update(unsupported)
            upsert_post_record(conn, media_to_post_record(media, insights))
            imported += 1
    finally:
        conn.close()

    return {
        "imported": imported,
        "unsupported_metrics": sorted(unsupported_metrics),
        "message": f"Instagram actualizado: {imported} posts leidos y guardados.",
    }
