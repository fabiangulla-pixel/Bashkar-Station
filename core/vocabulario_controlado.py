"""core/vocabulario_controlado.py — Vocabulario controlado consultable (Fase 2).

Expone como recurso único y consultable el vocabulario histórico ya capturado
por el proyecto, combinando tres fuentes 100% offline:

  1. Glosario histórico global (SQLite ~/.bashkar/bashkar.db, tabla glosario_global):
     arcaísmos, neologismos, colombianismos, extranjerismos, cargos, instituciones.
  2. Arcaísmos morfológicos (core.morfologia_historica): formas históricas →
     lema moderno (excepciones de lematización del español 1930s).
  3. Entidades canónicas del proyecto (datos.repositorio): vínculo término →
     tipo de entidad (persona/lugar/institución/...), para el cruce léxico-NER.

Pensado como insumo para el paper y como glosario reusable por otros proyectos
de prensa histórica colombiana. No depende de IA ni de red.
"""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

# ── Carga de las fuentes ──────────────────────────────────────────────────────

def _glosario_global(ruta_db_global: str | None = None) -> list[dict]:
    """Lee la tabla glosario_global de la DB global. [] si no existe."""
    if ruta_db_global is None:
        ruta_db_global = str(Path.home() / ".bashkar" / "bashkar.db")
    if not Path(ruta_db_global).exists():
        return []
    try:
        con = sqlite3.connect(ruta_db_global)
        con.row_factory = sqlite3.Row
        filas = con.execute(
            "SELECT termino, definicion, categoria, periodo, ejemplo, fuente "
            "FROM glosario_global"
        ).fetchall()
        con.close()
    except sqlite3.Error:
        return []
    return [{
        "termino": r["termino"],
        "definicion": r["definicion"] or "",
        "categoria": r["categoria"] or "otro",
        "tipo_entidad": "",
        "periodo": r["periodo"] or "",
        "ejemplo": r["ejemplo"] or "",
        "fuente": r["fuente"] or "glosario_global",
    } for r in filas]


def _arcaismos_morfologicos() -> list[dict]:
    """Arcaísmos del lematizador histórico (forma → lema moderno)."""
    try:
        from core.morfologia_historica import glosario_arcaismos
    except Exception:
        return []
    out = []
    for e in glosario_arcaismos():
        out.append({
            "termino": e["forma_historica"],
            "definicion": f"forma histórica de «{e['lema_moderno']}»",
            "categoria": "arcaismo",
            "tipo_entidad": "",
            "periodo": "1930s",
            "ejemplo": "",
            "fuente": "morfologia_historica",
        })
    return out


def _terminos_canonicos(ruta_db_proyecto: str | None) -> list[dict]:
    """Entidades canónicas del proyecto como términos con tipo de entidad."""
    if not ruta_db_proyecto or not Path(ruta_db_proyecto).exists():
        return []
    try:
        con = sqlite3.connect(ruta_db_proyecto)
        con.row_factory = sqlite3.Row
        filas = con.execute(
            "SELECT nombre, tipo, wikidata_id, n_menciones "
            "FROM entidades_canonicas"
        ).fetchall()
        con.close()
    except sqlite3.Error:
        return []
    out = []
    for r in filas:
        defn = f"entidad ({r['tipo']})"
        if r["wikidata_id"]:
            defn += f" · Wikidata {r['wikidata_id']}"
        out.append({
            "termino": r["nombre"],
            "definicion": defn,
            "categoria": "entidad",
            "tipo_entidad": r["tipo"],
            "periodo": "",
            "ejemplo": f"{r['n_menciones']} menciones",
            "fuente": "entidades_canonicas",
        })
    return out


# ── API pública ───────────────────────────────────────────────────────────────

_CAMPOS = ("termino", "definicion", "categoria", "tipo_entidad",
           "periodo", "ejemplo", "fuente")


def construir_vocabulario(ruta_db_proyecto: str | None = None,
                          ruta_db_global: str | None = None,
                          incluir_entidades: bool = True) -> list[dict]:
    """
    Construye el vocabulario controlado unificado, deduplicado por
    (termino_norm, categoria). Las fuentes con definición ganan sobre las vacías.
    Ordenado por término. 100% offline.
    """
    entradas = _glosario_global(ruta_db_global) + _arcaismos_morfologicos()
    if incluir_entidades:
        entradas += _terminos_canonicos(ruta_db_proyecto)

    fusionado: dict[tuple, dict] = {}
    for e in entradas:
        clave = (e["termino"].strip().lower(), e["categoria"])
        if clave not in fusionado:
            fusionado[clave] = e
        else:
            # conserva la entrada con definición no vacía
            if not fusionado[clave]["definicion"] and e["definicion"]:
                fusionado[clave] = e
    return sorted(fusionado.values(), key=lambda x: x["termino"].lower())


def consultar(vocabulario: list[dict], q: str = "",
              categoria: str = "", tipo_entidad: str = "") -> list[dict]:
    """Filtra el vocabulario por subcadena (q), categoría y/o tipo de entidad."""
    q = (q or "").strip().lower()
    res = vocabulario
    if q:
        res = [e for e in res
               if q in e["termino"].lower() or q in e["definicion"].lower()]
    if categoria:
        res = [e for e in res if e["categoria"] == categoria]
    if tipo_entidad:
        res = [e for e in res if e["tipo_entidad"] == tipo_entidad]
    return res


def estadisticas(vocabulario: list[dict]) -> dict:
    """Resumen: total y conteo por categoría y por fuente."""
    from collections import Counter
    return {
        "total": len(vocabulario),
        "por_categoria": dict(Counter(e["categoria"] for e in vocabulario)),
        "por_fuente": dict(Counter(e["fuente"] for e in vocabulario)),
    }


def exportar_csv(vocabulario: list[dict], ruta: str | Path) -> int:
    """Exporta a CSV utf-8-sig (Excel-friendly). Retorna nº de entradas."""
    with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(_CAMPOS), extrasaction="ignore")
        w.writeheader()
        w.writerows(vocabulario)
    return len(vocabulario)


def exportar_json(vocabulario: list[dict], ruta: str | Path) -> int:
    """Exporta a JSON reusable por otros proyectos. Retorna nº de entradas."""
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump({"vocabulario_controlado": vocabulario}, f,
                  ensure_ascii=False, indent=2)
    return len(vocabulario)
