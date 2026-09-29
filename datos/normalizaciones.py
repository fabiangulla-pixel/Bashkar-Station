"""
datos/normalizaciones.py — Capas de texto por página: OCR, IA y revisión humana.

Cada página normalizada tiene tres capas que NO son intercambiables:

  · ``ocr_crudo``    lo que produjo el motor. Es evidencia: nunca se sobrescribe.
  · ``norm_ia``      corrección automática (modelo o corrector ortográfico).
  · ``norm_usuario`` revisión del investigador.

Antes esto vivía en ``app.py`` (``_norm_escribir_db``) con tres fallos:

  1. El panel guarda el texto final en el ``.txt`` de la página y, en la
     sesión siguiente, relee ese ``.txt`` como si fuera OCR crudo. El UPSERT
     reemplazaba entonces ``ocr_crudo`` por la versión corregida: el original
     se perdía en la segunda pasada de normalización, sin aviso.
  2. ``ts_usuario`` y ``ts_ia`` recibían la misma hora en cada guardado, haya
     cambiado o no esa capa; la tabla no podía decir quién tocó qué y cuándo.
  3. ``except Exception: pass``: un fallo de escritura parecía un éxito.

Aquí el OCR crudo se fija en la primera escritura y queda congelado, cada capa
lleva su propia marca de tiempo, y cada cambio deja una fila en
``normalizaciones_historial`` (solo inserción) con autor y commit del software.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from datos.schema import SCHEMA_NORMALIZACIONES

SCHEMA_HISTORIAL = """
CREATE TABLE IF NOT EXISTS normalizaciones_historial (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    numero          TEXT NOT NULL,
    pagina          TEXT NOT NULL,
    capa            TEXT NOT NULL CHECK (capa IN ('ocr_crudo','norm_ia','norm_usuario')),
    texto           TEXT,
    autor           TEXT,
    commit_software TEXT,
    ts              TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_norm_hist_pag ON normalizaciones_historial(numero, pagina);
"""

# Columnas de proveniencia añadidas a una tabla que ya existe en proyectos
# reales: se agregan con ALTER TABLE, nunca recreando la tabla.
_COLUMNAS_PROVENIENCIA = {
    "ocr_motor": "TEXT",
    "ocr_version": "TEXT",
    "autor_usuario": "TEXT",
    "autor_ia": "TEXT",
    "commit_software": "TEXT",
}

CAPAS = ("ocr_crudo", "norm_ia", "norm_usuario")


def asegurar_esquema(con: sqlite3.Connection) -> None:
    """Crea o migra la tabla y el historial. Idempotente."""
    con.executescript(SCHEMA_NORMALIZACIONES)
    con.executescript(SCHEMA_HISTORIAL)
    existentes = {r[1] for r in con.execute("PRAGMA table_info(normalizaciones)")}
    for col, tipo in _COLUMNAS_PROVENIENCIA.items():
        if col not in existentes:
            con.execute(f"ALTER TABLE normalizaciones ADD COLUMN {col} {tipo}")


def _ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def leer(db_path, numero: str, pagina: str) -> dict | None:
    """Devuelve la fila completa como dict, o None si no hay base o fila."""
    if not db_path or not Path(db_path).exists():
        return None
    con = sqlite3.connect(str(db_path), timeout=30)
    try:
        con.row_factory = sqlite3.Row
        asegurar_esquema(con)
        fila = con.execute(
            "SELECT * FROM normalizaciones WHERE numero=? AND pagina=?",
            (numero, pagina),
        ).fetchone()
        return dict(fila) if fila else None
    finally:
        con.close()


def guardar(db_path, numero: str, pagina: str, *, ocr_crudo: str,
            norm_usuario: str, norm_ia: str, autor_usuario: str = "",
            autor_ia: str = "", ocr_motor: str = "", ocr_version: str = "",
            commit_software: str = "") -> list[str]:
    """Guarda las capas de una página. Devuelve la lista de capas que cambiaron.

    ``ocr_crudo`` solo se escribe si la fila no tenía uno: lo que llegue después
    se ignora, porque a partir de la primera sesión el ``.txt`` que lo origina
    ya contiene texto corregido. Los errores de SQLite se propagan.
    """
    con = sqlite3.connect(str(db_path), timeout=30)
    try:
        asegurar_esquema(con)
        previa = con.execute(
            "SELECT ocr_crudo, norm_ia, norm_usuario, ts_ia, ts_usuario "
            "FROM normalizaciones WHERE numero=? AND pagina=?",
            (numero, pagina),
        ).fetchone()
        ts = _ahora()
        if previa is None:
            antes = {"ocr_crudo": None, "norm_ia": None, "norm_usuario": None}
            ts_ia = ts if norm_ia else None
            ts_usuario = ts if norm_usuario else None
        else:
            antes = dict(zip(CAPAS, previa[:3], strict=True))
            ts_ia, ts_usuario = previa[3], previa[4]

        crudo_final = antes["ocr_crudo"] if antes["ocr_crudo"] else ocr_crudo
        nuevas = {"ocr_crudo": crudo_final, "norm_ia": norm_ia,
                  "norm_usuario": norm_usuario}
        cambiadas = [c for c in CAPAS if (nuevas[c] or "") != (antes[c] or "")]
        if previa is not None:
            if "norm_ia" in cambiadas:
                ts_ia = ts
            if "norm_usuario" in cambiadas:
                ts_usuario = ts

        con.execute(
            """INSERT INTO normalizaciones
                (numero, pagina, ocr_crudo, norm_usuario, norm_ia, ts_usuario, ts_ia,
                 ocr_motor, ocr_version, autor_usuario, autor_ia, commit_software)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(numero, pagina) DO UPDATE SET
                 ocr_crudo       = excluded.ocr_crudo,
                 norm_usuario    = excluded.norm_usuario,
                 norm_ia         = excluded.norm_ia,
                 ts_usuario      = excluded.ts_usuario,
                 ts_ia           = excluded.ts_ia,
                 ocr_motor       = COALESCE(NULLIF(normalizaciones.ocr_motor,''), excluded.ocr_motor),
                 ocr_version     = COALESCE(NULLIF(normalizaciones.ocr_version,''), excluded.ocr_version),
                 autor_usuario   = CASE WHEN ? THEN excluded.autor_usuario
                                        ELSE normalizaciones.autor_usuario END,
                 autor_ia        = CASE WHEN ? THEN excluded.autor_ia
                                        ELSE normalizaciones.autor_ia END,
                 commit_software = excluded.commit_software
            """,
            (numero, pagina, crudo_final, norm_usuario, norm_ia, ts_usuario, ts_ia,
             ocr_motor, ocr_version, autor_usuario, autor_ia, commit_software,
             "norm_usuario" in cambiadas, "norm_ia" in cambiadas),
        )
        autores = {"ocr_crudo": ocr_motor, "norm_ia": autor_ia,
                   "norm_usuario": autor_usuario}
        for capa in cambiadas:
            con.execute(
                "INSERT INTO normalizaciones_historial "
                "(numero, pagina, capa, texto, autor, commit_software, ts) "
                "VALUES (?,?,?,?,?,?,?)",
                (numero, pagina, capa, nuevas[capa], autores[capa], commit_software, ts),
            )
        con.commit()
        return cambiadas
    finally:
        con.close()


def historial(db_path, numero: str, pagina: str) -> list[dict]:
    """Todas las versiones de las capas de una página, en orden de escritura."""
    con = sqlite3.connect(str(db_path), timeout=30)
    try:
        con.row_factory = sqlite3.Row
        asegurar_esquema(con)
        return [dict(r) for r in con.execute(
            "SELECT capa, texto, autor, commit_software, ts "
            "FROM normalizaciones_historial WHERE numero=? AND pagina=? ORDER BY id",
            (numero, pagina))]
    finally:
        con.close()


def estado_epistemico(fila: dict | None) -> str:
    """Clasifica el texto vigente de una página según quién lo produjo.

    Devuelve 'revisado' (hay revisión humana), 'corregido_ia' (solo corrección
    automática), 'ocr' (solo salida del motor) o 'sin_datos'.
    """
    if not fila:
        return "sin_datos"
    if (fila.get("norm_usuario") or "").strip():
        return "revisado"
    if (fila.get("norm_ia") or "").strip():
        return "corregido_ia"
    if (fila.get("ocr_crudo") or "").strip():
        return "ocr"
    return "sin_datos"


ETIQUETAS_ESTADO = {
    "revisado": "✓ revisado por el investigador",
    "corregido_ia": "◐ corregido automáticamente (sin revisión humana)",
    "ocr": "○ OCR sin revisar",
    "sin_datos": "— sin texto",
}


def resumen_revision(db_path) -> dict | None:
    """Cuántas páginas hay en cada estado epistémico. None si no hay base.

    Solo cuenta páginas que pasaron por Normalizar: una página que nunca se
    abrió allí no está en la tabla, y eso se dice en ``nota`` en vez de
    contarla como revisada o no.
    """
    if not db_path or not Path(db_path).exists():
        return None
    con = sqlite3.connect(str(db_path), timeout=30)
    try:
        con.row_factory = sqlite3.Row
        asegurar_esquema(con)
        filas = [dict(r) for r in con.execute(
            "SELECT ocr_crudo, norm_ia, norm_usuario FROM normalizaciones")]
    finally:
        con.close()
    conteo = {k: 0 for k in ETIQUETAS_ESTADO}
    for f in filas:
        conteo[estado_epistemico(f)] += 1
    total = len(filas)
    return {
        **conteo,
        "total": total,
        "pct_revision_humana": round(100 * conteo["revisado"] / total, 1) if total else 0.0,
        "nota": "Solo páginas registradas en el panel Normalizar.",
    }
