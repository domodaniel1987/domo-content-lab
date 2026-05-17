# DOMO Content Lab

Dashboard local para analizar contenido de Instagram y LinkedIn con mirada estratégica DOMO.

La app no publica contenido, no envía mensajes y no automatiza interacción. Solo lee datos, guarda cache local y ayuda a decidir qué crear.

## Qué incluye

- Dashboard en Streamlit con tabs para:
  - Resumen
  - Tendencias
  - Audiencia
  - Posts
  - Capturas
  - Cuándo publicar
  - Ideas
  - Carruseles
  - Inspiración
  - Asistente
  - Monetización
- Base local SQLite en `data.nosync/`
- Cache privado fuera de git
- Gráficos con Plotly
- Generador de ideas DOMO con IA si hay API key
- Generador local de respaldo si no hay API key
- Filtros para comentarios y DMs triviales
- Registro histórico de capturas y métricas manuales
- Asistente interno para analizar links, capturas y decisiones de contenido
- Generador de carruseles con frases DOMO alimentado por links guardados

## Instalación simple

1. Crear entorno:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Instalar dependencias:

```bash
pip install -r requirements.txt
```

3. Crear tu archivo de configuración:

```bash
cp .env.example .env
```

4. Abrir la app:

```bash
streamlit run app.py
```

O más simple:

```bash
python launch.py
```

En Mac también puedes abrir:

```text
abrir_domo_content_lab.command
```

Ese archivo prepara el entorno si hace falta y abre el sistema.

## Datos

La primera vez, el proyecto crea datos de muestra en:

```text
data.nosync/domo_content_lab.sqlite
```

Cuando conectes APIs, `refresh.py` será el punto de entrada para traer datos nuevos en modo solo lectura.

```bash
python refresh.py
```

## Capturas y avance

En la pestaña `Capturas` puedes:

- Subir capturas de estadísticas.
- Registrar manualmente alcance, likes, comentarios, shares, guardados, visitas al perfil y clicks/DMs útiles.
- Guardar una nota sobre lo que sentiste que funcionó o no.
- Pedir una lectura con IA si tienes `OPENAI_API_KEY`.

Todo se guarda localmente en:

```text
data.nosync/
```

Eso permite ir creando un récord histórico para ver avance real.

## Links e inspiración

En la pestaña `Inspiración` puedes pegar un link de algo que te parezca chévere.

La app intenta leerlo y convertirlo en una sugerencia al estilo DOMO:

- Angulo propio
- Formato recomendado
- Hook
- Mecanismo de share/save
- CTA
- Adaptación estratégica

La idea no es copiar referencias, sino traducirlas a tu mundo: Cuenca, cultura visual LATAM, gráfica popular, dirección de arte y criterio creativo.

## Carruseles

En la pestaña `Carruseles` puedes:

- Escribir una frase o idea inicial.
- Usar un link guardado como fuente.
- Elegir objetivo: saves, shares, comentarios, leads o autoridad.
- Generar slides con frase, nota visual, caption y CTA.

Esto está pensado para carruseles guardables y compartibles, no frases genéricas.

## Asistente DOMO

En la pestaña `Asistente` puedes escribir preguntas como:

```text
Qué debería publicar esta semana para crecer en shares y conseguir colaboraciones?
```

Si hay API key, responde con IA usando tu historial. Si no hay API key, responde con una estrategia local de respaldo.

## IA para ideas

Si agregas `OPENAI_API_KEY` en `.env`, la pestaña Ideas, Capturas, Inspiración y Asistente pueden usar IA con el prompt:

```text
prompts/domo_ideas_system.md
```

Si no agregas API key, la app igual funciona con un banco local de ideas estratégicas.

## Abrir en el celular

1. Deja la app corriendo en tu computadora con `python launch.py` o `abrir_domo_content_lab.command`.
2. Conecta tu celular al mismo Wi-Fi.
3. Mira la barra lateral del dashboard: ahí aparece una dirección parecida a `http://192.168.x.x:8501`.
4. Abre esa dirección en el navegador del celular.
5. Usa "Agregar a pantalla de inicio" para abrirlo como si fuera una app.

Para uso fuera de tu Wi-Fi habría que publicarlo en un servidor privado o usar una conexión segura tipo túnel. No lo hice por defecto porque aquí estamos cuidando datos privados.

## Uso diario recomendado

Ver:

```text
docs/USO_DIARIO.md
```

La idea es usarlo como un registro vivo: cada captura, link, insight y pregunta al asistente alimenta el sistema.

## Usarlo desde cualquier lugar

Ver:

```text
docs/DESPLIEGUE_CELULAR.md
```

Para celular desde cualquier red hace falta desplegarlo en la nube. Localmente solo funciona en la misma red Wi-Fi.

## Checklist 100%

Ver:

```text
docs/CHECKLIST_100.md
```

Ahí está lo que falta para dejarlo online, con login, IA y datos reales.

## Variables de entorno

Ver `.env.example`.

## Enfoque estratégico

El dashboard prioriza señales que ayudan a crecer en:

- Shares
- Saves
- Comentarios de calidad
- Visitas al perfil
- Leads para workshops, consultoría creativa y colaboraciones

La regla central: no generar contenido genérico. Cada idea debe fortalecer a DOMO como referente visual LATAM con criterio creativo internacional.
