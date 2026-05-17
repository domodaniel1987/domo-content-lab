from __future__ import annotations

import os
from datetime import datetime

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> bool:
        return False

from cache import get_connection, initialize_database


def refresh_instagram_read_only() -> str:
    token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
    if not token:
        return "Instagram: sin token. Se mantienen datos de muestra."
    return "Instagram: token detectado. Conecta aquí la lectura de Graph API cuando tengas permisos."


def refresh_linkedin_read_only() -> str:
    token = os.getenv("LINKEDIN_ACCESS_TOKEN")
    if not token:
        return "LinkedIn: sin token. Se mantienen datos de muestra."
    return "LinkedIn: token detectado. Conecta aquí la lectura de LinkedIn API cuando tengas permisos."


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
