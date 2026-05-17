import os
import json
import socket
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from assistant import (
    analyze_link_for_domo,
    analyze_screenshot_for_domo,
    answer_as_domo_assistant,
    has_ai_key,
)
from cache import (
    DATA_DIR,
    add_action_item,
    add_assistant_note,
    add_carousel_draft,
    add_collab_target,
    add_inspiration,
    add_manual_post,
    add_screenshot,
    add_trend_item,
    get_connection,
    get_action_items,
    get_assistant_notes,
    get_carousel_drafts,
    get_collab_targets,
    get_content_ideas,
    get_daily_metrics,
    get_inspirations,
    get_monetization_signals,
    get_posts,
    get_profile_metrics,
    get_screenshots,
    get_trend_items,
    initialize_database,
    update_action_status,
)
from carousel import generate_carousel, slides_to_json
from ideas import generate_ideas
from trend_scout import DEFAULT_TREND_QUERIES, scout_trends, suggest_collabs


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
        .stApp {{
            background: {BRAND_COLORS["paper"]};
            color: {BRAND_COLORS["ink"]};
        }}
        h1, h2, h3 {{
            letter-spacing: 0 !important;
            font-weight: 900 !important;
            text-transform: uppercase;
        }}
        [data-testid="stMetric"] {{
            background: #fffaf0;
            border: 2px solid {BRAND_COLORS["ink"]};
            border-radius: 6px;
            padding: 14px;
            box-shadow: 5px 5px 0 {BRAND_COLORS["ink"]};
        }}
        [data-testid="stMetric"] * {{
            color: {BRAND_COLORS["ink"]} !important;
        }}
        [data-testid="stMetricValue"] {{
            color: {BRAND_COLORS["ink"]} !important;
            font-weight: 900 !important;
        }}
        div[data-testid="stDataFrame"] {{
            border: 2px solid {BRAND_COLORS["ink"]};
        }}
        .domo-label {{
            display: inline-block;
            background: {BRAND_COLORS["yellow"]};
            border: 2px solid {BRAND_COLORS["ink"]};
            padding: 4px 8px;
            font-weight: 900;
            text-transform: uppercase;
            transform: rotate(-1deg);
            margin-bottom: 10px;
        }}
        .domo-note {{
            border-left: 8px solid {BRAND_COLORS["red"]};
            background: #fffaf0;
            padding: 14px 16px;
            font-size: 1rem;
        }}
        .domo-action {{
            background: #fffaf0;
            border: 2px solid {BRAND_COLORS["ink"]};
            border-radius: 6px;
            padding: 14px;
            min-height: 128px;
            box-shadow: 4px 4px 0 {BRAND_COLORS["ink"]};
        }}
        .domo-action strong {{
            text-transform: uppercase;
            font-size: 1.02rem;
        }}
        .domo-pill {{
            display: inline-block;
            background: {BRAND_COLORS["red"]};
            color: white;
            border: 2px solid {BRAND_COLORS["ink"]};
            padding: 2px 7px;
            font-weight: 900;
            margin-right: 5px;
        }}
        section[data-testid="stSidebar"] {{
            background: #fffaf0;
            border-right: 2px solid {BRAND_COLORS["ink"]};
        }}
        section[data-testid="stSidebar"] * {{
            color: {BRAND_COLORS["ink"]} !important;
        }}
        section[data-testid="stSidebar"] code {{
            color: #1B998B !important;
            background: #111111 !important;
            border-radius: 6px;
            padding: 8px !important;
        }}
        div[role="radiogroup"] label {{
            color: {BRAND_COLORS["ink"]} !important;
            font-weight: 800 !important;
            opacity: 1 !important;
        }}
        div[role="radiogroup"] p {{
            color: {BRAND_COLORS["ink"]} !important;
        }}
        .stButton > button {{
            background: {BRAND_COLORS["ink"]} !important;
            color: #fffaf0 !important;
            border: 2px solid {BRAND_COLORS["ink"]} !important;
            border-radius: 6px !important;
            font-weight: 900 !important;
        }}
        .stButton > button * {{
            color: #fffaf0 !important;
        }}
        a {{
            color: {BRAND_COLORS["blue"]} !important;
            font-weight: 800;
        }}
        @media (max-width: 760px) {{
            h1 {{
                font-size: 2rem !important;
                line-height: 1.02 !important;
            }}
            [data-testid="column"] {{
                width: 100% !important;
                flex: 1 1 100% !important;
            }}
            .domo-action {{
                min-height: auto;
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
    st.markdown('<span class="domo-label">DOMO Content Lab</span>', unsafe_allow_html=True)
    st.title("Asistente de crecimiento visual")
    st.markdown(
        """
        <div class="domo-note">
        Lectura estratégica para Instagram y LinkedIn: menos vanidad, más señales para decidir
        qué publicar, qué repetir y qué convertir en workshop, consultoría o colaboración.
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_mobile_hint() -> None:
    if os.getenv("STREAMLIT_SERVER_HEADLESS") or os.getenv("HOSTNAME"):
        st.sidebar.markdown("### App online")
        st.sidebar.write("Abierta desde Streamlit Cloud.")
        st.sidebar.markdown("### IA")
        st.sidebar.write("Key configurada. Si falla, revisa saldo/cuota en OpenAI." if has_ai_key() else "Sin API key: funciona con estrategia local. Con API key analiza mejor capturas y links.")
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


def render_command_center(posts: pd.DataFrame, action_items: pd.DataFrame) -> None:
    st.subheader("Qué hacemos hoy")
    avg_share = posts["share_rate"].mean()
    avg_save = posts["save_rate"].mean()
    avg_comments = posts["quality_comment_rate"].mean()

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

    cols = st.columns(3)
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

    st.subheader("Señales importantes")
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

    filtered["strategic_score"] = (
        filtered["share_rate"] * 2.0
        + filtered["save_rate"] * 1.8
        + filtered["quality_comment_rate"] * 1.6
        + filtered["profile_visit_rate"] * 1.4
    ).round(2)
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
    with st.container(border=True):
        st.markdown(f"### {idea.get('title', 'Idea DOMO')}")
        cols = st.columns(3)
        cols[0].markdown(f"**Pilar:** {idea.get('pillar', 'DOMO')}")
        cols[1].markdown(f"**Formato:** {idea.get('format', 'Contenido')}")
        cols[2].markdown(f"**Prioridad:** {idea.get('priority', 'Media')}")
        if idea.get("hook"):
            st.markdown(f"**Hook:** {idea['hook']}")
        if idea.get("share_save_mechanism"):
            st.markdown(f"**Share/save:** {idea['share_save_mechanism']}")
        if idea.get("cta"):
            st.markdown(f"**CTA:** {idea['cta']}")
        if idea.get("strategic_reason"):
            st.markdown(f"**Razón:** {idea['strategic_reason']}")
        if idea.get("linkedin_adaptation"):
            st.markdown(f"**LinkedIn:** {idea['linkedin_adaptation']}")


def render_slide_card(slide: dict) -> None:
    with st.container(border=True):
        st.markdown(f"#### Slide {slide.get('number', '')}")
        st.markdown(f"**{slide.get('text', '')}**")
        if slide.get("note"):
            st.caption(slide["note"])


def render_ai_answer(answer: str) -> None:
    payload = parse_ai_payload(answer)
    if not payload:
        st.write(answer)
        return

    if isinstance(payload.get("ideas"), list):
        for idea in payload["ideas"]:
            render_idea_card(idea)
        return

    if isinstance(payload.get("slides"), list):
        st.markdown(f"### {payload.get('title', 'Carrusel DOMO')}")
        if payload.get("objective"):
            st.markdown(f"**Objetivo:** {payload['objective']}")
        for slide in payload["slides"]:
            render_slide_card(slide)
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
    st.write("Configuración simple del sistema. Aquí revisas si está listo para operar como app real.")
    checks = pd.DataFrame(
        [
            {"Área": "IA", "Estado": "Lista" if has_ai_key() else "Falta OPENAI_API_KEY", "Para qué sirve": "Ideas, capturas, asistente y lectura de links."},
            {"Área": "Instagram API", "Estado": "Configurada" if os.getenv("INSTAGRAM_ACCESS_TOKEN") else "Pendiente", "Para qué sirve": "Actualizar métricas casi automático."},
            {"Área": "Acceso remoto", "Estado": "Pendiente", "Para qué sirve": "Abrir desde celular/oficina desde cualquier lugar."},
            {"Área": "Base de datos", "Estado": "SQLite local", "Para qué sirve": "Perfecto para prototipo; para nube conviene Supabase/Postgres."},
        ]
    )
    st.dataframe(checks, hide_index=True, use_container_width=True)

    st.markdown("#### Para que funcione desde cualquier lugar")
    st.write(
        "Hay que desplegarlo en la nube con login. Para gratis: Streamlit Cloud sirve para probar; "
        "para datos serios conviene sumar Supabase gratis como base persistente."
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
        for idea in ideas_to_show:
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
        seed = st.text_area(
            "Idea o frase inicial",
            placeholder="Ej: Pinterest no entiende tu barrio / Cuenca no es postal, es sistema visual",
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
            with st.container(border=True):
                st.markdown(f"#### Slide {slide.get('number', '')}")
                st.markdown(f"**{slide.get('text', '')}**")
                st.caption(slide.get("note", ""))
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
                    st.markdown(f"**Slide {slide.get('number', '')}:** {slide.get('text', '')}")
                    st.caption(slide.get("note", ""))
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

    page = st.sidebar.radio(
        "Navegación",
        [
            "Inicio",
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
        ],
    )

    if page == "Inicio":
        render_command_center(posts, action_items)
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
            "Tendencias",
            "Audiencia",
            "Posts",
            "Cuándo publicar",
            "Monetización",
        ])

        with tabs[0]:
            render_summary(posts, profile)
        with tabs[1]:
            render_trends(posts, daily)
        with tabs[2]:
            render_audience(profile)
        with tabs[3]:
            render_posts(posts)
        with tabs[4]:
            render_publish_time(posts)
        with tabs[5]:
            render_monetization(monetization, posts)

    st.caption(f"Última lectura local: {datetime.now().strftime('%Y-%m-%d %H:%M')}. Solo lectura. No publica, no envía mensajes.")


if __name__ == "__main__":
    main()
