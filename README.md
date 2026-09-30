# Verne Studio · Yanbal — Calificación (Victor / Julio)

Sitio de despliegue (Vercel + Supabase) para que 2 sujetos de prueba califiquen,
de forma independiente, el mismo set de piezas ya generado por el standalone
local (`registro_costos.csv` / imágenes) — sin volver a generar nada acá.

## Estructura

- `index.html` — el sitio en sí (estático, sin build step). Reusa la lógica de
  composición en vivo/selector de formato/panel de costos del standalone local
  (`generar.html`), hablando con Supabase (`supabase-js`) en vez de con Flask.
- `supabase/schema.sql` — tabla `generaciones`, vista `comparacion_modelos`,
  función `calificar_pieza()` (única forma de escribir), bucket `piezas`.
- `scripts/migrar_a_supabase.py` — migración única de lo ya generado localmente
  (imágenes + CSV) hacia Supabase. No vuelve a llamar a ningún modelo de IA.

## Pasos para dejarlo funcionando (una sola vez)

1. **Pegar `supabase/schema.sql` completo en el SQL Editor de Supabase** y
   correrlo — no necesita la contraseña de la base de datos, el SQL Editor ya
   corre con tu propia sesión.
2. **Correr la migración**, con la `service_role` key puesta como variable de
   entorno local (nunca commiteada, nunca en el chat):
   ```
   pip install -r scripts/requirements.txt
   set SUPABASE_URL=https://hngerqczhaclswpiascp.supabase.co
   set SUPABASE_SERVICE_ROLE_KEY=sb_secret_...   (Settings -> API, en Supabase)
   python scripts/migrar_a_supabase.py
   ```
   Sube las 96 imágenes únicas a Storage (Victor y Julio comparten el mismo
   archivo, no se duplican bytes) e inserta las 192 filas en `generaciones`.
3. **Deploy en Vercel** — `index.html` es estático, no necesita build ni
   variables de entorno (la URL y la `publishable key` de Supabase, seguras de
   estar en el código, ya están adentro de `index.html`).
