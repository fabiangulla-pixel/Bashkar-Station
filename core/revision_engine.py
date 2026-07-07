"""Revisión human-in-the-loop de entidades NER (metodología DH: anotación validada).

Tras el NER automático, el investigador necesita poder **validar, corregir o
descartar** entidades para que el corpus sea publicable. Este módulo:

  1. Puntúa cada entidad del índice global con ``confianza_engine`` y arma una
     cola de las dudosas (amarillo/rojo).
  2. Persiste las decisiones del usuario en la tabla ``revision_entidades``
     (verificada / descartada / renombrada), con trazabilidad (quién, cuándo).
  3. Re-aplica esas decisiones al índice global en análisis futuros
     (``aplicar_revisiones``): descarta lo rechazado y fusiona renombres.

Portado de ¡Quac! y adaptado a Bashkar: la persistencia trabaja directamente
sobre una conexión ``sqlite3`` (con ``row_factory = sqlite3.Row``), el patrón que
usa ``datos/repositorio.py``, sin acoplarse a un wrapper concreto. Reutiliza
``confianza_engine`` (mismo en ambos proyectos); no reimplementa el scoring.

El índice global de Bashkar tiene la forma ``{categoria: {entidad: [art_ids]}}``
(ver ``ner_engine.actualizar_indice_global``), que es justo lo que este módulo
espera.
"""

from __future__ import annotations

from datetime import UTC, datetime

from core import confianza_engine

# Decisiones posibles del revisor
PENDIENTE = "pendiente"
VERIFICADA = "verificada"
DESCARTADA = "descartada"
RENOMBRADA = "renombrada"

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS revision_entidades (
    nombre        TEXT NOT NULL,
    categoria     TEXT NOT NULL,
    decision      TEXT NOT NULL DEFAULT 'pendiente',
    nombre_nuevo  TEXT DEFAULT '',
    score         REAL DEFAULT 0,
    nivel         TEXT DEFAULT '',
    n_articulos   INTEGER DEFAULT 0,
    editado_por   TEXT DEFAULT '',
    fecha         TEXT DEFAULT '',
    PRIMARY KEY (nombre, categoria)
);
"""

# Categorías por defecto del índice NER de Bashkar (ver ner_engine.CATEGORIAS)
CATEGORIAS_DEFECTO = ("personas", "lugares", "organizaciones")


def _asegurar_tabla(con):
    con.executescript(_ESQUEMA)
    con.commit()


def _score_entidad(nombre: str, n_articulos: int, kb: set | None) -> float:
    """Puntúa la confianza de una entidad SIN LLM (0–1).

    La señal principal es la **frecuencia** (en cuántos artículos aparece) más un
    bono si está en la base de conocimiento del investigador (entidades semilla
    declaradas / ya verificadas).

    - en KB                  → siempre confiable (1.0): el usuario la respalda.
    - en ≥3 artículos        → confiable (≥0.80, verde).
    - en 2 artículos         → revisar (amarillo).
    - en 1 artículo          → validar (rojo): lo más propenso a ruido NER.
    """
    if kb and nombre.lower() in kb:
        return 1.0
    # frecuencia saturando: 1→0.30, 2→0.55, 3→0.80, 4+→≥1.0
    return round(min(1.0, 0.05 + 0.25 * n_articulos), 3)


def construir_cola(indice_global: dict, kb: set | None = None,
                   categorias=CATEGORIAS_DEFECTO) -> list[dict]:
    """Arma la cola de entidades dudosas (nivel amarillo/rojo) para revisar.

    ``kb``: conjunto de formas (en minúscula) de entidades ya respaldadas
    (semillas o verificaciones previas); reciben score 1.0 y no entran en la cola.
    """
    kb = {k.lower() for k in kb} if kb else set()
    cola = []
    for cat in categorias:
        entidades = indice_global.get(cat, {})
        if not isinstance(entidades, dict):
            continue
        for nombre, arts in entidades.items():
            n = len(arts)
            score = _score_entidad(nombre, n, kb)
            nivel = confianza_engine.nivel_confianza(score)
            if nivel != confianza_engine.VERDE:   # solo dudosas
                cola.append({
                    "nombre": nombre, "categoria": cat, "n_articulos": n,
                    "score": score, "nivel": nivel,
                    "etiqueta": confianza_engine.etiqueta_semaforo(score),
                })
    cola.sort(key=lambda d: (d["score"], -d["n_articulos"]))
    return cola


def guardar_cola(con, cola: list[dict]):
    """Persiste la cola en la BD (sin pisar decisiones ya tomadas)."""
    _asegurar_tabla(con)
    for item in cola:
        cur = con.execute(
            "SELECT decision FROM revision_entidades WHERE nombre=? AND categoria=?",
            (item["nombre"], item["categoria"]))
        row = cur.fetchone()
        if row and row["decision"] != PENDIENTE:
            continue  # no sobrescribir una decisión ya tomada
        con.execute(
            "INSERT OR REPLACE INTO revision_entidades "
            "(nombre, categoria, decision, score, nivel, n_articulos) "
            "VALUES (?,?,?,?,?,?)",
            (item["nombre"], item["categoria"], PENDIENTE,
             item["score"], item["nivel"], item["n_articulos"]))
    con.commit()


def pendientes(con) -> list[dict]:
    _asegurar_tabla(con)
    cur = con.execute(
        "SELECT * FROM revision_entidades WHERE decision=? "
        "ORDER BY score, n_articulos DESC", (PENDIENTE,))
    return [dict(r) for r in cur.fetchall()]


def decidir(con, nombre: str, categoria: str, decision: str,
            nombre_nuevo: str = "", editado_por: str = "usuario") -> bool:
    """Registra la decisión del revisor sobre una entidad."""
    if decision not in (VERIFICADA, DESCARTADA, RENOMBRADA, PENDIENTE):
        raise ValueError(f"Decisión inválida: {decision}")
    _asegurar_tabla(con)
    con.execute(
        "UPDATE revision_entidades SET decision=?, nombre_nuevo=?, editado_por=?, "
        "fecha=? WHERE nombre=? AND categoria=?",
        (decision, nombre_nuevo, editado_por,
         datetime.now(UTC).isoformat(), nombre, categoria))
    con.commit()
    return con.total_changes > 0


def cargar_decisiones(con) -> dict:
    """Devuelve {(nombre,categoria): {decision, nombre_nuevo}} ya resueltas."""
    _asegurar_tabla(con)
    cur = con.execute(
        "SELECT nombre, categoria, decision, nombre_nuevo FROM revision_entidades "
        "WHERE decision != ?", (PENDIENTE,))
    return {(r["nombre"], r["categoria"]):
            {"decision": r["decision"], "nombre_nuevo": r["nombre_nuevo"]}
            for r in cur.fetchall()}


def aplicar_revisiones(indice_global: dict, decisiones: dict) -> dict:
    """Aplica las decisiones del revisor al índice global.

    - DESCARTADA: elimina la entidad.
    - RENOMBRADA: fusiona sus artículos en el nombre nuevo (sin duplicar art_ids).
    - VERIFICADA: se conserva tal cual.
    Modifica en lugar y devuelve el mismo índice.
    """
    for (nombre, categoria), d in decisiones.items():
        entidades = indice_global.get(categoria)
        if not isinstance(entidades, dict) or nombre not in entidades:
            continue
        if d["decision"] == DESCARTADA:
            entidades.pop(nombre, None)
        elif d["decision"] == RENOMBRADA and d["nombre_nuevo"]:
            arts = entidades.pop(nombre, [])
            destino = entidades.setdefault(d["nombre_nuevo"], [])
            for a in arts:
                if a not in destino:
                    destino.append(a)
    return indice_global


def estadisticas(con) -> dict:
    _asegurar_tabla(con)
    cur = con.execute(
        "SELECT decision, COUNT(*) n FROM revision_entidades GROUP BY decision")
    por = {r["decision"]: r["n"] for r in cur.fetchall()}
    return {
        "total": sum(por.values()),
        "pendientes": por.get(PENDIENTE, 0),
        "verificadas": por.get(VERIFICADA, 0),
        "descartadas": por.get(DESCARTADA, 0),
        "renombradas": por.get(RENOMBRADA, 0),
    }
