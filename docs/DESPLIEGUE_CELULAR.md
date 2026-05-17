# Despliegue para usar desde cualquier lugar

Objetivo: abrir DOMO Content Lab desde celular, oficina o cualquier red.

## Mejor camino gratis para empezar

Usar Streamlit Community Cloud.

Ventajas:
- Gratis.
- Funciona con celular desde cualquier lugar.
- Es el camino más rápido para probar la app real.

Punto importante:
- La base SQLite local puede no ser persistente en una nube gratuita.
- Para guardar capturas, historial y datos reales de forma seria, conviene conectar una base persistente como Supabase.

## Arquitectura recomendada

Primera versión:
- Streamlit Community Cloud
- OpenAI API key en secrets
- Sin datos demasiado sensibles
- Registro manual y capturas de prueba

Versión seria:
- Streamlit Cloud o Render
- Login
- Supabase Postgres para datos persistentes
- Almacenamiento privado para capturas
- Instagram Graph API en modo solo lectura
- Scheduler para refrescar métricas

## Por qué no Netlify

Netlify es excelente para sitios estáticos.

DOMO Content Lab necesita:
- Python
- Streamlit
- Base de datos
- Procesos de refresco
- IA

Por eso conviene Streamlit Cloud, Render o un servidor privado.

## Lo que falta para producción

1. Subir el proyecto a GitHub.
2. Crear app en Streamlit Community Cloud.
3. Configurar variables secretas:
   - `APP_PASSWORD`
   - `OPENAI_API_KEY`
   - `OPENAI_MODEL`
   - `INSTAGRAM_ACCESS_TOKEN`
4. Probar login.
5. Migrar de SQLite local a Supabase si quieres historial permanente.
6. Conectar Instagram Graph API en solo lectura.

Ver también:

```text
docs/CHECKLIST_100.md
```

## Regla de privacidad

No subir capturas sensibles ni estrategia comercial privada a una app pública sin login.
