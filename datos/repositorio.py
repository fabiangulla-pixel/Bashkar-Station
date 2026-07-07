"""
datos/repositorio.py — Única puerta de acceso a SQLite en Bashkar Station.

Los paneles y módulos NUNCA tocan sqlite3 directamente.
Todo pasa por esta clase.

Uso:
    from datos.repositorio import Repositorio
    repo = Repositorio("ruta/a/proyecto.db")
    repo.guardar_articulo({...})
    arts = repo.listar_articulos()
"""

import sqlite3
import json
import platform
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from datos.schema import SCHEMA_PROYECTO, SCHEMA_GLOBAL


# ── DB global (conocimiento compartido entre proyectos) ────────────────────────

def _ruta_db_global() -> Path:
    base = Path.home() / ".bashkar"
    base.mkdir(parents=True, exist_ok=True)
    return base / "bashkar.db"


def inicializar_db_global():
    """Crea la DB global si no existe."""
    ruta = _ruta_db_global()
    with sqlite3.connect(str(ruta)) as conn:
        conn.executescript(SCHEMA_GLOBAL)
    return ruta


# ── Repositorio por proyecto ───────────────────────────────────────────────────

class Repositorio:
    """
    Acceso a la base de datos SQLite de un proyecto .bashkar.

    Cada instancia gestiona UNA base de datos de proyecto.
    Usa WAL mode para concurrencia con los threads de procesamiento.
    """

    def __init__(self, ruta_db: str):
        self.ruta_db = str(ruta_db)
        self._inicializar()

    def _inicializar(self):
        with self._conn() as conn:
            conn.executescript(SCHEMA_PROYECTO)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.ruta_db, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── Artículos ──────────────────────────────────────────────────────────────

    def guardar_articulo(self, articulo: dict):
        """Inserta o actualiza un artículo. La clave es articulo['id']."""
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO articulos
                    (id, archivo_origen, numero, pagina_inicio, pagina_fin,
                     tipo, titulo, autor, fecha_publicacion, seccion,
                     palabras, estado)
                VALUES
                    (:id, :archivo_origen, :numero, :pagina_inicio, :pagina_fin,
                     :tipo, :titulo, :autor, :fecha_publicacion, :seccion,
                     :palabras, :estado)
                ON CONFLICT(id) DO UPDATE SET
                    titulo     = excluded.titulo,
                    autor      = excluded.autor,
                    seccion    = excluded.seccion,
                    palabras   = excluded.palabras,
                    estado     = excluded.estado,
                    modificado = datetime('now')
            """, {
                "id":               articulo.get("id", ""),
                "archivo_origen":   articulo.get("archivo_origen", ""),
                "numero":           articulo.get("numero", ""),
                "pagina_inicio":    articulo.get("pagina_inicio"),
                "pagina_fin":       articulo.get("pagina_fin"),
                "tipo":             articulo.get("tipo", "articulo"),
                "titulo":           articulo.get("titulo"),
                "autor":            articulo.get("autor"),
                "fecha_publicacion":articulo.get("fecha_publicacion"),
                "seccion":          articulo.get("seccion"),
                "palabras":         articulo.get("palabras", 0),
                "estado":           articulo.get("estado", "pendiente"),
            })

    def obtener_articulo(self, articulo_id: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM articulos WHERE id = ?", (articulo_id,)
            ).fetchone()
            return dict(row) if row else None

    def listar_articulos(self, numero: str = None, estado: str = None) -> list[dict]:
        sql = "SELECT * FROM articulos WHERE 1=1"
        params = []
        if numero:
            sql += " AND numero = ?"
            params.append(numero)
        if estado:
            sql += " AND estado = ?"
            params.append(estado)
        sql += " ORDER BY numero, pagina_inicio"
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def actualizar_estado(self, articulo_id: str, estado: str):
        """estados: pendiente | procesando | completo | error"""
        with self._conn() as conn:
            conn.execute(
                "UPDATE articulos SET estado = ?, modificado = datetime('now') WHERE id = ?",
                (estado, articulo_id)
            )

    def articulos_pendientes(self) -> list[dict]:
        return self.listar_articulos(estado="pendiente")

    def estadisticas_corpus(self) -> dict:
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM articulos").fetchone()[0]
            con_ocr = conn.execute(
                "SELECT COUNT(DISTINCT articulo_id) FROM ocr"
            ).fetchone()[0]
            con_entidades = conn.execute(
                "SELECT COUNT(DISTINCT articulo_id) FROM entidades"
            ).fetchone()[0]
            total_entidades = conn.execute(
                "SELECT COUNT(*) FROM entidades"
            ).fetchone()[0]
            con_tono = conn.execute(
                "SELECT COUNT(DISTINCT articulo_id) FROM tono"
            ).fetchone()[0]
        return {
            "total_articulos":   total,
            "con_ocr":           con_ocr,
            "con_entidades":     con_entidades,
            "total_entidades":   total_entidades,
            "con_tono":          con_tono,
        }

    # ── OCR ────────────────────────────────────────────────────────────────────

    def guardar_ocr(self, articulo_id: str, texto_crudo: str, texto_limpio: str,
                    confianza: float, motor: str, version_motor: str = ""):
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO ocr (articulo_id, texto_crudo, texto_limpio,
                                 confianza, motor, version_motor)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (articulo_id, texto_crudo, texto_limpio,
                  confianza, motor, version_motor))
        self.actualizar_estado(articulo_id, "completo")

    def obtener_texto(self, articulo_id: str, limpio: bool = True) -> Optional[str]:
        campo = "texto_limpio" if limpio else "texto_crudo"
        with self._conn() as conn:
            row = conn.execute(
                f"SELECT {campo} FROM ocr WHERE articulo_id = ? ORDER BY id DESC LIMIT 1",
                (articulo_id,)
            ).fetchone()
            return row[0] if row else None

    def obtener_confianza_ocr(self, articulo_id: str) -> float:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT confianza FROM ocr WHERE articulo_id = ? ORDER BY id DESC LIMIT 1",
                (articulo_id,)
            ).fetchone()
            return float(row[0]) if row else 0.0

    # ── Entidades NER ──────────────────────────────────────────────────────────

    def guardar_entidades(self, articulo_id: str, entidades: list[dict]):
        """
        Reemplaza todas las entidades del artículo.
        Cada entidad: {texto, categoria, confianza, fuente, inicio?, fin?, wikidata_id?}
        """
        with self._conn() as conn:
            conn.execute("DELETE FROM entidades WHERE articulo_id = ?", (articulo_id,))
            conn.executemany("""
                INSERT INTO entidades
                    (articulo_id, texto, categoria, inicio, fin,
                     confianza, fuente, wikidata_id, wikidata_uri)
                VALUES
                    (:articulo_id, :texto, :categoria, :inicio, :fin,
                     :confianza, :fuente, :wikidata_id, :wikidata_uri)
            """, [{
                "articulo_id": articulo_id,
                "texto":       e.get("texto", ""),
                "categoria":   e.get("categoria", "otros"),
                "inicio":      e.get("inicio"),
                "fin":         e.get("fin"),
                "confianza":   e.get("confianza", 0.0),
                "fuente":      e.get("fuente", "spacy"),
                "wikidata_id": e.get("wikidata_id"),
                "wikidata_uri":e.get("wikidata_uri"),
            } for e in entidades])

    def buscar_entidades(self, categoria: str = None, texto: str = None,
                         articulo_id: str = None) -> list[dict]:
        sql = "SELECT * FROM entidades WHERE 1=1"
        params = []
        if categoria:
            sql += " AND categoria = ?"
            params.append(categoria)
        if texto:
            sql += " AND texto LIKE ?"
            params.append(f"%{texto}%")
        if articulo_id:
            sql += " AND articulo_id = ?"
            params.append(articulo_id)
        sql += " ORDER BY confianza DESC"
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def indice_global(self, categoria: str = None) -> dict:
        """
        Retorna {entidad: [articulo_id, ...]} para todas las entidades.
        Si categoria, filtra por categoría.
        """
        sql = "SELECT texto, articulo_id FROM entidades"
        params = []
        if categoria:
            sql += " WHERE categoria = ?"
            params.append(categoria)
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()

        indice = {}
        for row in rows:
            texto, art_id = row["texto"], row["articulo_id"]
            if texto not in indice:
                indice[texto] = []
            if art_id not in indice[texto]:
                indice[texto].append(art_id)
        return indice

    # ── Zonas de anotación ─────────────────────────────────────────────────────

    def guardar_zonas_anotacion(self, articulo_id: str, zonas: list[dict]):
        """Reemplaza todas las zonas del artículo."""
        with self._conn() as conn:
            conn.execute(
                "DELETE FROM zonas_anotacion WHERE articulo_id = ?", (articulo_id,)
            )
            conn.executemany("""
                INSERT INTO zonas_anotacion
                    (articulo_id, tipo, x1, y1, x2, y2,
                     texto_ocr, texto_manual, confianza_ocr, fuente_det, verificada)
                VALUES
                    (:articulo_id, :tipo, :x1, :y1, :x2, :y2,
                     :texto_ocr, :texto_manual, :confianza_ocr, :fuente_det, :verificada)
            """, [{
                "articulo_id":  articulo_id,
                "tipo":         z.get("tipo", "articulo"),
                "x1":           z.get("x1", z.get("bbox", [0,0,0,0])[0]),
                "y1":           z.get("y1", z.get("bbox", [0,0,0,0])[1]),
                "x2":           z.get("x2", z.get("bbox", [0,0,0,0])[2]),
                "y2":           z.get("y2", z.get("bbox", [0,0,0,0])[3]),
                "texto_ocr":    z.get("texto_ocr"),
                "texto_manual": z.get("texto_manual"),
                "confianza_ocr":z.get("confianza_ocr", 0.0),
                "fuente_det":   z.get("fuente", "manual"),
                "verificada":   int(z.get("verificada", False)),
            } for z in zonas])

    def obtener_zonas_anotacion(self, articulo_id: str) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM zonas_anotacion WHERE articulo_id = ? ORDER BY id",
                (articulo_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Tono editorial ─────────────────────────────────────────────────────────

    def guardar_tono(self, articulo_id: str, resultado: dict):
        with self._conn() as conn:
            conn.execute("DELETE FROM tono WHERE articulo_id = ?", (articulo_id,))
            conn.execute("""
                INSERT INTO tono (articulo_id, tono_principal, tono_secundario,
                                  confianza, resumen, indicadores, fuente)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                articulo_id,
                resultado.get("tono_principal", ""),
                resultado.get("tono_secundario", ""),
                resultado.get("confianza", 0.0),
                resultado.get("resumen", ""),
                json.dumps(resultado.get("indicadores", []), ensure_ascii=False),
                resultado.get("fuente", "claude_api"),
            ))

    def obtener_tono(self, articulo_id: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM tono WHERE articulo_id = ? ORDER BY id DESC LIMIT 1",
                (articulo_id,)
            ).fetchone()
            if not row:
                return None
            d = dict(row)
            try:
                d["indicadores"] = json.loads(d["indicadores"] or "[]")
            except Exception:
                d["indicadores"] = []
            return d

    # ── Co-ocurrencias ─────────────────────────────────────────────────────────

    def guardar_coocurrencia(self, entidad_a: str, entidad_b: str,
                              categoria: str, articulo_id: str):
        """Incrementa peso o inserta par de co-ocurrencia."""
        a, b = sorted([entidad_a, entidad_b])
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id, articulo_ids, peso FROM coocurrencias WHERE entidad_a=? AND entidad_b=? AND categoria=?",
                (a, b, categoria)
            ).fetchone()
            if row:
                ids = json.loads(row["articulo_ids"] or "[]")
                if articulo_id not in ids:
                    ids.append(articulo_id)
                conn.execute(
                    "UPDATE coocurrencias SET peso = peso + 1, articulo_ids = ? WHERE id = ?",
                    (json.dumps(ids), row["id"])
                )
            else:
                conn.execute(
                    "INSERT INTO coocurrencias (entidad_a, entidad_b, categoria, peso, articulo_ids) VALUES (?,?,?,1,?)",
                    (a, b, categoria, json.dumps([articulo_id]))
                )

    def coocurrencias(self, categoria: str = None, min_peso: int = 2) -> list[dict]:
        sql = "SELECT * FROM coocurrencias WHERE peso >= ?"
        params = [min_peso]
        if categoria:
            sql += " AND categoria = ?"
            params.append(categoria)
        sql += " ORDER BY peso DESC"
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                try:
                    d["articulo_ids"] = json.loads(d.get("articulo_ids") or "[]")
                except Exception:
                    d["articulo_ids"] = []
                result.append(d)
            return result

    # ── Grafo: entidades canónicas + relaciones (tripletas) ──────────────────────

    @staticmethod
    def _normalizar_nombre(nombre: str) -> str:
        """Nombre canónico: minúsculas, sin tildes, espacios colapsados."""
        import unicodedata
        s = unicodedata.normalize("NFKD", str(nombre or ""))
        s = "".join(c for c in s if not unicodedata.combining(c))
        return " ".join(s.lower().split())

    @staticmethod
    def _slug(nombre_norm: str) -> str:
        """Slug ASCII para el id estable (sin espacios ni símbolos)."""
        import re
        s = re.sub(r"[^a-z0-9]+", "-", nombre_norm).strip("-")
        return s or "sin-nombre"

    @staticmethod
    def id_canonico(tipo: str, nombre: str) -> str:
        """id estable: '<tipo>:<slug>'. Determinista — mismo nombre → mismo id."""
        nn = Repositorio._normalizar_nombre(nombre)
        return f"{tipo}:{Repositorio._slug(nn)}"

    def guardar_entidad_canonica(self, tipo: str, nombre: str,
                                 atributos: dict = None,
                                 wikidata_id: str = None,
                                 wikidata_uri: str = None,
                                 confianza: float = 1.0,
                                 fuente: str = "manual") -> str:
        """
        Inserta o actualiza una entidad canónica. Retorna su id estable.
        El id se deriva de (tipo, nombre) → idempotente.
        """
        nn = self._normalizar_nombre(nombre)
        eid = f"{tipo}:{self._slug(nn)}"
        attrs_json = json.dumps(atributos or {}, ensure_ascii=False)
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO entidades_canonicas
                    (id, tipo, nombre, nombre_norm, atributos,
                     wikidata_id, wikidata_uri, confianza, fuente)
                VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    nombre       = excluded.nombre,
                    atributos    = excluded.atributos,
                    wikidata_id  = COALESCE(excluded.wikidata_id, entidades_canonicas.wikidata_id),
                    wikidata_uri = COALESCE(excluded.wikidata_uri, entidades_canonicas.wikidata_uri),
                    confianza    = excluded.confianza,
                    fuente       = excluded.fuente,
                    modificado   = datetime('now')
            """, (eid, tipo, nombre, nn, attrs_json,
                  wikidata_id, wikidata_uri, confianza, fuente))
        return eid

    def obtener_entidad_canonica(self, entidad_id: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM entidades_canonicas WHERE id = ?", (entidad_id,)
            ).fetchone()
            if not row:
                return None
            d = dict(row)
            try:
                d["atributos"] = json.loads(d.get("atributos") or "{}")
            except Exception:
                d["atributos"] = {}
            return d

    def listar_entidades_canonicas(self, tipo: str = None) -> list[dict]:
        sql = "SELECT * FROM entidades_canonicas"
        params = []
        if tipo:
            sql += " WHERE tipo = ?"
            params.append(tipo)
        sql += " ORDER BY n_menciones DESC, nombre"
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["atributos"] = json.loads(d.get("atributos") or "{}")
            except Exception:
                d["atributos"] = {}
            result.append(d)
        return result

    def vincular_mencion(self, mencion_id: int, canonica_id: str,
                         fuente: str = "auto"):
        """Asocia una mención (entidades.id) a una entidad canónica."""
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO menciones_canonicas (mencion_id, canonica_id, fuente)
                VALUES (?,?,?)
                ON CONFLICT(mencion_id) DO UPDATE SET
                    canonica_id = excluded.canonica_id,
                    fuente      = excluded.fuente
            """, (mencion_id, canonica_id, fuente))
            # recalcular n_menciones de la canónica
            conn.execute("""
                UPDATE entidades_canonicas SET n_menciones = (
                    SELECT COUNT(*) FROM menciones_canonicas WHERE canonica_id = ?
                ) WHERE id = ?
            """, (canonica_id, canonica_id))

    def fundir_menciones_en_canonicas(self, fuente: str = "ner") -> dict:
        """
        Funde las menciones de la tabla `entidades` en entidades canónicas,
        agrupando por (categoría→tipo, nombre_norm). Idempotente: re-ejecutar
        no duplica. Retorna {canonicas, menciones_vinculadas}.

        Mapa categoría NER → tipo canónico.
        """
        cat_a_tipo = {
            "personas":            "persona",
            "organizaciones":      "institucion",
            "lugares":             "lugar",
            "obras":               "obra",
            "obras_publicaciones": "publicacion",
            "eventos":             "evento",
            "cargos":              "otro",
        }
        n_can = 0
        n_vinc = 0
        with self._conn() as conn:
            menciones = conn.execute(
                "SELECT id, texto, categoria, confianza, wikidata_id, wikidata_uri "
                "FROM entidades"
            ).fetchall()

        for m in menciones:
            tipo = cat_a_tipo.get(m["categoria"], "otro")
            nombre = (m["texto"] or "").strip()
            if not nombre:
                continue
            eid = self.guardar_entidad_canonica(
                tipo=tipo, nombre=nombre,
                wikidata_id=m["wikidata_id"], wikidata_uri=m["wikidata_uri"],
                confianza=float(m["confianza"] or 0.0) or 1.0,
                fuente=fuente,
            )
            self.vincular_mencion(m["id"], eid, fuente="auto")
            n_vinc += 1

        with self._conn() as conn:
            n_can = conn.execute(
                "SELECT COUNT(*) FROM entidades_canonicas"
            ).fetchone()[0]
        return {"canonicas": n_can, "menciones_vinculadas": n_vinc}

    def guardar_relacion(self, origen_id: str, predicado: str,
                         destino_id: str = None, destino_pagina: str = None,
                         evidencia: str = None, confianza: float = 1.0,
                         fuente: str = "manual") -> int:
        """Inserta una tripleta. Retorna su id (o el existente si ya estaba).

        destino_id se guarda NULL cuando el objeto es una página (la FK ignora
        NULL). La unicidad se garantiza con el índice idx_relaciones_unica sobre
        COALESCE(...); el ON CONFLICT apunta a esas mismas expresiones.
        """
        d_id = destino_id or None
        d_pag = destino_pagina or None
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO relaciones
                    (origen_id, predicado, destino_id, destino_pagina,
                     evidencia, confianza, fuente)
                VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(origen_id, predicado,
                            COALESCE(destino_id, ''), COALESCE(destino_pagina, ''))
                DO UPDATE SET
                    confianza = excluded.confianza,
                    evidencia = COALESCE(excluded.evidencia, relaciones.evidencia)
            """, (origen_id, predicado, d_id, d_pag,
                  evidencia, confianza, fuente))
            row = conn.execute("""
                SELECT id FROM relaciones
                WHERE origen_id=? AND predicado=?
                  AND COALESCE(destino_id,'')=COALESCE(?,'')
                  AND COALESCE(destino_pagina,'')=COALESCE(?,'')
            """, (origen_id, predicado, d_id, d_pag)).fetchone()
            return row["id"] if row else 0

    def listar_relaciones(self, origen_id: str = None, predicado: str = None,
                          destino_id: str = None) -> list[dict]:
        sql = "SELECT * FROM relaciones WHERE 1=1"
        params = []
        if origen_id:
            sql += " AND origen_id = ?"; params.append(origen_id)
        if predicado:
            sql += " AND predicado = ?"; params.append(predicado)
        if destino_id:
            sql += " AND destino_id = ?"; params.append(destino_id)
        sql += " ORDER BY confianza DESC, id"
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def grafo_entidades(self) -> dict:
        """
        Devuelve el grafo de conocimiento como {nodos, aristas} listo para
        export (GEXF/RDF/JSON). nodos = entidades canónicas; aristas = tripletas
        entidad→entidad (las que tienen destino_id).
        """
        nodos = self.listar_entidades_canonicas()
        with self._conn() as conn:
            aristas = [dict(r) for r in conn.execute(
                "SELECT * FROM relaciones WHERE destino_id IS NOT NULL"
            ).fetchall()]
        return {"nodos": nodos, "aristas": aristas}

    # ── Historial IA ───────────────────────────────────────────────────────────

    def registrar_llamada_ia(self, etapa: str, proveedor: str, modelo: str,
                              tokens_entrada: int = 0, tokens_salida: int = 0,
                              costo_usd: float = 0.0, ok: bool = True,
                              articulo_id: str = None):
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO historial_ia
                    (articulo_id, etapa, proveedor, modelo,
                     tokens_entrada, tokens_salida, costo_usd, ok)
                VALUES (?,?,?,?,?,?,?,?)
            """, (articulo_id, etapa, proveedor, modelo,
                  tokens_entrada, tokens_salida, costo_usd, int(ok)))

    def costo_total_ia(self) -> float:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT SUM(costo_usd) FROM historial_ia WHERE ok = 1"
            ).fetchone()
            return float(row[0] or 0.0)

    def resumen_uso_ia(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT etapa, proveedor, modelo,
                       COUNT(*) as llamadas,
                       SUM(tokens_entrada) as tokens_in,
                       SUM(tokens_salida) as tokens_out,
                       SUM(costo_usd) as costo_total
                FROM historial_ia
                WHERE ok = 1
                GROUP BY etapa, proveedor, modelo
                ORDER BY costo_total DESC
            """).fetchall()
            return [dict(r) for r in rows]

    # ── Bitácora de investigación ──────────────────────────────────────────────

    def insertar_nota(self, nota: dict) -> int:
        """Inserta una nota y retorna su id."""
        with self._conn() as conn:
            cur = conn.execute("""
                INSERT INTO notas_investigacion
                    (tipo, estado, texto, etiquetas,
                     ref_numero, ref_pagina, ref_art_id, modulo_origen)
                VALUES (?,?,?,?,?,?,?,?)
            """, (
                nota.get("tipo", "libre"),
                nota.get("estado"),
                nota.get("texto", ""),
                json.dumps(nota.get("etiquetas", []), ensure_ascii=False),
                nota.get("ref_numero", ""),
                nota.get("ref_pagina", ""),
                nota.get("ref_art_id", ""),
                nota.get("modulo_origen", ""),
            ))
            return cur.lastrowid

    def actualizar_nota(self, nota_id: int, campos: dict):
        """Actualiza campos específicos de una nota por id."""
        permitidos = {"tipo", "estado", "texto", "etiquetas",
                      "ref_numero", "ref_pagina", "ref_art_id", "modulo_origen"}
        updates = {k: v for k, v in campos.items() if k in permitidos}
        if not updates:
            return
        if "etiquetas" in updates and isinstance(updates["etiquetas"], list):
            updates["etiquetas"] = json.dumps(updates["etiquetas"], ensure_ascii=False)
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        vals = list(updates.values()) + [nota_id]
        with self._conn() as conn:
            conn.execute(
                f"UPDATE notas_investigacion SET {set_clause}, "
                f"modificado = datetime('now') WHERE id = ?",
                vals,
            )

    def eliminar_nota(self, nota_id: int):
        with self._conn() as conn:
            conn.execute("DELETE FROM notas_investigacion WHERE id = ?", (nota_id,))

    def listar_notas(
        self,
        tipo: str = None,
        estado: str = None,
        modulo: str = None,
        q: str = None,
    ) -> list[dict]:
        """Lista notas con filtros opcionales. q busca en texto y etiquetas."""
        sql = "SELECT * FROM notas_investigacion WHERE 1=1"
        params: list = []
        if tipo:
            sql += " AND tipo = ?"; params.append(tipo)
        if estado:
            sql += " AND estado = ?"; params.append(estado)
        if modulo:
            sql += " AND modulo_origen = ?"; params.append(modulo)
        if q:
            sql += " AND (texto LIKE ? OR etiquetas LIKE ?)";
            params += [f"%{q}%", f"%{q}%"]
        sql += " ORDER BY creado DESC"
        with self._conn() as conn:
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
