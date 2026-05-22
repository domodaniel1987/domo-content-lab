from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> bool:
        return False


PROMPT_PATH = Path("prompts/domo_ideas_system.md")


DOMO_PILLARS = [
    "Así pienso yo",
    "Creatividad para todos",
    "DOMO ve el mundo",
]


LOCAL_IDEA_BANK = [
    {
        "title": "El rótulo que explica una marca mejor que un brief",
        "pillar": "DOMO ve el mundo",
        "format": "Reel documental corto",
        "hook": "Plano cerrado a un rótulo: 'Esta esquina tiene más identidad que muchas marcas premium.'",
        "share_save_mechanism": "Share por orgullo cultural; save por lectura visual en 3 capas: color, jerarquía y memoria.",
        "cta": "Comenta 'rótulo' y analizo uno de tu barrio.",
        "strategic_reason": "Posiciona a DOMO como traductor de cultura visual LATAM con ojo internacional.",
        "priority": "Alta",
        "linkedin_adaptation": "Convertirlo en post ensayo: qué pueden aprender las marcas globales de la gráfica popular.",
    },
    {
        "title": "Antes de diseñar, hago esta pregunta incómoda",
        "pillar": "Así pienso yo",
        "format": "Reel hablando a cámara + cortes de proceso",
        "hook": "'Si la idea solo se ve bonita, todavía no está lista.'",
        "share_save_mechanism": "Save por marco de evaluación; share entre creativos que necesitan defender criterio.",
        "cta": "Comenta una idea que se veía bonita pero no decía nada.",
        "strategic_reason": "Mueve la conversación de estética a pensamiento estratégico.",
        "priority": "Alta",
        "linkedin_adaptation": "Publicar como reflexión profesional con ejemplo de dirección creativa.",
    },
    {
        "title": "La checklist DOMO para saber si una pieza tiene calle",
        "pillar": "Creatividad para todos",
        "format": "Carrusel guardable",
        "hook": "Portada: 'Tu diseño tiene estilo, pero ¿tiene mundo?'",
        "share_save_mechanism": "Save por checklist aplicable; share porque nombra una tensión común en diseño.",
        "cta": "Guárdalo y comenta qué punto te falta trabajar.",
        "strategic_reason": "Educación visual sin fórmula genérica, con vocabulario propio.",
        "priority": "Alta",
        "linkedin_adaptation": "Documento corto: 5 preguntas de criterio para evaluar campañas visuales.",
    },
    {
        "title": "Cuenca como sistema visual, no como postal",
        "pillar": "DOMO ve el mundo",
        "format": "Reel con fotos de calle y texto editorial",
        "hook": "'Cuenca no es solo bonita. Cuenca tiene reglas visuales.'",
        "share_save_mechanism": "Share por identidad local; save por mapa de códigos visuales.",
        "cta": "Comenta qué ciudad debería leer después.",
        "strategic_reason": "Une territorio, cultura y dirección de arte de forma propia.",
        "priority": "Media",
        "linkedin_adaptation": "Caso de estudio sobre cómo leer una ciudad antes de construir una marca.",
    },
    {
        "title": "Una foto publicitaria no vende por verse limpia",
        "pillar": "Así pienso yo",
        "format": "Reel comparativo",
        "hook": "'La foto correcta no es la más perfecta. Es la que sostiene una tensión.'",
        "share_save_mechanism": "Save por criterio de producción; share entre fotógrafos, diseñadores y marcas.",
        "cta": "DM 'foto' si quieres revisar una imagen de tu marca.",
        "strategic_reason": "Conecta arte visual con consultoría creativa y producción comercial.",
        "priority": "Alta",
        "linkedin_adaptation": "Artículo breve sobre tensión visual en fotografía publicitaria.",
    },
    {
        "title": "El error de importar referencias sin traducirlas",
        "pillar": "Creatividad para todos",
        "format": "Carrusel editorial",
        "hook": "Portada: 'Pinterest no entiende tu barrio.'",
        "share_save_mechanism": "Share por frase memorable; save por método para adaptar referencias globales a contexto LATAM.",
        "cta": "Comenta una referencia que ves repetida en todos lados.",
        "strategic_reason": "Refuerza criterio internacional sin abandonar raíz local.",
        "priority": "Alta",
        "linkedin_adaptation": "Post sobre localización cultural en dirección creativa.",
    },
    {
        "title": "Branding que no empieza en el logo",
        "pillar": "Así pienso yo",
        "format": "Reel + pantalla de proceso",
        "hook": "'Si tu marca solo vive en el logo, todavía no tiene mundo.'",
        "share_save_mechanism": "Save por criterio de branding; share entre emprendedores y diseñadores que necesitan ordenar una marca.",
        "cta": "Comenta 'mundo' y te digo qué sistema visual le falta a una marca.",
        "strategic_reason": "Vende consultoría creativa sin sonar vendedor: muestra que DOMO piensa sistemas, no piezas sueltas.",
        "priority": "Alta",
        "linkedin_adaptation": "Post: por qué el branding se construye con tono, ritmo, foto, objeto, lenguaje y contexto.",
    },
    {
        "title": "Mockup no es decoración, es prueba de realidad",
        "pillar": "Creatividad para todos",
        "format": "Carrusel guardable",
        "hook": "Portada: 'Un mockup bonito puede mentirte.'",
        "share_save_mechanism": "Save por checklist para revisar mockups; share entre diseñadores que presentan marcas.",
        "cta": "Guárdalo antes de presentar tu próxima identidad.",
        "strategic_reason": "Convierte material de marca existente en educación útil y posiciona a DOMO como director creativo práctico.",
        "priority": "Alta",
        "linkedin_adaptation": "Documento LinkedIn: 6 preguntas para saber si un mockup realmente valida una marca.",
    },
    {
        "title": "Fotografía publicitaria con tensión, no con perfección",
        "pillar": "Así pienso yo",
        "format": "Reel comparativo / antes y después",
        "hook": "'La foto correcta no es la más limpia. Es la que hace que quieras mirar dos veces.'",
        "share_save_mechanism": "Save por método visual; share entre marcas que quieren verse mejor sin caer en foto genérica.",
        "cta": "DM 'foto' si quieres que revise una imagen de tu marca.",
        "strategic_reason": "Abre puerta directa a producción fotográfica, dirección de arte y campañas comerciales.",
        "priority": "Alta",
        "linkedin_adaptation": "Caso corto: cómo una decisión de luz, fondo u objeto cambia la percepción de una marca.",
    },
    {
        "title": "INHAUS: cómo se ve una marca cuando ya tiene carácter",
        "pillar": "DOMO ve el mundo",
        "format": "Reel editorial + carrusel de shots",
        "hook": "'Esto no es solo un local bonito. Es una marca comportándose en el mundo real.'",
        "share_save_mechanism": "Share por referencia aspiracional; save por breakdown de color, textura, encuadre y tono.",
        "cta": "Comenta qué detalle visual te hizo confiar en la marca.",
        "strategic_reason": "Usa material propio/aliado como caso de autoridad: DOMO lee y construye atmósferas comerciales.",
        "priority": "Alta",
        "linkedin_adaptation": "Post de caso: cómo una experiencia física puede convertirse en sistema visual para contenido.",
    },
    {
        "title": "Shots enteros: una campaña puede nacer de un solo encuadre",
        "pillar": "Así pienso yo",
        "format": "Reel de análisis visual",
        "hook": "'Este encuadre ya tiene campaña. Solo hay que saber leerlo.'",
        "share_save_mechanism": "Save por análisis de composición; share porque enseña a mirar mejor material existente.",
        "cta": "Mándame un shot y te digo qué historia visual tiene escondida.",
        "strategic_reason": "Ayuda a reutilizar material de marca y fotografía existente para producir más contenido con menos desgaste.",
        "priority": "Media",
        "linkedin_adaptation": "Post: cómo extraer narrativa de una fotografía de producto, espacio o persona.",
    },
    {
        "title": "LinkedIn sin corbata: criterio visual para marcas vivas",
        "pillar": "Creatividad para todos",
        "format": "Post de LinkedIn + carrusel documento",
        "hook": "'LinkedIn no tiene que sonar corporativo para vender criterio.'",
        "share_save_mechanism": "Save por estructura de post; share entre creativos que quieren vender sin perder voz.",
        "cta": "Comenta 'LinkedIn' y convierto una idea visual en post profesional.",
        "strategic_reason": "Activa LinkedIn como canal de leads para workshops, consultoría y colaboraciones.",
        "priority": "Alta",
        "linkedin_adaptation": "Publicarlo directamente como manifiesto práctico con ejemplo DOMO.",
    },
]


def load_system_prompt() -> str:
    if PROMPT_PATH.exists():
        return PROMPT_PATH.read_text(encoding="utf-8")
    return ""


def get_secret(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return value or os.getenv(name, default)


def summarize_context(posts: pd.DataFrame) -> dict:
    if posts.empty:
        return {}
    by_pillar = posts.groupby("pillar")[["share_rate", "save_rate", "quality_comment_rate", "profile_visit_rate"]].mean().round(2)
    by_format = posts.groupby("format")[["share_rate", "save_rate", "quality_comment_rate", "profile_visit_rate"]].mean().round(2)
    return {
        "best_pillars": by_pillar.sort_values("share_rate", ascending=False).to_dict(),
        "best_formats": by_format.sort_values("save_rate", ascending=False).to_dict(),
        "recent_titles": posts["title"].head(8).tolist(),
    }


def generate_with_openai(posts: pd.DataFrame, focus: str, platform: str, count: int) -> list[dict] | None:
    load_dotenv()
    api_key = get_secret("OPENAI_API_KEY", "")
    if not api_key:
        return None

    try:
        from openai import OpenAI
    except ImportError:
        return None

    client = OpenAI(api_key=api_key)
    system_prompt = load_system_prompt()
    context = summarize_context(posts)
    user_prompt = {
        "brand": "DOMO",
        "focus": focus,
        "platform": platform,
        "count": count,
        "context": context,
        "required_fields": [
            "title",
            "pillar",
            "format",
            "hook",
            "share_save_mechanism",
            "cta",
            "strategic_reason",
            "priority",
            "linkedin_adaptation",
        ],
    }

    try:
        response = client.chat.completions.create(
            model=get_secret("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_prompt, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"},
            temperature=0.8,
        )
        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        return parsed.get("ideas", [])
    except Exception as exc:
        st.warning("OpenAI no respondió ahora. Uso el banco local de ideas.")
        st.caption(f"Detalle técnico: {type(exc).__name__}")
        return None


def score_local_idea(idea: dict, focus: str, platform: str) -> int:
    score = 0
    text = " ".join(str(value).lower() for value in idea.values())
    if focus in text:
        score += 4
    if platform.lower() in text or platform == "Ambas":
        score += 2
    if idea["priority"] == "Alta":
        score += 2
    if "latam" in text or "calle" in text or "cultura" in text:
        score += 2
    return score


def generate_locally(focus: str, platform: str, count: int) -> list[dict]:
    ranked = sorted(
        LOCAL_IDEA_BANK,
        key=lambda idea: score_local_idea(idea, focus, platform),
        reverse=True,
    )
    return ranked[:count]


def generate_ideas(posts: pd.DataFrame, focus: str, platform: str, count: int = 6) -> list[dict]:
    ai_ideas = generate_with_openai(posts, focus, platform, count)
    if ai_ideas:
        return ai_ideas[:count]
    return generate_locally(focus, platform, count)
