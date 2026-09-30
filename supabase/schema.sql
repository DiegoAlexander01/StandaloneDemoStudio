-- Verne Studio · Yanbal — esquema de Supabase para la galería de calificación
-- (Victor 1-96 / Julio 97-192, ver memory.md del standalone local §23).
--
-- Cómo usarlo: pegar TODO este archivo en el SQL Editor de Supabase
-- (dashboard → SQL Editor → New query) y correrlo una sola vez.
--
-- No requiere la contraseña de la base de datos ni la service_role key acá
-- — el SQL Editor ya corre autenticado con tu propia cuenta de Supabase.

-- =========================================================================
-- 1. Tabla oficial (equivalente a resultados/registro_costos.csv)
-- =========================================================================
create table if not exists public.generaciones (
  id integer primary key,
  fecha_hora text not null,
  modelo_verso text not null,
  modelo_atelier text not null,
  modelo_lumina text not null,
  input_verso integer not null default 0,
  output_verso integer not null default 0,
  input_atelier integer not null default 0,
  output_atelier integer not null default 0,
  input_lumina integer not null default 0,
  output_lumina integer not null default 0,
  costo_verso numeric not null default 0,
  costo_atelier numeric not null default 0,
  costo_lumina_4x5 numeric not null default 0,
  costo_lumina_16x9 numeric not null default 0,
  costo_total_4x5 numeric not null default 0,
  costo_total_16x9 numeric not null default 0,
  costo_total numeric not null default 0,
  tiempo_generacion numeric not null default 0,
  calificacion_texto integer,
  calificacion_imagen integer,
  -- Texto completo de la pieza (equivalente a Piezas/<id>.json):
  -- {tag, head, sub, cta, wa, shade, photoPos}
  pieza jsonb not null,
  -- URLs públicas de Supabase Storage (equivalentes a los PNG servidos por
  -- Flask en el standalone local) — se llenan en la migración.
  composicion_url text,
  foto_4x5_url text,
  foto_16x9_url text,
  constraint calificacion_texto_rango
    check (calificacion_texto is null or calificacion_texto between 0 and 10),
  constraint calificacion_imagen_rango
    check (calificacion_imagen is null or calificacion_imagen between 0 and 10)
);

comment on table public.generaciones is
  'Equivalente a resultados/registro_costos.csv del standalone local. Ids 1-96
   = set de Victor, 97-192 = mismo set duplicado para Julio (ver memory.md §23
   del standalone). Cada id es independiente para calificar.';

-- =========================================================================
-- 2. Vista derivada (equivalente a resultados/comparacion_modelos.csv) —
--    "opción B": nunca se escribe, se calcula sola en cada consulta a partir
--    de `generaciones` (única fuente de verdad) — nunca puede desincronizarse.
-- =========================================================================
create or replace view public.comparacion_modelos
with (security_invoker = true) as
select id, modelo_verso, modelo_atelier, modelo_lumina,
       costo_verso, costo_atelier, costo_lumina_4x5, costo_lumina_16x9,
       tiempo_generacion, costo_total,
       calificacion_texto, calificacion_imagen
from public.generaciones
order by id;

-- =========================================================================
-- 3. Acceso — no hay login (link privado compartido con Victor y Julio):
--    lectura pública de todo, escritura SOLO a través de la función de abajo
--    (nunca UPDATE directo por REST, para que nadie pueda reescribir costos
--    o modelos, solo las 2 columnas de calificación).
-- =========================================================================
alter table public.generaciones enable row level security;

drop policy if exists "lectura_publica" on public.generaciones;
create policy "lectura_publica" on public.generaciones
  for select
  to anon
  using (true);

grant select on public.generaciones to anon;
grant select on public.comparacion_modelos to anon;

-- =========================================================================
-- 4. Función para calificar (única forma de escribir) — valida 0-10 y
--    actualiza SOLO calificacion_texto/calificacion_imagen de un id que ya
--    existe. `security definer` = corre con permisos de quien la creó, así
--    que puede hacer el UPDATE aunque no haya política de UPDATE para `anon`.
-- =========================================================================
create or replace function public.calificar_pieza(
  p_id integer,
  p_calificacion_texto integer,
  p_calificacion_imagen integer
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  if p_calificacion_texto is null or p_calificacion_texto < 0 or p_calificacion_texto > 10 then
    raise exception 'calificacion_texto debe ser un número entre 0 y 10';
  end if;
  if p_calificacion_imagen is null or p_calificacion_imagen < 0 or p_calificacion_imagen > 10 then
    raise exception 'calificacion_imagen debe ser un número entre 0 y 10';
  end if;

  update public.generaciones
     set calificacion_texto = p_calificacion_texto,
         calificacion_imagen = p_calificacion_imagen
   where id = p_id;

  if not found then
    raise exception 'no existe una generación con id=%', p_id;
  end if;
end;
$$;

grant execute on function public.calificar_pieza(integer, integer, integer) to anon;

-- =========================================================================
-- 5. Bucket de Storage para las imágenes (público de solo lectura — la
--    subida real la hace el script de migración con la service_role key,
--    que bypassea esto). Mismos 3 "subdirectorios" que ya usa el standalone
--    local: composiciones/, 4x5/, 16x9/ — nombrados por el id ORIGINAL
--    1-96 (Victor e Julio comparten el mismo archivo físico, ver memory.md
--    §23 y el script de migración).
-- =========================================================================
insert into storage.buckets (id, name, public)
values ('piezas', 'piezas', true)
on conflict (id) do nothing;
