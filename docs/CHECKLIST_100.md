# Checklist para dejar DOMO Content Lab al 100%

Esto es lo que falta para que funcione desde cualquier lugar, con IA y datos reales.

## Lo que ya está listo

- App Streamlit móvil-first.
- Login por contraseña.
- Dashboard y Data Center.
- Capturas y registro histórico.
- Asistente DOMO.
- Ideas con IA o respaldo local.
- Radar de trends web.
- Collabs y marcas sugeridas.
- Generador de carruseles alimentado por links.
- Archivos para Streamlit Cloud y Render.
- `.streamlit/secrets.toml.example` para configurar secretos.

## Lo que necesito de ti

### 1. GitHub

Necesito que el proyecto esté en un repositorio de GitHub.

Si me das acceso con el conector de GitHub, puedo ayudarte a subirlo. Si no, tú puedes crear el repo y subir la carpeta.

### 2. Streamlit Community Cloud

Necesitas una cuenta en Streamlit Community Cloud conectada a GitHub.

Ahí se despliega la app gratis para abrirla desde cualquier lugar.

### 3. Clave privada de la app

Define una clave para entrar:

```text
APP_PASSWORD=una-clave-fuerte
```

### 4. OpenAI API key

Para que el asistente piense con IA real:

```text
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini
OPENAI_VISION_MODEL=gpt-4o-mini
```

Sin esto, la app funciona con lógica local, pero no analiza con tanta profundidad.

### 5. Instagram oficial

Para alimentar datos casi automático necesitas:

- Cuenta Instagram Creator o Business.
- Conexión con una página de Facebook.
- App en Meta Developers.
- Permisos de lectura aprobados.
- Token de acceso.

Variables:

```text
INSTAGRAM_ACCESS_TOKEN=...
INSTAGRAM_BUSINESS_ACCOUNT_ID=...
```

### 6. Base persistente

Para prototipo puede usar SQLite.

Para producción seria recomiendo Supabase/Postgres, porque en nube gratis los archivos locales pueden perderse al reiniciar.

## Orden recomendado

1. Subir a GitHub.
2. Desplegar en Streamlit Community Cloud.
3. Configurar `APP_PASSWORD`.
4. Configurar `OPENAI_API_KEY`.
5. Probar desde celular.
6. Migrar datos a Supabase.
7. Conectar Instagram Graph API.
8. Programar refresco automático.

## Lo que no debe hacerse

- No poner usuario/contraseña de Instagram en la app.
- No hacer scraping agresivo.
- No publicar la app sin clave.
- No subir capturas sensibles si la app no tiene login.
