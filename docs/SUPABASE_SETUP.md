# Supabase para DOMO Content Lab

Supabase es la memoria en la nube de la app. Sin esto, Streamlit puede reiniciar y perder registros recientes. Con esto, lo que guardes desde el celular, oficina o compu queda en una base online.

## Paso 1: crear las tablas

1. En Supabase abre tu proyecto `DOMO CONTENT`.
2. En el menu izquierdo entra a `SQL Editor`.
3. Crea una consulta nueva.
4. Pega todo el contenido del archivo `supabase_schema.sql`.
5. Presiona `Run`.

## Paso 2: copiar la clave correcta

1. En Supabase entra a `Settings`.
2. Abre `API Keys`.
3. Copia la key llamada `service_role`.
4. No pegues esa key en chats ni la compartas. Va solo en Streamlit Secrets.

## Paso 3: agregar secrets en Streamlit

En Streamlit Cloud entra a:

`Manage app` -> `Settings` -> `Secrets`

Agrega estas lineas, manteniendo tambien tu `OPENAI_API_KEY`:

```toml
SUPABASE_PROJECT_ID = "gccbondkipsqgakduokf"
SUPABASE_URL = "https://gccbondkipsqgakduokf.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "pega-aqui-tu-service-role-key"
```

Guarda y reinicia la app.

## Paso 4: comprobar

Abre la app, entra a `Admin` y revisa `Datos persistentes`.

Debe decir `Supabase conectado`.

Si aun dice `SQLite local`, casi siempre falta una de estas tres cosas:

- no corriste el SQL
- falta la `SUPABASE_SERVICE_ROLE_KEY`
- Streamlit no reinicio despues de guardar los secrets
