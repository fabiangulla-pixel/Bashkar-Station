"""conocimiento/base_conocimiento.py — Base de conocimiento SQLite acumulativa.

Persiste entre proyectos:
  - Entidades validadas (personas, lugares, organizaciones, etc.)
  - Relaciones entre entidades
  - Glosario de arcaísmos/colombianismos
  - Correcciones OCR frecuentes
  - Trazabilidad de procesamiento (qué modelo, qué versión, quién editó)
  - Registro de proyectos abiertos
"""

from __future__ import annotations

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

DB_PATH = Path.home() / ".bashkar" / "bashkar.db"


def _conectar() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def inicializar_db() -> None:
    """Crea todas las tablas si no existen."""
    conn = _conectar()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS entidades (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre      TEXT NOT NULL,
            categoria   TEXT NOT NULL,
            descripcion TEXT,
            proyecto    TEXT,
            confianza   REAL DEFAULT 1.0,
            verificada  INTEGER DEFAULT 0,
            creado_en   TEXT DEFAULT (datetime('now')),
            UNIQUE(nombre, categoria)
        );

        CREATE TABLE IF NOT EXISTS relaciones (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            entidad_a   TEXT NOT NULL,
            relacion    TEXT NOT NULL,
            entidad_b   TEXT NOT NULL,
            articulo_id TEXT,
            proyecto    TEXT,
            peso        REAL DEFAULT 1.0,
            creado_en   TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS glosario (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            termino     TEXT NOT NULL UNIQUE,
            tipo        TEXT NOT NULL,
            definicion  TEXT,
            ejemplo     TEXT,
            frecuencia  INTEGER DEFAULT 1,
            proyecto    TEXT,
            creado_en   TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS correcciones_ocr (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            error       TEXT NOT NULL UNIQUE,
            correccion  TEXT NOT NULL,
            frecuencia  INTEGER DEFAULT 1,
            creado_en   TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS trazabilidad (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            proyecto        TEXT NOT NULL,
            articulo_id     TEXT,
            modulo          TEXT NOT NULL,
            modelo          TEXT,
            version_prompt  TEXT,
            confianza       REAL,
            editado_por     TEXT,
            fecha           TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS proyectos (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ruta        TEXT NOT NULL UNIQUE,
            nombre      TEXT,
            ultima_vez  TEXT DEFAULT (datetime('now')),
            metadatos   TEXT
        );
    """)

    conn.commit()
    conn.close()


# ── Entidades ────────────────────────────────────────────────────────────────

def registrar_entidad(
    nombre: str,
    categoria: str,
    descripcion: str = "",
    proyecto: str = "",
    confianza: float = 1.0,
    verificada: bool = False,
) -> int:
    """Inserta o actualiza una entidad. Retorna su id."""
    conn = _conectar()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO entidades (nombre, categoria, descripcion, proyecto, confianza, verificada)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(nombre, categoria) DO UPDATE SET
            descripcion = COALESCE(excluded.descripcion, descripcion),
            proyecto    = COALESCE(excluded.proyecto, proyecto),
            confianza   = MAX(confianza, excluded.confianza),
            verificada  = MAX(verificada, excluded.verificada)
    """, (nombre, categoria, descripcion, proyecto, confianza, int(verificada)))
    eid = cur.lastrowid or cur.execute(
        "SELECT id FROM entidades WHERE nombre=? AND categoria=?", (nombre, categoria)
    ).fetchone()[0]
    conn.commit()
    conn.close()
    return eid


def buscar_entidad(nombre: str, categoria: str = "") -> list[dict]:
    """Busca entidades por nombre (parcial) y opcionalmente categoría."""
    conn = _conectar()
    cur = conn.cursor()
    if categoria:
        cur.execute(
            "SELECT * FROM entidades WHERE nombre LIKE ? AND categoria=? ORDER BY confianza DESC",
            (f"%{nombre}%", categoria),
        )
    else:
        cur.execute(
            "SELECT * FROM entidades WHERE nombre LIKE ? ORDER BY confianza DESC",
            (f"%{nombre}%",),
        )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def marcar_verificada(nombre: str, categoria: str) -> None:
    conn = _conectar()
    conn.execute(
        "UPDATE entidades SET verificada=1 WHERE nombre=? AND categoria=?",
        (nombre, categoria),
    )
    conn.commit()
    conn.close()


def obtener_entidades(categoria: str = "", solo_verificadas: bool = False) -> list[dict]:
    conn = _conectar()
    cur = conn.cursor()
    wheres, params = [], []
    if categoria:
        wheres.append("categoria=?")
        params.append(categoria)
    if solo_verificadas:
        wheres.append("verificada=1")
    sql = "SELECT * FROM entidades"
    if wheres:
        sql += " WHERE " + " AND ".join(wheres)
    sql += " ORDER BY nombre"
    cur.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# ── Correcciones OCR ─────────────────────────────────────────────────────────

def registrar_correccion_ocr(error: str, correccion: str) -> None:
    """Registra o incrementa frecuencia de una corrección OCR."""
    conn = _conectar()
    conn.execute("""
        INSERT INTO correcciones_ocr (error, correccion, frecuencia)
        VALUES (?, ?, 1)
        ON CONFLICT(error) DO UPDATE SET
            frecuencia  = frecuencia + 1,
            correccion  = excluded.correccion
    """, (error, correccion))
    conn.commit()
    conn.close()


def obtener_correcciones_frecuentes(min_frecuencia: int = 3) -> list[dict]:
    conn = _conectar()
    cur = conn.cursor()
    cur.execute(
        "SELECT error, correccion, frecuencia FROM correcciones_ocr "
        "WHERE frecuencia >= ? ORDER BY frecuencia DESC",
        (min_frecuencia,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# ── Glosario ─────────────────────────────────────────────────────────────────

def registrar_termino_glosario(
    termino: str, tipo: str, definicion: str = "", ejemplo: str = "", proyecto: str = ""
) -> None:
    conn = _conectar()
    conn.execute("""
        INSERT INTO glosario (termino, tipo, definicion, ejemplo, frecuencia, proyecto)
        VALUES (?, ?, ?, ?, 1, ?)
        ON CONFLICT(termino) DO UPDATE SET
            frecuencia  = frecuencia + 1,
            definicion  = COALESCE(excluded.definicion, definicion),
            ejemplo     = COALESCE(excluded.ejemplo, ejemplo)
    """, (termino, tipo, definicion, ejemplo, proyecto))
    conn.commit()
    conn.close()


def obtener_glosario(tipo: str = "") -> list[dict]:
    conn = _conectar()
    cur = conn.cursor()
    if tipo:
        cur.execute(
            "SELECT * FROM glosario WHERE tipo=? ORDER BY frecuencia DESC",
            (tipo,),
        )
    else:
        cur.execute("SELECT * FROM glosario ORDER BY frecuencia DESC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# ── Trazabilidad ─────────────────────────────────────────────────────────────

def registrar_trazabilidad(
    proyecto: str,
    modulo: str,
    articulo_id: str = "",
    modelo: str = "",
    version_prompt: str = "",
    confianza: float = 1.0,
    editado_por: str = "",
) -> None:
    conn = _conectar()
    conn.execute("""
        INSERT INTO trazabilidad
            (proyecto, articulo_id, modulo, modelo, version_prompt, confianza, editado_por)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (proyecto, articulo_id, modulo, modelo, version_prompt, confianza, editado_por))
    conn.commit()
    conn.close()


def obtener_trazabilidad(proyecto: str) -> list[dict]:
    conn = _conectar()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM trazabilidad WHERE proyecto=? ORDER BY fecha DESC",
        (proyecto,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# ── Proyectos ─────────────────────────────────────────────────────────────────

def registrar_proyecto(ruta: str, nombre: str = "", metadatos: dict = None) -> None:
    conn = _conectar()
    conn.execute("""
        INSERT INTO proyectos (ruta, nombre, ultima_vez, metadatos)
        VALUES (?, ?, datetime('now'), ?)
        ON CONFLICT(ruta) DO UPDATE SET
            ultima_vez = datetime('now'),
            nombre     = COALESCE(excluded.nombre, nombre),
            metadatos  = COALESCE(excluded.metadatos, metadatos)
    """, (ruta, nombre, json.dumps(metadatos or {})))
    conn.commit()
    conn.close()


def obtener_proyectos_recientes(limite: int = 10) -> list[dict]:
    conn = _conectar()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM proyectos ORDER BY ultima_vez DESC LIMIT ?", (limite,)
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# ── Estadísticas ──────────────────────────────────────────────────────────────

def estadisticas_db() -> dict:
    conn = _conectar()
    cur = conn.cursor()
    stats = {}
    for tabla in ("entidades", "glosario", "correcciones_ocr", "trazabilidad", "proyectos"):
        cur.execute(f"SELECT COUNT(*) FROM {tabla}")
        stats[tabla] = cur.fetchone()[0]
    stats["entidades_verificadas"] = conn.execute(
        "SELECT COUNT(*) FROM entidades WHERE verificada=1"
    ).fetchone()[0]
    conn.close()
    return stats


# ── Importar desde índice NER ─────────────────────────────────────────────────

def importar_desde_indice_ner(
    indice_global: dict, proyecto: str = "", confianza: float = 0.8
) -> int:
    """Importa todas las entidades del índice NER a la base de conocimiento."""
    n = 0
    for categoria, entidades in indice_global.items():
        if not isinstance(entidades, dict):
            continue
        for nombre, articulos in entidades.items():
            if not nombre.strip():
                continue
            registrar_entidad(
                nombre=nombre,
                categoria=categoria,
                descripcion=f"Artículos: {', '.join(list(articulos)[:3])}",
                proyecto=proyecto,
                confianza=confianza,
            )
            n += 1
    return n
