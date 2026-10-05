#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migración ÚNICA de la "fase 2" (32 generaciones que sobrevivieron al
descarte de modelos, ver memory.md del standalone) hacia Supabase, para que
6 sujetos de prueba nuevos (Nuria, Diana, Kiomi, David, Cielo, Paty) puedan
calificar ese mismo set de 32 piezas, cada uno de forma independiente.

Corrida a mano, una sola vez, por vos (no por Claude): necesita la
`service_role` key, que nunca debe pegarse en el chat ni commitearse.

Uso:
    export SUPABASE_URL="https://hngerqczhaclswpiascp.supabase.co"
    export SUPABASE_SERVICE_ROLE_KEY="sb_secret_..."   # Settings -> API
    python migrar_fase2_a_supabase.py

Requiere: pip install requests

IMPORTANTE — seguridad de los datos ya existentes (Victor/Julio, ids
1-192, ya calificados): este script SOLO hace INSERT de ids 193-384,
que nunca existieron antes en la tabla. No hace ningún UPDATE ni DELETE
sobre ningún id existente, así que es imposible que toque una fila de
Victor o Julio aunque se corra más de una vez (el conflicto de
`merge-duplicates` solo puede chocar con un id que YA insertó este mismo
script antes, nunca con 1-192).

Qué hace:
  1. NO sube ninguna imagen nueva — las 32 piezas de la fase 2 son un
     SUBCONJUNTO de las 96 originales (ids 1-96), cuyas imágenes ya están
     subidas al bucket "piezas" desde la migración original. Solo arma las
     URLs públicas que ya existen.
  2. Inserta 192 filas nuevas (32 piezas x 6 sujetos) en la tabla
     `generaciones`, ids 193 a 384, con `calificacion_texto`/
     `calificacion_imagen` en NULL (sin calificar todavía).

Nada de esto toca `resultados/` del standalone local — es de solo lectura.
"""

import csv
import json
import os
import sys
from datetime import datetime

import requests

# --- Config: ruta al standalone local (ya generado, nunca se modifica) ----
RUTA_STANDALONE = r"C:\Users\Diego\Downloads\standaloneDemoStudio\resultados"
RUTA_CSV = os.path.join(RUTA_STANDALONE, "registro_costos.csv")
RUTA_PIEZAS = os.path.join(RUTA_STANDALONE, "Piezas")

# Las 32 piezas de la fase 2, en el mismo orden que `generaciones_fase2.csv`
# (ids ORIGINALES 1-96, recuperados emparejando por `modelo_verso` +
# `modelo_lumina` contra `registro_costos.csv` — ese csv de fase 2 había
# renumerado sus propios ids de 1 a 32, perdiendo el id original; se
# recalculó una sola vez y se verificó cruzando el costo_total de cada fila,
# 0 colisiones, 32/32 emparejadas).
IDS_ORIGINALES_FASE2 = [
    3, 4, 6, 8, 12, 13, 14, 18, 20, 26, 27, 29, 34, 38, 41, 45,
    48, 52, 53, 57, 59, 65, 67, 70, 71, 73, 77, 83, 88, 90, 91, 92,
]
assert len(IDS_ORIGINALES_FASE2) == 32

# Bloques de 32 ids nuevos por sujeto de prueba, exactos como los pidió el usuario.
SUJETOS_FASE2 = [
    ("Nuria", 193),
    ("Diana", 225),
    ("Kiomi", 257),
    ("David", 289),
    ("Cielo", 321),
    ("Paty", 353),
]

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_URL or not SERVICE_ROLE_KEY:
    print("Faltan SUPABASE_URL y/o SUPABASE_SERVICE_ROLE_KEY como variables de entorno.")
    print("Ver el docstring de este archivo para el uso exacto.")
    sys.exit(1)

HEADERS_TABLA = {
    "apikey": SERVICE_ROLE_KEY,
    "Authorization": "Bearer " + SERVICE_ROLE_KEY,
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates,return=minimal",
}


def url_publica_storage(ruta_en_bucket):
    return "%s/storage/v1/object/public/piezas/%s" % (SUPABASE_URL, ruta_en_bucket)


def main():
    with open(RUTA_CSV, encoding="utf-8") as f:
        filas_por_id = {int(r["id"]): r for r in csv.DictReader(f)}

    for id_original in IDS_ORIGINALES_FASE2:
        assert id_original in filas_por_id, "falta el id original %d en registro_costos.csv" % id_original

    fecha_hora_nueva = datetime.now().strftime("%Y-%m-%d %H-%M-%S")

    filas_para_insertar = []
    for nombre_sujeto, id_base in SUJETOS_FASE2:
        for offset, id_original in enumerate(IDS_ORIGINALES_FASE2):
            id_nuevo = id_base + offset
            fila = filas_por_id[id_original]

            with open(os.path.join(RUTA_PIEZAS, "%s.json" % id_original), encoding="utf-8") as f:
                piece = json.load(f)
            pieza_jsonb = {
                "tag": piece.get("tag"), "head": piece.get("head"), "sub": piece.get("sub"),
                "cta": piece.get("cta"), "wa": piece.get("wa"), "shade": piece.get("shade"),
                "photoPos": piece.get("photoPos"),
            }

            filas_para_insertar.append({
                "id": id_nuevo,
                "fecha_hora": fecha_hora_nueva,
                "modelo_verso": fila["modelo_verso"],
                "modelo_atelier": fila["modelo_atelier"],
                "modelo_lumina": fila["modelo_lumina"],
                "input_verso": int(fila["input_verso"] or 0),
                "output_verso": int(fila["output_verso"] or 0),
                "input_atelier": int(fila["input_atelier"] or 0),
                "output_atelier": int(fila["output_atelier"] or 0),
                "input_lumina": int(fila["input_lumina"] or 0),
                "output_lumina": int(fila["output_lumina"] or 0),
                "costo_verso": float(fila["costo_verso"] or 0),
                "costo_atelier": float(fila["costo_atelier"] or 0),
                "costo_lumina_4x5": float(fila["costo_lumina_4x5"] or 0),
                "costo_lumina_16x9": float(fila["costo_lumina_16x9"] or 0),
                "costo_total_4x5": float(fila["costo_total_4x5"] or 0),
                "costo_total_16x9": float(fila["costo_total_16x9"] or 0),
                "costo_total": float(fila["costo_total"] or 0),
                "tiempo_generacion": float(fila["tiempo_generacion"] or 0),
                "calificacion_texto": None,
                "calificacion_imagen": None,
                "pieza": pieza_jsonb,
                "composicion_url": url_publica_storage("composiciones/%s.jpg" % id_original),
                "foto_4x5_url": url_publica_storage("4x5/%s.jpg" % id_original),
                "foto_16x9_url": url_publica_storage("16x9/%s.jpg" % id_original),
            })

        print("%-6s -> ids %d a %d (sin calificar)" % (nombre_sujeto, id_base, id_base + 31))

    print("\nTotal de filas nuevas a insertar:", len(filas_para_insertar))
    assert len(filas_para_insertar) == 192

    resp = requests.post(
        "%s/rest/v1/generaciones" % SUPABASE_URL,
        headers=HEADERS_TABLA,
        data=json.dumps(filas_para_insertar, ensure_ascii=False),
        timeout=60,
    )
    if resp.status_code not in (200, 201, 204):
        raise RuntimeError("insert falló (%d): %s" % (resp.status_code, resp.text[:500]))

    print("192 filas nuevas insertadas (ids 193-384) en `generaciones`.")
    print("Ids 1-192 (Victor/Julio) no fueron tocados por este script.")


if __name__ == "__main__":
    main()
