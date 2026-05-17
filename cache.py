from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable


DATA_DIR = Path("data.nosync")
DB_PATH = DATA_DIR / "domo_content_lab.sqlite"


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def initialize_database() -> None:
    conn = get_connection()
    create_tables(conn)
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
            profile_visit_rate REAL NOT NULL
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


def table_count(conn: sqlite3.Connection, table: str) -> int:
    row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    return int(row[0])


def seed_if_empty(conn: sqlite3.Connection) -> None:
    if table_count(conn, "posts") > 0:
        return

    posts = [
        ("2026-04-20", "Instagram", "El rótulo popular también piensa", "DOMO ve el mundo", "Reel", "Lunes", 19, 14500, 980, 52, 18, 41, 63, 188, 12),
        ("2026-04-22", "Instagram", "Antes de diseñar, miro la calle", "Así pienso yo", "Carrusel", "Miércoles", 12, 9800, 710, 44, 21, 30, 94, 122, 9),
        ("2026-04-25", "Instagram", "Tres formas de leer una marca sin brief", "Creatividad para todos", "Carrusel", "Sábado", 10, 7600, 530, 21, 11, 18, 89, 80, 5),
        ("2026-04-29", "Instagram", "Cuenca no es postal, es sistema visual", "DOMO ve el mundo", "Reel", "Miércoles", 20, 18200, 1340, 76, 34, 69, 77, 241, 18),
        ("2026-05-02", "Instagram", "Por qué una foto publicitaria necesita tensión", "Así pienso yo", "Reel", "Sábado", 18, 12100, 900, 38, 17, 27, 44, 151, 10),
        ("2026-05-05", "Instagram", "Checklist visual para saber si una idea aguanta", "Creatividad para todos", "Carrusel", "Martes", 11, 8300, 640, 29, 16, 23, 121, 104, 7),
        ("2026-05-08", "Instagram", "La gráfica de tienda como escuela de dirección de arte", "DOMO ve el mundo", "Reel", "Viernes", 19, 16400, 1190, 61, 29, 57, 82, 211, 15),
        ("2026-05-10", "LinkedIn", "La cultura visual local no es adorno, es estrategia", "DOMO ve el mundo", "Post texto", "Domingo", 9, 4100, 154, 19, 14, 11, 22, 48, 6),
        ("2026-05-12", "LinkedIn", "Cómo evalúo una idea antes de producirla", "Así pienso yo", "Documento", "Martes", 8, 5200, 230, 27, 20, 16, 44, 72, 11),
        ("2026-05-14", "Instagram", "La diferencia entre verse bonito y tener criterio", "Así pienso yo", "Reel", "Jueves", 20, 19300, 1510, 93, 39, 74, 68, 276, 19),
    ]
    insert_posts(conn, posts)

    daily = [
        ("2026-05-08", 16400, 211, 15, 82),
        ("2026-05-09", 4200, 49, 4, 18),
        ("2026-05-10", 4100, 48, 6, 23),
        ("2026-05-11", 3900, 41, 5, 16),
        ("2026-05-12", 5200, 72, 11, 34),
        ("2026-05-13", 4500, 53, 8, 21),
        ("2026-05-14", 19300, 276, 19, 105),
    ]
    conn.executemany(
        "INSERT INTO daily_metrics (date, reach, profile_visits, website_clicks, followers_delta) VALUES (?, ?, ?, ?, ?)",
        daily,
    )

    profile = [
        ("2026-05-14", "Instagram", 18420, 276, 19, 5, 1.43),
        ("2026-05-14", "LinkedIn", 2120, 72, 11, 3, 1.38),
    ]
    conn.executemany(
        """
        INSERT INTO profile_metrics
        (date, platform, followers, profile_visits, website_clicks, dm_leads, profile_visit_rate)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        profile,
    )

    monetization = [
        ("2026-05-14", "Instagram Reels", 4, 2, 1, 1850),
        ("2026-05-14", "Instagram Carruseles", 2, 1, 0, 900),
        ("2026-05-14", "LinkedIn", 1, 3, 2, 3200),
    ]
    conn.executemany(
        """
        INSERT INTO monetization_signals
        (date, source, workshop_leads, consulting_leads, collab_leads, estimated_value_usd)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        monetization,
    )

    ideas = [
        (
            "DOMO ve el mundo",
            "Reel",
            "La esquina que enseña más dirección de arte que una moodboard",
            "Zoom rápido a un rótulo popular y frase: 'Esto no es decoración. Es estrategia visual.'",
            "La audiencia comparte porque reconoce su ciudad; guarda porque aprende a mirar sistemas visuales.",
            "Comenta 'calle' si quieres que analice una gráfica de tu barrio.",
            "Convierte cultura local en criterio profesional internacional.",
            "Alta",
            "Publicar como mini ensayo con 3 aprendizajes para marcas que quieren identidad real.",
        )
    ]
    conn.executemany(
        """
        INSERT INTO content_ideas
        (pillar, format, title, hook, share_save_mechanism, cta, strategic_reason, priority, linkedin_adaptation)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ideas,
    )
    conn.commit()


def insert_posts(conn: sqlite3.Connection, rows: Iterable[tuple]) -> None:
    enriched = []
    for row in rows:
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
        ) = row
        engagement_rate = round(((likes + comments + shares + saves) / reach) * 100, 2)
        share_rate = round((shares / reach) * 100, 2)
        save_rate = round((saves / reach) * 100, 2)
        quality_comment_rate = round((quality_comments / reach) * 100, 2)
        profile_visit_rate = round((profile_visits / reach) * 100, 2)
        enriched.append(
            (
                *row,
                engagement_rate,
                share_rate,
                save_rate,
                quality_comment_rate,
                profile_visit_rate,
            )
        )
    conn.executemany(
        """
        INSERT INTO posts
        (date, platform, title, pillar, format, weekday, hour, reach, likes, comments,
        quality_comments, shares, saves, profile_visits, website_clicks, engagement_rate,
        share_rate, save_rate, quality_comment_rate, profile_visit_rate)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        enriched,
    )
    conn.commit()


def read_sql(conn: sqlite3.Connection, query: str):
    import pandas as pd

    return pd.read_sql_query(query, conn)


def get_posts(conn: sqlite3.Connection):
    return read_sql(conn, "SELECT * FROM posts ORDER BY date DESC")


def get_daily_metrics(conn: sqlite3.Connection):
    return read_sql(conn, "SELECT * FROM daily_metrics ORDER BY date")


def get_profile_metrics(conn: sqlite3.Connection):
    return read_sql(conn, "SELECT * FROM profile_metrics ORDER BY date DESC")


def get_monetization_signals(conn: sqlite3.Connection):
    return read_sql(conn, "SELECT * FROM monetization_signals ORDER BY date DESC")


def get_content_ideas(conn: sqlite3.Connection):
    return read_sql(
        conn,
        """
        SELECT pillar, format, title, hook, share_save_mechanism, cta,
        strategic_reason, priority, linkedin_adaptation
        FROM content_ideas
        ORDER BY created_at DESC
        """,
    )


def add_screenshot(
    conn: sqlite3.Connection,
    date: str,
    platform: str,
    content_title: str,
    image_path: str,
    notes: str,
    ai_reading: str,
) -> None:
    conn.execute(
        """
        INSERT INTO screenshots
        (date, platform, content_title, image_path, notes, ai_reading)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (date, platform, content_title, image_path, notes, ai_reading),
    )
    conn.commit()


def get_screenshots(conn: sqlite3.Connection):
    return read_sql(conn, "SELECT * FROM screenshots ORDER BY created_at DESC")


def add_manual_post(
    conn: sqlite3.Connection,
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
    conn: sqlite3.Connection,
    url: str,
    title: str,
    source_notes: str,
    domo_angle: str,
    suggested_content: str,
) -> None:
    conn.execute(
        """
        INSERT INTO inspirations
        (url, title, source_notes, domo_angle, suggested_content)
        VALUES (?, ?, ?, ?, ?)
        """,
        (url, title, source_notes, domo_angle, suggested_content),
    )
    conn.commit()


def get_inspirations(conn: sqlite3.Connection):
    return read_sql(conn, "SELECT * FROM inspirations ORDER BY created_at DESC")


def add_assistant_note(conn: sqlite3.Connection, question: str, answer: str) -> None:
    conn.execute(
        "INSERT INTO assistant_notes (question, answer) VALUES (?, ?)",
        (question, answer),
    )
    conn.commit()


def get_assistant_notes(conn: sqlite3.Connection):
    return read_sql(conn, "SELECT * FROM assistant_notes ORDER BY created_at DESC")


def add_trend_item(
    conn: sqlite3.Connection,
    query: str,
    title: str,
    url: str,
    source: str,
    domo_reading: str,
) -> None:
    conn.execute(
        """
        INSERT INTO trend_items (query, title, url, source, domo_reading)
        VALUES (?, ?, ?, ?, ?)
        """,
        (query, title, url, source, domo_reading),
    )
    conn.commit()


def get_trend_items(conn: sqlite3.Connection):
    return read_sql(conn, "SELECT * FROM trend_items ORDER BY created_at DESC")


def add_collab_target(
    conn: sqlite3.Connection,
    name: str,
    category: str,
    why_fit: str,
    approach: str,
    priority: str,
    url: str = "",
) -> None:
    conn.execute(
        """
        INSERT INTO collab_targets
        (name, category, why_fit, approach, priority, url)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (name, category, why_fit, approach, priority, url),
    )
    conn.commit()


def get_collab_targets(conn: sqlite3.Connection):
    return read_sql(conn, "SELECT * FROM collab_targets ORDER BY created_at DESC")


def add_action_item(
    conn: sqlite3.Connection,
    title: str,
    area: str,
    reason: str,
    priority: str,
) -> None:
    conn.execute(
        """
        INSERT INTO action_items (title, area, reason, priority)
        VALUES (?, ?, ?, ?)
        """,
        (title, area, reason, priority),
    )
    conn.commit()


def update_action_status(conn: sqlite3.Connection, item_id: int, status: str) -> None:
    conn.execute("UPDATE action_items SET status = ? WHERE id = ?", (status, item_id))
    conn.commit()


def get_action_items(conn: sqlite3.Connection):
    return read_sql(conn, "SELECT * FROM action_items ORDER BY created_at DESC")


def add_carousel_draft(
    conn: sqlite3.Connection,
    source: str,
    title: str,
    objective: str,
    slides_json: str,
    caption: str,
    cta: str,
) -> None:
    conn.execute(
        """
        INSERT INTO carousel_drafts
        (source, title, objective, slides_json, caption, cta)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (source, title, objective, slides_json, caption, cta),
    )
    conn.commit()


def get_carousel_drafts(conn: sqlite3.Connection):
    return read_sql(conn, "SELECT * FROM carousel_drafts ORDER BY created_at DESC")
