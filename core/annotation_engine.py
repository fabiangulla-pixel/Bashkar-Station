"""core/annotation_engine.py — Anotación semántica revisable con historial (estilo Recogito).

Permite al investigador corregir y enriquecer entidades detectadas automáticamente,
con trazabilidad completa: quién cambió qué, cuándo y por qué.

Almacenamiento: SQLite (misma DB del proyecto o DB global de anotaciones).

Tablas:
  anotaciones      — cada mención de entidad con su estado
  historial        — log de cambios por anotación
  autoridades      — cache de enlaces a autoridades externas (Wikidata, GND, etc.)
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ESTADOS_VALIDOS = ("auto", "confirmada", "corregida", "rechazada", "pendiente")

DDL = """
CREATE TABLE IF NOT EXISTS anotaciones (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    art_id      TEXT NOT NULL,
    texto_orig  TEXT NOT NULL,
    texto_norm  TEXT NOT NULL,
    categoria   TEXT NOT NULL,
    inicio_char INTEGER,
    fin_char    INTEGER,
    estado      TEXT DEFAULT 'auto',
    confianza   REAL DEFAULT 0.0,
    fuente      TEXT DEFAULT 'auto',
    wikidata_id TEXT,
    wikidata_lbl TEXT,
    notas       TEXT DEFAULT '',
    creada_en   TEXT NOT NULL,
    modificada_en TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS historial_anotaciones (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    anotacion_id INTEGER NOT NULL,
    campo        TEXT NOT NULL,
    valor_ant    TEXT,
    valor_nuevo  TEXT,
    razon        TEXT DEFAULT '',
    ts           TEXT NOT NULL,
    FOREIGN KEY (anotacion_id) REFERENCES anotaciones(id)
);

CREATE TABLE IF NOT EXISTS autoridades_cache (
    texto_norm   TEXT NOT NULL,
    categoria    TEXT NOT NULL,
    wikidata_id  TEXT,
    wikidata_lbl TEXT,
    descripcion  TEXT,
    consultado_en TEXT,
    PRIMARY KEY (texto_norm, categoria)
);

CREATE INDEX IF NOT EXISTS idx_anot_art ON anotaciones(art_id);
CREATE INDEX IF NOT EXISTS idx_anot_cat ON anotaciones(categoria);
CREATE INDEX IF NOT EXISTS idx_anot_estado ON anotaciones(estado);
"""


@dataclass
class Anotacion:
    art_id:       str
    texto_orig:   str
    texto_norm:   str
    categoria:    str
    inicio_char:  int = 0
    fin_char:     int = 0
    estado:       str = "auto"
    confianza:    float = 0.0
    fuente:       str = "auto"
    wikidata_id:  str = ""
    wikidata_lbl: str = ""
    notas:        str = ""
    id:           int | None = None


class GestorAnotaciones:
    """Gestiona anotaciones semánticas con historial de cambios."""

    def __init__(self, ruta_db: str | Path):
        self.ruta_db = str(ruta_db)
        self._init_db()

    def _conexion(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.ruta_db)
        con.row_factory = sqlite3.Row
        return con

    def _init_db(self):
        with self._conexion() as con:
            con.executescript(DDL)

    # ── Insertar ──────────────────────────────────────────────────────────────

    def insertar(self, anot: Anotacion) -> int:
        """Inserta una anotación nueva. Retorna su id."""
        ahora = datetime.utcnow().isoformat()
        with self._conexion() as con:
            cur = con.execute("""
                INSERT INTO anotaciones
                  (art_id, texto_orig, texto_norm, categoria, inicio_char, fin_char,
                   estado, confianza, fuente, wikidata_id, wikidata_lbl, notas,
                   creada_en, modificada_en)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (anot.art_id, anot.texto_orig, anot.texto_norm, anot.categoria,
                  anot.inicio_char, anot.fin_char, anot.estado, anot.confianza,
                  anot.fuente, anot.wikidata_id, anot.wikidata_lbl, anot.notas,
                  ahora, ahora))
            return cur.lastrowid

    def insertar_lote(self, anotaciones: list[Anotacion]) -> int:
        """Inserta múltiples anotaciones. Retorna cantidad insertada."""
        n = 0
        for anot in anotaciones:
            self.insertar(anot)
            n += 1
        return n

    # ── Consultar ─────────────────────────────────────────────────────────────

    def por_articulo(self, art_id: str,
                     categoria: str | None = None,
                     estado: str | None = None) -> list[dict]:
        sql = "SELECT * FROM anotaciones WHERE art_id = ?"
        params: list = [art_id]
        if categoria:
            sql += " AND categoria = ?"
            params.append(categoria)
        if estado:
            sql += " AND estado = ?"
            params.append(estado)
        sql += " ORDER BY inicio_char"
        with self._conexion() as con:
            return [dict(r) for r in con.execute(sql, params).fetchall()]

    def pendientes(self) -> list[dict]:
        """Anotaciones automáticas aún no revisadas."""
        with self._conexion() as con:
            return [dict(r) for r in con.execute(
                "SELECT * FROM anotaciones WHERE estado IN ('auto','pendiente') "
                "ORDER BY confianza ASC"
            ).fetchall()]

    def estadisticas(self) -> dict:
        with self._conexion() as con:
            total = con.execute("SELECT COUNT(*) FROM anotaciones").fetchone()[0]
            por_estado = {
                row[0]: row[1]
                for row in con.execute(
                    "SELECT estado, COUNT(*) FROM anotaciones GROUP BY estado"
                ).fetchall()
            }
            por_cat = {
                row[0]: row[1]
                for row in con.execute(
                    "SELECT categoria, COUNT(*) FROM anotaciones GROUP BY categoria"
                ).fetchall()
            }
        return {"total": total, "por_estado": por_estado, "por_categoria": por_cat}

    # ── Actualizar con historial ──────────────────────────────────────────────

    def actualizar(self, anot_id: int, cambios: dict, razon: str = "") -> bool:
        """
        Actualiza campos de una anotación y registra en historial.
        cambios: {campo: nuevo_valor}
        """
        campos_permitidos = {
            "texto_norm", "categoria", "estado", "wikidata_id",
            "wikidata_lbl", "notas", "confianza",
        }
        cambios_validos = {k: v for k, v in cambios.items() if k in campos_permitidos}
        if not cambios_validos:
            return False

        if "estado" in cambios_validos and cambios_validos["estado"] not in ESTADOS_VALIDOS:
            raise ValueError(f"Estado inválido: {cambios_validos['estado']}")

        ahora = datetime.utcnow().isoformat()

        with self._conexion() as con:
            actual = con.execute(
                "SELECT * FROM anotaciones WHERE id = ?", (anot_id,)
            ).fetchone()
            if not actual:
                return False

            for campo, nuevo in cambios_validos.items():
                viejo = actual[campo]
                if str(viejo) == str(nuevo):
                    continue
                con.execute("""
                    INSERT INTO historial_anotaciones
                      (anotacion_id, campo, valor_ant, valor_nuevo, razon, ts)
                    VALUES (?,?,?,?,?,?)
                """, (anot_id, campo, str(viejo), str(nuevo), razon, ahora))

            set_clause = ", ".join(f"{k} = ?" for k in cambios_validos)
            vals = list(cambios_validos.values()) + [ahora, anot_id]
            con.execute(
                f"UPDATE anotaciones SET {set_clause}, modificada_en = ? WHERE id = ?",
                vals
            )
        return True

    def historial(self, anot_id: int) -> list[dict]:
        with self._conexion() as con:
            return [dict(r) for r in con.execute(
                "SELECT * FROM historial_anotaciones WHERE anotacion_id = ? ORDER BY ts",
                (anot_id,)
            ).fetchall()]

    # ── Exportar ──────────────────────────────────────────────────────────────

    def exportar_json(self, ruta_destino: str | Path,
                      solo_confirmadas: bool = False) -> int:
        """Exporta anotaciones a JSON-LD compatible con Recogito."""
        with self._conexion() as con:
            if solo_confirmadas:
                rows = con.execute(
                    "SELECT * FROM anotaciones WHERE estado IN ('confirmada','corregida')"
                ).fetchall()
            else:
                rows = con.execute("SELECT * FROM anotaciones").fetchall()

        anotaciones_ld = []
        for r in rows:
            d = dict(r)
            anotaciones_ld.append({
                "@context": "http://www.w3.org/ns/anno.jsonld",
                "@type":    "Annotation",
                "id":       f"bashkar:anotacion:{d['id']}",
                "body": [{
                    "type":  "TextualBody",
                    "value": d["texto_norm"],
                    "purpose": "tagging",
                    "creator": "Bashkar Station",
                }],
                "target": {
                    "source":   d["art_id"],
                    "selector": {
                        "type":  "TextPositionSelector",
                        "start": d["inicio_char"],
                        "end":   d["fin_char"],
                    }
                },
                "bashkar:categoria":   d["categoria"],
                "bashkar:estado":      d["estado"],
                "bashkar:confianza":   d["confianza"],
                "bashkar:wikidata_id": d["wikidata_id"],
                "created":             d["creada_en"],
                "modified":            d["modificada_en"],
            })

        with open(ruta_destino, "w", encoding="utf-8") as f:
            json.dump(anotaciones_ld, f, ensure_ascii=False, indent=2)

        return len(anotaciones_ld)

    def importar_desde_ner(
        self,
        resultados_ner: dict,
        reemplazar: bool = False,
    ) -> int:
        """
        Importa entidades del NER automático como anotaciones en estado 'auto'.
        resultados_ner: {art_id: {categoria: [{texto, inicio, fin, confianza}]}}
        """
        if reemplazar:
            with self._conexion() as con:
                con.execute(
                    "DELETE FROM anotaciones WHERE fuente = 'ner_auto'"
                )

        n = 0
        for art_id, cats in resultados_ner.items():
            for cat, menciones in cats.items():
                for m in menciones:
                    anot = Anotacion(
                        art_id=art_id,
                        texto_orig=m.get("texto", ""),
                        texto_norm=m.get("texto", "").strip(),
                        categoria=cat,
                        inicio_char=m.get("inicio", 0),
                        fin_char=m.get("fin", 0),
                        estado="auto",
                        confianza=m.get("confianza", 0.0),
                        fuente="ner_auto",
                    )
                    self.insertar(anot)
                    n += 1
        return n
