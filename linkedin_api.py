from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import requests

from cache import get_connection, get_secret, initialize_database, upsert_post_record


LINKEDIN_REST_BASE_URL = "https://api.linkedin.com/rest"
LINKEDIN_USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
LINKEDIN_VERSION = os.getenv("LINKEDIN_VERSION", "202605")

LINKEDIN_MEMBER_METRICS = [
    "IMPRESSION",
    "MEMBERS_REACHED",
    "REACTION",
    "COMMENT",
    "RESHARE",
    "POST_SAVE",
    "POST_SEND",
    "LINK_CLICKS",
    "FOLLOWER_GAINED_FROM_CONTENT",
    "PROFILE_VIEW_FROM_CONTENT",
]

WEEKDAYS = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]


class LinkedInAPIError(Exception):
    pass


def linkedin_config() -> dict[str, str]:
    return {
        "token": get_secret("LINKEDIN_ACCESS_TOKEN", ""),
        "version": get_secret("LINKEDIN_VERSION", LINKEDIN_VERSION),
    }


def linkedin_headers(config: dict[str, str] | None = None) -> dict[str, str]:
    config = config or linkedin_config()
    return {
        "Authorization": f"Bearer {config['token']}",
        "Linkedin-Version": config["version"],
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }


def parse_linkedin_error(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"LinkedIn respondio {response.status_code}."
    message = payload.get("message") or payload.get("error_description") or payload.get("error")
    if message:
        return str(message)
    return f"LinkedIn respondio {response.status_code}."


def linkedin_rest_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    config = linkedin_config()
    if not config["token"]:
        raise LinkedInAPIError("Falta LINKEDIN_ACCESS_TOKEN.")
    response = requests.get(
        f"{LINKEDIN_REST_BASE_URL}/{path.strip('/')}",
        params=params or {},
        headers=linkedin_headers(config),
        timeout=25,
    )
    if response.ok:
        return response.json()
    raise LinkedInAPIError(parse_linkedin_error(response))


def linkedin_userinfo() -> dict[str, Any]:
    config = linkedin_config()
    if not config["token"]:
        raise LinkedInAPIError("Falta LINKEDIN_ACCESS_TOKEN.")
    response = requests.get(
        LINKEDIN_USERINFO_URL,
        headers={"Authorization": f"Bearer {config['token']}"},
        timeout=20,
    )
    if response.ok:
        return response.json()
    raise LinkedInAPIError(parse_linkedin_error(response))


def get_metric_type(item: dict[str, Any], fallback: str) -> str:
    value = item.get("metricType", fallback)
    if isinstance(value, dict):
        return str(next(iter(value.values()), fallback))
    return str(value or fallback)


def metric_total(payload: dict[str, Any], metric: str) -> int:
    total = 0
    for item in payload.get("elements", []):
        if get_metric_type(item, metric) == metric:
            total += int(item.get("count") or 0)
    return total


def fetch_member_metric(metric: str) -> int:
    payload = linkedin_rest_get(
        "memberCreatorPostAnalytics",
        {"q": "me", "queryType": metric, "aggregation": "TOTAL"},
    )
    return metric_total(payload, metric)


def fetch_member_analytics() -> tuple[dict[str, int], list[str]]:
    analytics: dict[str, int] = {}
    unsupported: list[str] = []
    for metric in LINKEDIN_MEMBER_METRICS:
        try:
            analytics[metric] = fetch_member_metric(metric)
        except LinkedInAPIError:
            unsupported.append(metric)
    return analytics, unsupported


def get_linkedin_status(check_api: bool = False) -> dict[str, Any]:
    config = linkedin_config()
    status: dict[str, Any] = {
        "token": "Lista" if config["token"] else "Falta LINKEDIN_ACCESS_TOKEN",
        "version": config["version"],
        "api": "No probado",
        "profile": {},
        "message": "Pega token de LinkedIn en Streamlit Secrets.",
        "ready": False,
    }
    if not config["token"]:
        return status

    if not check_api:
        status["message"] = "Token presente. Prueba la conexion para confirmar permisos."
        return status

    try:
        profile = linkedin_userinfo()
    except LinkedInAPIError:
        profile = {}

    try:
        test_value = fetch_member_metric("IMPRESSION")
    except LinkedInAPIError as exc:
        status["api"] = "Sin permiso de metricas"
        status["profile"] = profile
        status["message"] = (
            "LinkedIn recibio el token, pero no dejo leer metricas. "
            "Necesita el permiso r_member_postAnalytics / Community Management API. "
            f"Detalle: {exc}"
        )
        return status

    status["api"] = "Lista"
    status["profile"] = profile
    status["message"] = f"LinkedIn conectado. Impresiones detectadas: {test_value}."
    status["ready"] = True
    return status


def analytics_to_post_record(analytics: dict[str, int], profile: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now()
    impressions = int(analytics.get("IMPRESSION") or 0)
    reached = int(analytics.get("MEMBERS_REACHED") or 0)
    comments = int(analytics.get("COMMENT") or 0)
    name = profile.get("name") or "DOMO"
    reach = max(reached or impressions, 1)
    return {
        "external_id": f"linkedin-member-snapshot-{now.date().isoformat()}",
        "permalink": "",
        "date": now.date().isoformat(),
        "platform": "LinkedIn",
        "title": f"LinkedIn snapshot - {name}",
        "pillar": "Asi pienso yo",
        "format": "Lectura API",
        "weekday": WEEKDAYS[now.weekday()],
        "hour": int(now.hour),
        "reach": reach,
        "likes": int(analytics.get("REACTION") or 0),
        "comments": comments,
        "quality_comments": int(round(comments * 0.55)),
        "shares": int(analytics.get("RESHARE") or 0),
        "saves": int(analytics.get("POST_SAVE") or 0),
        "profile_visits": int(analytics.get("PROFILE_VIEW_FROM_CONTENT") or 0),
        "website_clicks": int(analytics.get("LINK_CLICKS") or 0),
    }


def refresh_linkedin_to_cache() -> dict[str, Any]:
    initialize_database()
    try:
        profile = linkedin_userinfo()
    except LinkedInAPIError:
        profile = {}
    analytics, unsupported = fetch_member_analytics()
    if not analytics:
        raise LinkedInAPIError(
            "El token existe, pero LinkedIn no entrego metricas. Revisa permisos de Community Management API."
        )

    conn = get_connection()
    try:
        upsert_post_record(conn, analytics_to_post_record(analytics, profile))
    finally:
        conn.close()

    return {
        "message": "LinkedIn actualizado: snapshot de metricas guardado.",
        "analytics": analytics,
        "unsupported_metrics": unsupported,
    }
