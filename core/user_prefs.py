"""core/user_prefs.py — Preferencias de usuario persistentes entre sesiones.

Sigue la misma convención de core/zone_labeler.py (tipos_zona.json):
JSON simple en ~/.bashkar/, sin dependencias, tolerante a archivo ausente
o corrupto (nunca lanza, siempre degrada a valores por defecto).

Usado por: verificador OCR (umbral de confianza), diálogo de exportación
("abrir al terminar"), pantalla de inicio ("no mostrar al inicio").
"""

from __future__ import annotations

import json
from pathlib import Path

PREFS_PATH = Path.home() / ".bashkar" / "prefs.json"


def cargar_prefs() -> dict:
    """Carga todas las preferencias. Nunca lanza: archivo ausente o
    corrupto devuelve dict vacío."""
    if not PREFS_PATH.exists():
        return {}
    try:
        return json.loads(PREFS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def guardar_pref(clave: str, valor) -> None:
    """Persiste una preferencia individual (mezcla con las existentes)."""
    prefs = cargar_prefs()
    prefs[clave] = valor
    PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PREFS_PATH.write_text(
        json.dumps(prefs, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def obtener_pref(clave: str, default=None):
    """Lee una preferencia individual, o `default` si no existe."""
    return cargar_prefs().get(clave, default)
