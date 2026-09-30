#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migración ÚNICA de lo ya generado localmente (standalone/resultados/) hacia
Supabase — no vuelve a llamar a ningún modelo de IA, solo sube lo que ya
existe. Corrida a mano, una sola vez, por vos (no por Claude): necesita la
`service_role` key, que nunca debe pegarse en el chat ni commitearse.

Uso:
    export SUPABASE_URL="https://hngerqczhaclswpiascp.supabase.co"
    export SUPABASE_SERVICE_ROLE_KEY="sb_secret_..."   # Settings -> API
    python migrar_a_supabase.py

Requiere: pip install requests
Requiere que ya hayas corrido supabase/schema.sql en el SQL Editor antes.

Qué hace:
  1. Sube las 3 imágenes de cada una de las 96 piezas ORIGINALES (ids 1-96)
     al bucket "piezas" (composiciones/, 4x5/, 16x9/) — Victor y Julio, en la
     tabla, apuntan al MISMO archivo subido (id % 96), así no se duplican
     ~280 MB de bytes en Storage sin necesidad (ver memory.md §23 del
     standalone: los archivos locales 1-96 y 97-192 ya son bytes idénticos).
  2. Inserta las 192 filas en la tabla `generaciones` (upsert: se puede
     correr de nuevo sin duplicar si algo falla a mitad de camino).

Nada de esto toca `resultados/` del standalone local — es de solo lectura.
"""

import csv
import json
import os
import sys

import requests

# --- Config: ruta al standalone local (ya generado, nunca se modifica) ----
RUTA_STANDALONE = r"C:\Users\Diego\Downloads\standaloneDemoStudio\resultados"
RUTA_CSV = os.path.join(RUTA_STANDALONE, "registro_costos.csv")
RUTA_PIEZAS = os.path.join(RUTA_STANDALONE, "Piezas")
RUTA_COMPOSICIONES = os.path.join(RUTA_STANDALONE, "Composiciones_Atelier")
RUTA_FOTOS = os.path.join(RUTA_STANDALONE, "Fotos_Lumina")

TOTAL_UNICAS = 96          # ids 1-96 son las imágenes reales, únicas
OFFSET_SUJETO_2 = 96       # 97-192 reusan las mismas imágenes que 1-96

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_URL or not SERVICE_ROLE_KEY:
    print("Faltan SUPABASE_URL y/o SUPABASE_SERVICE_ROLE_KEY como variables de entorno.")
    print("Ver el docstring de este archivo para el uso exacto.")
    sys.exit(1)

HEADERS_STORAGE = {
    "apikey": SERVICE_ROLE_KEY,
    "Authorization": "Bearer " + SERVICE_ROLE_KEY,
}
HEADERS_TABLA = {
    "apikey": SERVICE_ROLE_KEY,
    "Authorization": "Bearer " + SERVICE_ROLE_KEY,
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates,return=minimal",
}


def url_publica_storage(ruta_en_bucket):
    return "%s/storage/v1/object/public/piezas/%s" % (SUPABASE_URL, ruta_en_bucket)


def subir_archivo(ruta_local, ruta_en_bucket):
    """Sube (o sobreescribe, x-upsert) un archivo al bucket 'piezas'."""
    with open(ruta_local, "rb") as f:
        contenido = f.read()
    resp = requests.post(
        "%s/storage/v1/object/piezas/%s" % (SUPABASE_URL, ruta_en_bucket),
        headers={**HEADERS_STORAGE, "Content-Type": "image/png", "x-upsert": "true"},
        data=contenido,
        timeout=60,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError("subida de %s falló (%d): %s" % (ruta_en_bucket, resp.status_code, resp.text[:300]))


def main():
    with open(RUTA_CSV, encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    print("filas leídas del CSV local:", len(filas))
    assert len(filas) == 192, "se esperaban 192 filas (96 + 96 duplicadas), hay %d" % len(filas)

    # --- 1. Subir las 96 imágenes únicas ----------------------------------
    print("\n== Subiendo imágenes (solo ids 1-%d, únicas) ==" % TOTAL_UNICAS)
    for id_ in range(1, TOTAL_UNICAS + 1):
        subir_archivo(os.path.join(RUTA_COMPOSICIONES, "%s.png" % id_), "composiciones/%s.png" % id_)
        subir_archivo(os.path.join(RUTA_FOTOS, "4x5", "%s.png" % id_), "4x5/%s.png" % id_)
        subir_archivo(os.path.join(RUTA_FOTOS, "16x9", "%s.png" % id_), "16x9/%s.png" % id_)
        print("  id=%d OK" % id_, end="\r")
    print("\n96 x 3 imágenes subidas.")

    # --- 2. Armar e insertar las 192 filas ---------------------------------
    print("\n== Insertando 192 filas en la tabla `generaciones` ==")
    filas_para_insertar = []
    for fila in filas:
        id_ = int(fila["id"])
        id_original = ((id_ - 1) % TOTAL_UNICAS) + 1  # 97 -> 1, 192 -> 96, etc.

        with open(os.path.join(RUTA_PIEZAS, "%s.json" % id_original), encoding="utf-8") as f:
            piece = json.load(f)
        pieza_jsonb = {
            "tag": piece.get("tag"), "head": piece.get("head"), "sub": piece.get("sub"),
            "cta": piece.get("cta"), "wa": piece.get("wa"), "shade": piece.get("shade"),
            "photoPos": piece.get("photoPos"),
        }

        filas_para_insertar.append({
            "id": id_,
            "fecha_hora": fila["fecha_hora"],
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
            "calificacion_texto": int(fila["calificacion_texto"]) if (fila.get("calificacion_texto") or "").strip() else None,
            "calificacion_imagen": int(fila["calificacion_imagen"]) if (fila.get("calificacion_imagen") or "").strip() else None,
            "pieza": pieza_jsonb,
            "composicion_url": url_publica_storage("composiciones/%s.png" % id_original),
            "foto_4x5_url": url_publica_storage("4x5/%s.png" % id_original),
            "foto_16x9_url": url_publica_storage("16x9/%s.png" % id_original),
        })

    resp = requests.post(
        "%s/rest/v1/generaciones" % SUPABASE_URL,
        headers=HEADERS_TABLA,
        data=json.dumps(filas_para_insertar, ensure_ascii=False),
        timeout=60,
    )
    if resp.status_code not in (200, 201, 204):
        raise RuntimeError("insert falló (%d): %s" % (resp.status_code, resp.text[:500]))

    print("192 filas insertadas (o actualizadas, si ya existían) en `generaciones`.")
    print("\nMigración completa.")


if __name__ == "__main__":
    main()
