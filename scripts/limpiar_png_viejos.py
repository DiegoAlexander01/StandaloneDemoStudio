#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Borra los 96 x 3 = 288 archivos .png viejos del bucket "piezas" en Supabase
Storage, que quedaron huérfanos tras migrar a .jpg (ver memory.md §24 del
standalone). La tabla `generaciones` ya apunta solo a .jpg desde que se
volvió a correr migrar_a_supabase.py — esto solo libera espacio en Storage.

Corrida a mano, una sola vez, por vos (no por Claude): necesita la
`service_role` key, que nunca debe pegarse en el chat ni commitearse.

Uso:
    export SUPABASE_URL="https://hngerqczhaclswpiascp.supabase.co"
    export SUPABASE_SERVICE_ROLE_KEY="sb_secret_..."   # Settings -> API
    python limpiar_png_viejos.py

Requiere: pip install requests

Por qué NO por SQL Editor: borrar filas de storage.objects a mano por SQL
solo borra el metadato del catálogo, no el archivo real en el backend de
Storage -- queda el blob huérfano igual. El borrado real tiene que pasar por
la API de Storage (este script), la misma que usa migrar_a_supabase.py para
subir.
"""

import os
import sys

import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_URL or not SERVICE_ROLE_KEY:
    print("Faltan SUPABASE_URL y/o SUPABASE_SERVICE_ROLE_KEY como variables de entorno.")
    print("Ver el docstring de este archivo para el uso exacto.")
    sys.exit(1)

HEADERS = {
    "apikey": SERVICE_ROLE_KEY,
    "Authorization": "Bearer " + SERVICE_ROLE_KEY,
    "Content-Type": "application/json",
}

TOTAL_UNICAS = 96
CARPETAS = ["composiciones", "4x5", "16x9"]


def main():
    rutas = [
        "%s/%s.png" % (carpeta, id_)
        for carpeta in CARPETAS
        for id_ in range(1, TOTAL_UNICAS + 1)
    ]
    print("Borrando %d archivos .png viejos del bucket 'piezas'..." % len(rutas))

    resp = requests.delete(
        "%s/storage/v1/object/piezas" % SUPABASE_URL,
        headers=HEADERS,
        json={"prefixes": rutas},
        timeout=60,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError("borrado falló (%d): %s" % (resp.status_code, resp.text[:500]))

    borrados = resp.json()
    print("Borrados: %d de %d solicitados." % (len(borrados), len(rutas)))
    print("Listo.")


if __name__ == "__main__":
    main()
