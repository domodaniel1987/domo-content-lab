from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any, Iterable


DATA_DIR = Path("data.nosync")
DB_PATH = DATA_DIR / "domo_content_lab.sqlite"
SUPABASE_PROJECT_ID = "gccbondkipsqgakduokf"


POST_BASE_COLUMNS = [
    "date",
    "platform",
    "title",
    "pillar",
    "format",
    "weekday",
    "hour",
    "reach",
    "likes",
    "comments",
    "quality_comments",
    "shares",
    "saves",
    "profile_visits",
    "website_clicks",
]
POST_RATE_COLUMNS = [
    "engagement_rate",
    "share_rate",
    "save_rate",
    "quality_comment_rate",
    "profile_visit_rate",
]
POST_OPTIONAL_COLUMNS = ["external_id", "permalink", "imported_at"]
POST_COLUMNS = [*POST_BASE_COLUMNS, *POST_RATE_COLUMNS]


class SupabaseConnection:
    def __init__(self, client: Any) -> None:
        self.client = client

    def close(self) -> None:
        return None


def get_secret(name: str, default: str = "") -> str:
    try:
        import streamlit as st

        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return str(value or os.getenv(name, default) or "").strip()


def normalize_supabase_url(value: str) -> str:
    value = value.strip()
    if not value:
        project_id = get_secret("SUPABASE_PROJECT_ID", SUPABASE_PROJECT_ID)
        return f"https://{project_id}.supabase.co" if project_id else ""
    if value.startswith("http://") or value.startswith("https://"):
        return value.rstrip("/")
    if "." not in value:
        return f"https://{value}.supabase.co"
    return f"https://{value}".rstrip("/")


def get_supabase_client() -> Any | None:
    url = normalize_supabase_url(get_secret("SUPABASE_URL", ""))
    key = (
        get_secret("SUPABASE_SERVICE_ROLE_KEY", "")
        or get_secret("SUPABASE_KEY", "")
        or get_secret("SUPABASE_ANON_KEY", "")
    )
    if not url or not key:
        return None
    try:
        from supabase import create_client

        return create_client(url, key)
    except Exception:
        return None


def get_supabase_status() -> dict[str, str]:
    url = normalize_supabase_url(get_secret("SUPABASE_URL", ""))
    key = (
        get_secret("SUPABASE_SERVICE_ROLE_KEY", "")
        or get_secret("SUPABASE_KEY", "")
        or get_secret("SUPABASE_ANON_KEY", "")
    )
    status = {
        "mode": "SQLite local",
        "url": "Lista" if url else "Falta SUPABASE_URL",
        "key": "Lista" if key else "Falta SUPABASE_SERVICE_ROLE_KEY",
        "package": "Pendiente",
        "schema": "Pendiente",
        "message": "La app esta usando memoria local.",
    }
    if not url or not key:
        status["message"] = "Falta pegar la URL o la service_role key en Streamlit Secrets."
        return status

    try:
        from supabase import create_client

        status["package"] = "Listo"
    except Exception as exc:
        status["package"] = "Falta instalar supabase"
        status["message"] = f"Sube/reemplaza requirements.txt y reinicia Streamlit. Detalle: {type(exc).__name__}"
        return status

    try:
        client = create_client(url, key)
    except Exception as exc:
        status["message"] = f"La URL o key no pudo crear conexion. Detalle: {type(exc).__name__}"
        return status

    try:
        client.table("posts").select("id,external_id,permalink").limit(1).execute()
    except Exception as exc:
        status["schema"] = "Falta SQL o permisos"
        status["message"] = f"Falta correr supabase_schema.sql o revisar la key. Detalle: {type(exc).__name__}"
        return status

    status["mode"] = "Supabase"
    status["schema"] = "Listo"
    status["message"] = "Supabase conectado. El historial ya puede quedar en la nube."
    return status


def supabase_schema_ready(client: Any) -> bool:
    try:
        client.table("posts").select("id,external_id,permalink").limit(1).execute()
        return True
    except Exception:
        return False


def get_connection() -> sqlite3.Connection | SupabaseConnection:
    client = get_supabase_client()
    if client is not None and supabase_schema_ready(client):
        return SupabaseConnection(client)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def is_supabase(conn: sqlite3.Connection | SupabaseConnection) -> bool:
    return isinstance(conn, SupabaseConnection)


def get_database_mode() -> str:
    conn = get_connection()
    mode = "Supabase" if is_supabase(conn) else "SQLite local"
    conn.close()
    return mode


def initialize_database() -> None:
    conn = get_connection()
    if not is_supabase(conn):
        create_tables(conn)
        migrate_sqlite_schema(conn)
    seed_if_empty(conn)
    conn.close()


def create_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            platform TEXT NOT NULL,
            title TEXT NOT NULL,
            pillar TEXT NOT NULL,
            format TEXT NOT NULL,
            weekday TEXT NOT NULL,
            hour INTEGER NOT NULL,
            reach INTEGER NOT NULL,
            likes INTEGER NOT NULL,
            comments INTEGER NOT NULL,
            quality_comments INTEGER NOT NULL,
            shares INTEGER NOT NULL,
            saves INTEGER NOT NULL,
            profile_visits INTEGER NOT NULL,
            website_clicks INTEGER NOT NULL,
            engagement_rate REAL NOT NULL,
            share_rate REAL NOT NULL,
            save_rate REAL NOT NULL,
            quality_comment_rate REAL NOT NULL,
            profile_visit_rate REAL NOT NULL,
            external_id TEXT,
            permalink TEXT,
            imported_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS daily_metrics (
            date TEXT PRIMARY KEY,
            reach INTEGER NOT NULL,
            profile_visits INTEGER NOT NULL,
            website_clicks INTEGER NOT NULL,
            followers_delta INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS profile_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            platform TEXT NOT NULL,
            followers INTEGER NOT NULL,
            profile_visits INTEGER NOT NULL,
            website_clicks INTEGER NOT NULL,
            dm_leads INTEGER NOT NULL,
            profile_visit_rate REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS monetization_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            source TEXT NOT NULL,
            workshop_leads INTEGER NOT NULL,
            consulting_leads INTEGER NOT NULL,
            collab_leads INTEGER NOT NULL,
            estimated_value_usd INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS content_ideas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pillar TEXT NOT NULL,
            format TEXT NOT NULL,
            title TEXT NOT NULL,
            hook TEXT NOT NULL,
            share_save_mechanism TEXT NOT NULL,
            cta TEXT NOT NULL,
            strategic_reason TEXT NOT NULL,
            priority TEXT NOT NULL,
            linkedin_adaptation TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS screenshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            platform TEXT NOT NULL,
            content_title TEXT NOT NULL,
            image_path TEXT NOT NULL,
            notes TEXT,
            ai_reading TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS inspirations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            title TEXT,
            source_notes TEXT,
            domo_angle TEXT,
            suggested_content TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS assistant_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS trend_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            source TEXT,
            domo_reading TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS collab_targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            why_fit TEXT NOT NULL,
            approach TEXT NOT NULL,
            priority TEXT NOT NULL,
            status TEXT DEFAULT 'Por investigar',
            url TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS action_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            area TEXT NOT NULL,
            reason TEXT NOT NULL,
            priority TEXT NOT NULL,
            status TEXT DEFAULT 'Pendiente',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS carousel_drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            title TEXT NOT NULL,
            objective TEXT NOT NULL,
            slides_json TEXT NOT NULL,
            caption TEXT,
            cta TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.commit()


def migrate_sqlite_schema(conn: sqlite3.Connection) -> None:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(posts)").fetchall()}
    migrations = {
        "external_id": "ALTER TABLE posts ADD COLUMN external_id TEXT",
        "permalink": "ALTER TABLE posts ADD COLUMN permalink TEXT",
        "imported_at": "ALTER TABLE posts ADD COLUMN imported_at TEXT",
    }
    for column, sql in migrations.items():
        if column not in existing:
            conn.execute(sql)
    conn.commit()


def table_count(conn: sqlite3.Connection | SupabaseConnection, table: str) -> int:
    if is_supabase(conn):
        result = conn.client.table(table).select("id", count="exact").limit(1).execute()
        if result.count is not None:
            return int(result.count)
        return len(result.data or [])
    row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    return int(row[0])


def insert_rows(conn: sqlite3.Connection | SupabaseConnection, table: str, rows: Iterable[dict[str, Any]]) -> None:
    payload = list(rows)
    if not payload:
        return
    if is_supabase(conn):
        conn.client.table(table).insert(payload).execute()
        return

    columns = list(payload[0].keys())
    placeholders = ", ".join(["?"] * len(columns))
    column_sql = ", ".join(columns)
    values = [tuple(row.get(column) for column in columns) for row in payload]
    conn.executemany(f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders})", values)
    conn.commit()


def update_row(conn: sqlite3.Connection | SupabaseConnection, table: str, item_id: int, values: dict[str, Any]) -> None:
    payload = {key: value for key, value in values.items() if key != "id"}
    if not payload:
        return
    if is_supabase(conn):
        conn.client.table(table).update(payload).eq("id", item_id).execute()
        return
    columns = list(payload.keys())
    set_sql = ", ".join([f"{column} = ?" for column in columns])
    conn.execute(f"UPDATE {table} SET {set_sql} WHERE id = ?", [payload[column] for column in columns] + [item_id])
    conn.commit()


def delete_row(conn: sqlite3.Connection | SupabaseConnection, table: str, item_id: int) -> None:
    if is_supabase(conn):
        conn.client.table(table).delete().eq("id", item_id).execute()
        return
    conn.execute(f"DELETE FROM {table} WHERE id = ?", (item_id,))
    conn.commit()


def enrich_post_row(row: tuple) -> dict[str, Any]:
    data = dict(zip(POST_BASE_COLUMNS, row))
    return enrich_post_record(data)


def enrich_post_record(data: dict[str, Any]) -> dict[str, Any]:
    reach = max(float(data["reach"]), 1.0)
    likes = float(data["likes"])
    comments = float(data["comments"])
    shares = float(data["shares"])
    saves = float(data["saves"])
    quality_comments = float(data["quality_comments"])
    profile_visits = float(data["profile_visits"])
    data.update(
        {
            "engagement_rate": round(((likes + comments + shares + saves) / reach) * 100, 2),
            "share_rate": round((shares / reach) * 100, 2),
            "save_rate": round((saves / reach) * 100, 2),
            "quality_comment_rate": round((quality_comments / reach) * 100, 2),
            "profile_visit_rate": round((profile_visits / reach) * 100, 2),
        }
    )
    return data


def seed_if_empty(conn: sqlite3.Connection | SupabaseConnection) -> None:
    if table_count(conn, "posts") > 0:
        return

    posts = [
        ("2026-04-20", "Instagram", "El rotulo popular tambien piensa", "DOMO ve el mundo", "Reel", "Lunes", 19, 14500, 980, 52, 18, 41, 63, 188, 12),
        ("2026-04-22", "Instagram", "Antes de disenar, miro la calle", "Asi pienso yo", "Carrusel", "Miercoles", 12, 9800, 710, 44, 21, 30, 94, 122, 9),
        ("2026-04-25", "Instagram", "Tres formas de leer una marca sin brief", "Creatividad para todos", "Carrusel", "Sabado", 10, 7600, 530, 21, 11, 18, 89, 80, 5),
        ("2026-04-29", "Instagram", "Cuenca no es postal, es sistema visual", "DOMO ve el mundo", "Reel", "Miercoles", 20, 18200, 1340, 76, 34, 69, 77, 241, 18),
        ("2026-05-02", "Instagram", "Por que una foto publicitaria necesita tension", "Asi pienso yo", "Reel", "Sabado", 18, 12100, 900, 38, 17, 27, 44, 151, 10),
        ("2026-05-05", "Instagram", "Checklist visual para saber si una idea aguanta", "Creatividad para todos", "Carrusel", "Martes", 11, 8300, 640, 29, 16, 23, 121, 104, 7),
        ("2026-05-08", "Instagram", "La grafica de tienda como escuela de direccion de arte", "DOMO ve el mundo", "Reel", "Viernes", 19, 16400, 1190, 61, 29, 57, 82, 211, 15),
        ("2026-05-10", "LinkedIn", "La cultura visual local no es adorno, es estrategia", "DOMO ve el mundo", "Post texto", "Domingo", 9, 4100, 154, 19, 14, 11, 22, 48, 6),
        ("2026-05-12", "LinkedIn", "Como evaluo una idea antes de producirla", "Asi pienso yo", "Documento", "Martes", 8, 5200, 230, 27, 20, 16, 44, 72, 11),
        ("2026-05-14", "Instagram", "La diferencia entre verse bonito y tener criterio", "Asi pienso yo", "Reel", "Jueves", 20, 19300, 1510, 93, 39, 74, 68, 276, 19),
    ]
    insert_posts(conn, posts)

    insert_rows(
        conn,
        "daily_metrics",
        [
            {"date": "2026-05-08", "reach": 16400, "profile_visits": 211, "website_clicks": 15, "followers_delta": 82},
            {"date": "2026-05-09", "reach": 4200, "profile_visits": 49, "website_clicks": 4, "followers_delta": 18},
            {"date": "2026-05-10", "reach": 4100, "profile_visits": 48, "website_clicks": 6, "followers_delta": 23},
            {"date": "2026-05-11", "reach": 3900, "profile_visits": 41, "website_clicks": 5, "followers_delta": 16},
            {"date": "2026-05-12", "reach": 5200, "profile_visits": 72, "website_clicks": 11, "followers_delta": 34},
            {"date": "2026-05-13", "reach": 4500, "profile_visits": 53, "website_clicks": 8, "followers_delta": 21},
            {"date": "2026-05-14", "reach": 19300, "profile_visits": 276, "website_clicks": 19, "followers_delta": 105},
        ],
    )

    insert_rows(
        conn,
        "profile_metrics",
        [
            {"date": "2026-05-14", "platform": "Instagram", "followers": 18420, "profile_visits": 276, "website_clicks": 19, "dm_leads": 5, "profile_visit_rate": 1.43},
            {"date": "2026-05-14", "platform": "LinkedIn", "followers": 2120, "profile_visits": 72, "website_clicks": 11, "dm_leads": 3, "profile_visit_rate": 1.38},
        ],
    )

    insert_rows(
        conn,
        "monetization_signals",
        [
            {"date": "2026-05-14", "source": "Instagram Reels", "workshop_leads": 4, "consulting_leads": 2, "collab_leads": 1, "estimated_value_usd": 1850},
            {"date": "2026-05-14", "source": "Instagram Carruseles", "workshop_leads": 2, "consulting_leads": 1, "collab_leads": 0, "estimated_value_usd": 900},
            {"date": "2026-05-14", "source": "LinkedIn", "workshop_leads": 1, "consulting_leads": 3, "collab_leads": 2, "estimated_value_usd": 3200},
        ],
    )

    insert_rows(
        conn,
        "content_ideas",
        [
            {
                "pillar": "DOMO ve el mundo",
                "format": "Reel",
                "title": "La esquina que ensena mas direccion de arte que una moodboard",
                "hook": "Zoom rapido a un rotulo popular y frase: Esto no es decoracion. Es estrategia visual.",
                "share_save_mechanism": "La audiencia comparte porque reconoce su ciudad; guarda porque aprende a mirar sistemas visuales.",
                "cta": "Comenta calle si quieres que analice una grafica de tu barrio.",
                "strategic_reason": "Convierte cultura local en criterio profesional internacional.",
                "priority": "Alta",
                "linkedin_adaptation": "Publicar como mini ensayo con 3 aprendizajes para marcas que quieren identidad real.",
            }
        ],
    )


def insert_posts(conn: sqlite3.Connection | SupabaseConnection, rows: Iterable[tuple]) -> None:
    insert_rows(conn, "posts", [enrich_post_row(row) for row in rows])


def upsert_post_record(conn: sqlite3.Connection | SupabaseConnection, post: dict[str, Any]) -> None:
    payload = enrich_post_record(post.copy())
    external_id = payload.get("external_id", "")

    if is_supabase(conn):
        if external_id:
            existing = (
                conn.client.table("posts")
                .select("id")
                .eq("external_id", external_id)
                .limit(1)
                .execute()
                .data
                or []
            )
            if existing:
                conn.client.table("posts").update(payload).eq("external_id", external_id).execute()
                return
        conn.client.table("posts").insert(payload).execute()
        return

    if external_id:
        existing = conn.execute("SELECT id FROM posts WHERE external_id = ? LIMIT 1", (external_id,)).fetchone()
        if existing:
            columns = list(payload.keys())
            set_sql = ", ".join([f"{column} = ?" for column in columns])
            values = [payload[column] for column in columns]
            values.append(int(existing[0]))
            conn.execute(f"UPDATE posts SET {set_sql} WHERE id = ?", values)
            conn.commit()
            return

    insert_rows(conn, "posts", [payload])


def read_sql(conn: sqlite3.Connection | SupabaseConnection, query: str):
    import pandas as pd

    if is_supabase(conn):
        raise ValueError("read_sql solo se usa con SQLite.")
    return pd.read_sql_query(query, conn)


def get_table(
    conn: sqlite3.Connection | SupabaseConnection,
    table: str,
    order_by: str | None = None,
    descending: bool = True,
    columns: list[str] | None = None,
):
    import pandas as pd

    if is_supabase(conn):
        select_columns = ",".join(columns) if columns else "*"
        query = conn.client.table(table).select(select_columns)
        if order_by:
            query = query.order(order_by, desc=descending)
        data = query.execute().data or []
        frame = pd.DataFrame(data)
        if columns:
            for column in columns:
                if column not in frame.columns:
                    frame[column] = None
            frame = frame[columns]
        return frame

    select_sql = ", ".join(columns) if columns else "*"
    order_sql = ""
    if order_by:
        direction = "DESC" if descending else "ASC"
        order_sql = f" ORDER BY {order_by} {direction}"
    return read_sql(conn, f"SELECT {select_sql} FROM {table}{order_sql}")


def get_posts(conn: sqlite3.Connection | SupabaseConnection):
    return get_table(conn, "posts", order_by="date", descending=True)


def get_daily_metrics(conn: sqlite3.Connection | SupabaseConnection):
    return get_table(conn, "daily_metrics", order_by="date", descending=False)


def get_profile_metrics(conn: sqlite3.Connection | SupabaseConnection):
    return get_table(conn, "profile_metrics", order_by="date", descending=True)


def get_monetization_signals(conn: sqlite3.Connection | SupabaseConnection):
    return get_table(conn, "monetization_signals", order_by="date", descending=True)


def get_content_ideas(conn: sqlite3.Connection | SupabaseConnection):
    return get_table(
        conn,
        "content_ideas",
        order_by="created_at",
        descending=True,
        columns=[
            "id",
            "pillar",
            "format",
            "title",
            "hook",
            "share_save_mechanism",
            "cta",
            "strategic_reason",
            "priority",
            "linkedin_adaptation",
            "created_at",
        ],
    )


def add_content_idea(conn: sqlite3.Connection | SupabaseConnection, idea: dict[str, Any]) -> None:
    insert_rows(
        conn,
        "content_ideas",
        [
            {
                "pillar": idea.get("pillar", "Así pienso yo"),
                "format": idea.get("format", "Contenido"),
                "title": idea.get("title", "Idea DOMO"),
                "hook": idea.get("hook", ""),
                "share_save_mechanism": idea.get("share_save_mechanism", ""),
                "cta": idea.get("cta", ""),
                "strategic_reason": idea.get("strategic_reason", ""),
                "priority": idea.get("priority", "Media"),
                "linkedin_adaptation": idea.get("linkedin_adaptation", ""),
            }
        ],
    )


def add_screenshot(
    conn: sqlite3.Connection | SupabaseConnection,
    date: str,
    platform: str,
    content_title: str,
    image_path: str,
    notes: str,
    ai_reading: str,
) -> None:
    insert_rows(
        conn,
        "screenshots",
        [
            {
                "date": date,
                "platform": platform,
                "content_title": content_title,
                "image_path": image_path,
                "notes": notes,
                "ai_reading": ai_reading,
            }
        ],
    )


def get_screenshots(conn: sqlite3.Connection | SupabaseConnection):
    return get_table(conn, "screenshots", order_by="created_at", descending=True)


def add_manual_post(
    conn: sqlite3.Connection | SupabaseConnection,
    date: str,
    platform: str,
    title: str,
    pillar: str,
    format_name: str,
    weekday: str,
    hour: int,
    reach: int,
    likes: int,
    comments: int,
    quality_comments: int,
    shares: int,
    saves: int,
    profile_visits: int,
    website_clicks: int,
) -> None:
    insert_posts(
        conn,
        [
            (
                date,
                platform,
                title,
                pillar,
                format_name,
                weekday,
                hour,
                reach,
                likes,
                comments,
                quality_comments,
                shares,
                saves,
                profile_visits,
                website_clicks,
            )
        ],
    )


def add_inspiration(
    conn: sqlite3.Connection | SupabaseConnection,
    url: str,
    title: str,
    source_notes: str,
    domo_angle: str,
    suggested_content: str,
) -> None:
    insert_rows(
        conn,
        "inspirations",
        [
            {
                "url": url,
                "title": title,
                "source_notes": source_notes,
                "domo_angle": domo_angle,
                "suggested_content": suggested_content,
            }
        ],
    )


def get_inspirations(conn: sqlite3.Connection | SupabaseConnection):
    return get_table(conn, "inspirations", order_by="created_at", descending=True)


def add_assistant_note(conn: sqlite3.Connection | SupabaseConnection, question: str, answer: str) -> None:
    insert_rows(conn, "assistant_notes", [{"question": question, "answer": answer}])


def get_assistant_notes(conn: sqlite3.Connection | SupabaseConnection):
    return get_table(conn, "assistant_notes", order_by="created_at", descending=True)


def add_trend_item(
    conn: sqlite3.Connection | SupabaseConnection,
    query: str,
    title: str,
    url: str,
    source: str,
    domo_reading: str,
) -> None:
    insert_rows(
        conn,
        "trend_items",
        [{"query": query, "title": title, "url": url, "source": source, "domo_reading": domo_reading}],
    )


def get_trend_items(conn: sqlite3.Connection | SupabaseConnection):
    return get_table(conn, "trend_items", order_by="created_at", descending=True)


def add_collab_target(
    conn: sqlite3.Connection | SupabaseConnection,
    name: str,
    category: str,
    why_fit: str,
    approach: str,
    priority: str,
    url: str = "",
) -> None:
    insert_rows(
        conn,
        "collab_targets",
        [
            {
                "name": name,
                "category": category,
                "why_fit": why_fit,
                "approach": approach,
                "priority": priority,
                "url": url,
            }
        ],
    )


def get_collab_targets(conn: sqlite3.Connection | SupabaseConnection):
    return get_table(conn, "collab_targets", order_by="created_at", descending=True)


def add_action_item(
    conn: sqlite3.Connection | SupabaseConnection,
    title: str,
    area: str,
    reason: str,
    priority: str,
) -> None:
    insert_rows(conn, "action_items", [{"title": title, "area": area, "reason": reason, "priority": priority}])


def update_action_status(conn: sqlite3.Connection | SupabaseConnection, item_id: int, status: str) -> None:
    if is_supabase(conn):
        conn.client.table("action_items").update({"status": status}).eq("id", item_id).execute()
        return
    conn.execute("UPDATE action_items SET status = ? WHERE id = ?", (status, item_id))
    conn.commit()


def get_action_items(conn: sqlite3.Connection | SupabaseConnection):
    return get_table(conn, "action_items", order_by="created_at", descending=True)


def add_carousel_draft(
    conn: sqlite3.Connection | SupabaseConnection,
    source: str,
    title: str,
    objective: str,
    slides_json: str,
    caption: str,
    cta: str,
) -> None:
    insert_rows(
        conn,
        "carousel_drafts",
        [
            {
                "source": source,
                "title": title,
                "objective": objective,
                "slides_json": slides_json,
                "caption": caption,
                "cta": cta,
            }
        ],
    )


def get_carousel_drafts(conn: sqlite3.Connection | SupabaseConnection):
    return get_table(conn, "carousel_drafts", order_by="created_at", descending=True)
