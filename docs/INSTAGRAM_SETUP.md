# Instagram API para DOMO Content Lab

La app usa Instagram Graph API en modo solo lectura. No publica, no responde mensajes y no comenta.

## Secrets necesarios

En Streamlit Cloud, abre:

`Manage app` -> `Settings` -> `Secrets`

Necesitas estas dos variables:

```toml
INSTAGRAM_ACCESS_TOKEN = "tu-token"
INSTAGRAM_BUSINESS_ACCOUNT_ID = "tu-instagram-business-account-id"
```

## Permisos que debe tener el token

Para leer posts e insights, el token debe venir de una app Meta con permisos de lectura para Instagram profesional. Normalmente necesitas permisos como:

- `instagram_basic`
- `instagram_manage_insights`
- `pages_show_list`
- `pages_read_engagement`

Meta puede cambiar nombres o requisitos segun el tipo de app/cuenta.

## Uso dentro de la app

1. Entra a `Admin`.
2. Presiona `Probar conexion Instagram`.
3. Si conecta, presiona `Actualizar metricas de Instagram`.
4. La app lee los posts recientes, trae insights disponibles y los guarda en Supabase.

## Notas importantes

- Algunas metricas no existen para todos los formatos. Por ejemplo, Reels, fotos y carruseles no siempre devuelven exactamente los mismos campos.
- `Comentarios de calidad` se estima con una fraccion de comentarios totales hasta que conectemos lectura/analisis de comentarios.
- Si Meta devuelve errores por permisos, hay que revisar el token en Meta Developer / Graph API Explorer.
