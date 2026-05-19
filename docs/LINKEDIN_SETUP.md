# Conectar LinkedIn

LinkedIn es más cerrado que Instagram. La app puede leer métricas si el token tiene permisos de analítica para creadores.

## Secrets

En Streamlit Cloud, agrega:

```toml
LINKEDIN_ACCESS_TOKEN = "pega-aqui-tu-token"
LINKEDIN_VERSION = "202605"
```

No pegues el token en chats ni capturas.

## Permisos que buscamos

Para métricas de contenido de perfil:

```text
r_member_postAnalytics
r_member_profileAnalytics
```

Si LinkedIn no aprueba esos permisos, la app igual puede funcionar con:

- capturas de pantalla,
- carga manual de métricas,
- ideas y carruseles adaptados a LinkedIn,
- historial en Supabase.

## Dentro de la app

1. Entra a `Admin`.
2. Baja a `LinkedIn API`.
3. Haz clic en `Probar conexión LinkedIn`.
4. Si conecta, haz clic en `Actualizar métricas de LinkedIn`.

La app guardará un snapshot de LinkedIn en `Posts` para compararlo con Instagram.

## Qué mide cuando LinkedIn lo permite

- impresiones,
- miembros alcanzados,
- reacciones,
- comentarios,
- republicaciones,
- guardados,
- envíos,
- clics,
- visitas al perfil desde contenido.

LinkedIn puede bloquear algunas métricas según el tipo de cuenta, permisos o revisión de la app.
