"""
core/bitacora_engine.py — Motor de la Bitácora de Investigación.

Proporciona acceso de alto nivel a las notas del investigador:
- Notas libres, hipótesis (con estado) y citas del corpus
- Ancladas a número/página/artículo específico y módulo de origen
- Exportación a Markdown para uso en papers

Persistencia: tabla `notas_investigacion` en el SQLite del proyecto.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

# Tipos válidos y estados válidos
TIPOS_NOTA   = ("libre", "hipotesis", "cita")
ESTADOS_HYPO = ("abierta", "confirmada", "descartada", "revisada")

# Meses en español, para no depender del locale del sistema (que en Windows
# suele quedar en inglés y produce fechas mixtas tipo "02 de September de 2026"
# en un documento que va a apéndice de paper en español).
_MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _fecha_es(dt: datetime) -> str:
    return f"{dt.day:02d} de {_MESES_ES[dt.month - 1]} de {dt.year}"


# Iconos para exportación Markdown
_ICONO_TIPO = {"libre": "📝", "hipotesis": "💡", "cita": "📌"}
_ICONO_ESTADO = {
    "abierta":     "🔵",
    "confirmada":  "✅",
    "descartada":  "❌",
    "revisada":    "🔄",
}


class BitacoraEngine:
    """
    Motor de notas de investigación.

    Uso:
        b = BitacoraEngine("ruta/proyecto.db")
        nota_id = b.insertar({
            "tipo": "hipotesis",
            "estado": "abierta",
            "texto": "Las noticias de deportes aumentan en verano",
            "etiquetas": ["deportes", "temporalidad"],
            "ref_numero": "enero_1939",
            "ref_pagina": "p0042",
            "modulo_origen": "anal",
        })
        notas = b.listar(tipo="hipotesis", estado="abierta")
        b.exportar_markdown(Path("bitacora.md"))
    """

    def __init__(self, db_path: str):
        self._db_path = str(db_path)
        self._garantizar_tabla()

    # ── Gestión de tabla ──────────────────────────────────────────────────────

    def _garantizar_tabla(self):
        """Crea la tabla si no existe (migración suave para proyectos anteriores)."""
        import sqlite3
        with sqlite3.connect(self._db_path) as conn:
            conn.executescript("""
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS notas_investigacion (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    tipo          TEXT NOT NULL DEFAULT 'libre',
                    estado        TEXT DEFAULT NULL,
                    texto         TEXT NOT NULL DEFAULT '',
                    etiquetas     TEXT DEFAULT '[]',
                    ref_numero    TEXT DEFAULT '',
                    ref_pagina    TEXT DEFAULT '',
                    ref_art_id    TEXT DEFAULT '',
                    modulo_origen TEXT DEFAULT '',
                    creado        TEXT DEFAULT (datetime('now')),
                    modificado    TEXT DEFAULT (datetime('now'))
                );
                CREATE INDEX IF NOT EXISTS idx_notas_tipo
                    ON notas_investigacion(tipo);
                CREATE INDEX IF NOT EXISTS idx_notas_estado
                    ON notas_investigacion(estado);
            """)

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def insertar(self, nota: dict) -> int:
        """Inserta una nota y retorna su id."""
        import sqlite3
        with sqlite3.connect(self._db_path) as conn:
            cur = conn.execute("""
                INSERT INTO notas_investigacion
                    (tipo, estado, texto, etiquetas,
                     ref_numero, ref_pagina, ref_art_id, modulo_origen)
                VALUES (?,?,?,?,?,?,?,?)
            """, (
                nota.get("tipo", "libre"),
                nota.get("estado") or None,
                nota.get("texto", "").strip(),
                json.dumps(nota.get("etiquetas", []), ensure_ascii=False),
                nota.get("ref_numero", ""),
                nota.get("ref_pagina", ""),
                nota.get("ref_art_id", ""),
                nota.get("modulo_origen", ""),
            ))
            return cur.lastrowid

    def actualizar(self, nota_id: int, campos: dict):
        """Actualiza campos específicos de una nota por id."""
        import sqlite3
        permitidos = {"tipo", "estado", "texto", "etiquetas",
                      "ref_numero", "ref_pagina", "ref_art_id", "modulo_origen"}
        updates = {k: v for k, v in campos.items() if k in permitidos}
        if not updates:
            return
        if "etiquetas" in updates and isinstance(updates["etiquetas"], list):
            updates["etiquetas"] = json.dumps(
                updates["etiquetas"], ensure_ascii=False)
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        vals = list(updates.values()) + [nota_id]
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                f"UPDATE notas_investigacion "
                f"SET {set_clause}, modificado = datetime('now') "
                f"WHERE id = ?",
                vals,
            )

    def eliminar(self, nota_id: int):
        import sqlite3
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "DELETE FROM notas_investigacion WHERE id = ?", (nota_id,))

    def listar(
        self,
        tipo: str = None,
        estado: str = None,
        modulo: str = None,
        q: str = None,
    ) -> list[dict]:
        """Lista notas con filtros opcionales. q busca en texto y etiquetas."""
        import sqlite3
        sql = "SELECT * FROM notas_investigacion WHERE 1=1"
        params: list = []
        if tipo:
            sql += " AND tipo = ?"; params.append(tipo)
        if estado:
            sql += " AND estado = ?"; params.append(estado)
        if modulo:
            sql += " AND modulo_origen = ?"; params.append(modulo)
        if q:
            sql += " AND (texto LIKE ? OR etiquetas LIKE ?)"
            params += [f"%{q}%", f"%{q}%"]
        sql += " ORDER BY creado DESC"
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["etiquetas"] = json.loads(d.get("etiquetas") or "[]")
            except Exception:
                d["etiquetas"] = []
            result.append(d)
        return result

    def obtener(self, nota_id: int) -> dict | None:
        import sqlite3
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM notas_investigacion WHERE id = ?",
                (nota_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["etiquetas"] = json.loads(d.get("etiquetas") or "[]")
        except Exception:
            d["etiquetas"] = []
        return d

    def contar(self) -> dict:
        """Retorna conteos por tipo y estado."""
        import sqlite3
        with sqlite3.connect(self._db_path) as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM notas_investigacion").fetchone()[0]
            por_tipo = {}
            for row in conn.execute(
                "SELECT tipo, COUNT(*) FROM notas_investigacion GROUP BY tipo"
            ).fetchall():
                por_tipo[row[0]] = row[1]
            por_estado = {}
            for row in conn.execute(
                "SELECT estado, COUNT(*) FROM notas_investigacion "
                "WHERE tipo='hipotesis' GROUP BY estado"
            ).fetchall():
                por_estado[row[0] or "sin_estado"] = row[1]
        return {"total": total, "por_tipo": por_tipo, "por_estado": por_estado}

    # ── Exportación ───────────────────────────────────────────────────────────

    def exportar_markdown(self, ruta: Path, publicacion: str = "") -> Path:
        """
        Exporta toda la bitácora a Markdown estructurado.
        Ideal para incluir en apéndice de paper o compartir con colaboradores.
        """
        ruta = Path(ruta)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        notas = self.listar()
        fecha = _fecha_es(datetime.now())

        lineas = [
            "# Bitácora de investigación",
            "",
            f"**Corpus:** {publicacion or 'Sin título'}  ",
            f"**Exportado:** {fecha}  ",
            f"**Total de notas:** {len(notas)}",
            "",
        ]

        # Sección hipótesis primero (más valiosas para el paper)
        hipotesis = [n for n in notas if n["tipo"] == "hipotesis"]
        if hipotesis:
            lineas += ["## 💡 Hipótesis de investigación", ""]
            for estado in ESTADOS_HYPO:
                grupo = [h for h in hipotesis if h.get("estado") == estado]
                if not grupo:
                    continue
                icono = _ICONO_ESTADO.get(estado, "•")
                lineas += [
                    f"### {icono} {estado.capitalize()} ({len(grupo)})", ""]
                for n in grupo:
                    lineas += _nota_a_md(n)
            lineas.append("")

        # Citas del corpus
        citas = [n for n in notas if n["tipo"] == "cita"]
        if citas:
            lineas += ["## 📌 Citas del corpus", ""]
            for n in citas:
                lineas += _nota_a_md(n)
            lineas.append("")

        # Notas libres
        libres = [n for n in notas if n["tipo"] == "libre"]
        if libres:
            lineas += ["## 📝 Notas libres", ""]
            for n in libres:
                lineas += _nota_a_md(n)

        contenido = "\n".join(lineas)
        ruta.write_text(contenido, encoding="utf-8")
        return ruta


# ── Helpers ───────────────────────────────────────────────────────────────────

def _nota_a_md(n: dict) -> list[str]:
    """Convierte una nota a líneas Markdown."""
    ref_parts = [p for p in [n.get("ref_numero"), n.get("ref_pagina")] if p]
    ref = " · ".join(ref_parts) if ref_parts else ""
    tags = n.get("etiquetas", [])
    tags_str = " ".join(f"`{t}`" for t in tags) if tags else ""
    fecha = (n.get("creado") or "")[:10]
    modulo = n.get("modulo_origen", "")

    lineas = []
    if ref or modulo or fecha:
        meta_parts = []
        if ref:
            meta_parts.append(f"📍 {ref}")
        if modulo:
            meta_parts.append(f"módulo: {modulo}")
        if fecha:
            meta_parts.append(fecha)
        lineas.append(f"*{' · '.join(meta_parts)}*")
    if tags_str:
        lineas.append(tags_str)
    lineas.append("")
    # Texto con sangría de cita si es tipo "cita"
    texto = n.get("texto", "").strip()
    if n.get("tipo") == "cita":
        for linea in texto.splitlines():
            lineas.append(f"> {linea}")
    else:
        lineas.append(texto)
    lineas += ["", "---", ""]
    return lineas
