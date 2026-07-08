"""core/local_cache.py — Caché en disco LOCAL (nunca en la unidad del proyecto).

Bashkar suele vivir en Google Drive (I:\\), donde la latencia de lectura/
escritura es alta y donde escribir miles de archivos pequeños de caché
además ensucia la sincronización. Este módulo centraliza dónde va la
caché derivada (miniaturas, thumbnails) para que SIEMPRE quede en disco
local: %LOCALAPPDATA%\\BashkarStation\\<subdir> en Windows, ~/.cache/
bashkar_station/<subdir> en otros sistemas.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path


def ruta_cache(subdir: str) -> Path:
    """Directorio de caché local para `subdir` (p.ej. "thumbs"). Se crea
    si no existe."""
    base = os.environ.get("LOCALAPPDATA")
    raiz = Path(base) / "BashkarStation" if base else Path.home() / ".cache" / "bashkar_station"
    destino = raiz / subdir
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def clave_cache(path: Path) -> str:
    """Clave estable para un archivo fuente, sensible a cambios de
    contenido (mtime + tamaño) sin necesidad de leer el archivo entero."""
    path = Path(path)
    try:
        st = path.stat()
        firma = f"{path.resolve()}|{st.st_mtime_ns}|{st.st_size}"
    except FileNotFoundError:
        firma = str(path.resolve())
    return hashlib.sha1(firma.encode("utf-8")).hexdigest()
