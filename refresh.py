from __future__ import annotations

import os
from datetime import datetime

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> bool:
        return False

from cache import get_connection, initialize_database
from instagram_api import InstagramAPIError, refresh_instagram_to_cache
from linkedin_api import LinkedInAPIError, refresh_linkedin_to_cache


def refresh_instagram_read_only() -> str:
    token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
    account_id = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")
    if not token or not account_id:
        return "Instagram: sin token. Se mantienen datos de muestra."
    try:
        result = refresh_instagram_to_cache(limit=int(os.getenv("INSTAGRAM_REFRESH_LIMIT", "20")))
    except InstagramAPIError as exc:
        return f"Instagram: no se pudo actualizar. {exc}"
    return result["message"]


def refresh_linkedin_read_only() -> str:
    token = os.getenv("LINKEDIN_ACCESS_TOKEN")
    if not token:
        return "LinkedIn: sin token. Se mantienen datos de muestra."
    try:
        result = refresh_linkedin_to_cache()
    except LinkedInAPIError as exc:
        return f"LinkedIn: no se pudo actualizar. {exc}"
    return result["message"]


def refresh_all() -> None:
    load_dotenv()
    initialize_database()
    conn = get_connection()
    messages = [
        refresh_instagram_read_only(),
        refresh_linkedin_read_only(),
    ]
    conn.close()

    print(f"Refresco local DOMO Content Lab - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    for message in messages:
        print(message)
    print("Modo seguro: solo lectura. No publica contenido ni envía mensajes.")


if __name__ == "__main__":
    refresh_all()
