"""core/colaboracion.py — Colaboración basada en archivos .bashkar.patch.

Permite a múltiples investigadores trabajar sobre el mismo corpus:
  - Exportar parche con correcciones/validaciones locales
  - Importar y mezclar parches de otros investigadores
  - Generar reporte de trazabilidad de contribuciones
  - Resolución de conflictos básica (el más reciente gana, o manual)
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Callable

PATCH_VERSION = "1.0"


def _get_indice_ner(bashkar: dict) -> dict:
    """Ubica el índice NER en un proyecto .bashkar.

    En proyectos reales (post-migración a SQLite) el índice NER vive anidado
    en ``resultados.indice_ner_global``, no en la raíz del dict. Algunas
    llamadas de la GUI (p. ej. al construir el estado "modificado" antes de
    generar un parche) sí lo colocan en la raíz. Se revisan ambas ubicaciones
    para no comparar un índice real contra un `{}` espurio.
    """
    if bashkar.get("indice_ner_global"):
        return bashkar["indice_ner_global"]
    return bashkar.get("resultados", {}).get("indice_ner_global", {}) or {}


# Alias público: app.py y otros frontends deben leer el índice por aquí y no
# por `proyecto["indice_ner_global"]`, que en un .bashkar real no existe.
indice_ner_de = _get_indice_ner


def _get_articulos(bashkar: dict) -> dict:
    """Artículos con texto embebido en el dict del proyecto, si los hay.

    Ojo: un .bashkar real (v11) NO los trae. Sus artículos viven en el SQLite
    hermano y en ``<stem>/articulos.csv`` (que además no guarda la columna
    'texto'). Solo pipeline_maestro escribe "articulos" en la raíz. Se acepta
    también la forma de lista para no depender de cuál de los dos productores
    generó el archivo.
    """
    arts = bashkar.get("articulos")
    if arts is None:
        arts = (bashkar.get("resultados", {}) or {}).get("articulos")
    if isinstance(arts, list):
        return {str(a.get("id", i)): a for i, a in enumerate(arts)
                if isinstance(a, dict)}
    return arts if isinstance(arts, dict) else {}


def _ruta_db_de(bashkar: dict) -> Path | None:
    """SQLite hermano del proyecto, si se puede ubicar y existe.

    Un .bashkar v11 sano guarda "db" como ruta ABSOLUTA (ver
    project_manager._ruta_db y el bug de pérdida de datos de la sesión 65). Los
    migrados por versiones viejas dejaron un nombre pelado; para esos hace falta
    saber dónde está el .bashkar, que por convención del proyecto viaja en la
    clave "_ruta" (misma que usa core/comparador.py).
    """
    valor = (bashkar.get("db") or "").strip()
    if not valor:
        return None
    db = Path(valor)
    if not db.is_absolute():
        base = bashkar.get("_ruta")
        if not base:
            return None
        db = Path(base).parent / db
    return db if db.exists() else None


def _normalizaciones(bashkar: dict) -> dict[str, dict]:
    """Correcciones manuales de OCR del proyecto, indexadas por "numero||pagina".

    En v11 el texto NO está en el dict: vive en el SQLite hermano. Las
    correcciones que un investigador hace a mano quedan en la tabla
    ``normalizaciones`` (numero, pagina, ocr_crudo, norm_usuario, ts_usuario),
    no en la tabla ``ocr`` —que solo guarda lo que produjeron los motores—. Por
    eso `crear_parche` no generaba ningún cambio de OCR en proyectos v11: leía
    un sitio donde ese trabajo nunca estuvo.

    Se devuelven solo las filas donde el usuario realmente cambió algo respecto
    del crudo: esas, y solo esas, son su aporte compartible.
    """
    db = _ruta_db_de(bashkar)
    if db is None:
        return {}
    import sqlite3
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    except Exception:
        return {}
    try:
        filas = con.execute(
            "SELECT numero, pagina, ocr_crudo, norm_usuario, ts_usuario "
            "FROM normalizaciones "
            "WHERE COALESCE(norm_usuario, '') <> '' "
            "  AND norm_usuario <> COALESCE(ocr_crudo, '')"
        ).fetchall()
    except Exception:
        # Proyecto sin la tabla (v10, o base recién creada).
        return {}
    finally:
        con.close()
    return {
        f"{f[0]}||{f[1]}": {
            "numero": f[0],
            "pagina": f[1],
            "antes": f[2] or "",
            "despues": f[3] or "",
            "ts_usuario": f[4] or "",
        }
        for f in filas
    }


# ── Crear parche ──────────────────────────────────────────────────────────────

def crear_parche(
    bashkar_original: dict,
    bashkar_modificado: dict,
    investigador: str,
    notas: str = "",
) -> dict:
    """
    Genera un parche con las diferencias entre el original y el modificado.
    El parche contiene solo los cambios (NER validado, correcciones OCR, etc.)
    """
    cambios = {}

    # Comparar índice NER
    ner_orig = _get_indice_ner(bashkar_original)
    ner_mod  = _get_indice_ner(bashkar_modificado)
    cambios_ner = {}
    for cat in set(list(ner_orig.keys()) + list(ner_mod.keys())):
        orig_ents = ner_orig.get(cat, {})
        mod_ents  = ner_mod.get(cat, {})
        if orig_ents != mod_ents:
            cambios_ner[cat] = {
                "agregadas":   {k: v for k, v in mod_ents.items() if k not in orig_ents},
                "eliminadas":  {k: v for k, v in orig_ents.items() if k not in mod_ents},
                "modificadas": {k: v for k, v in mod_ents.items()
                                if k in orig_ents and orig_ents[k] != mod_ents[k]},
            }
    if cambios_ner:
        cambios["ner"] = cambios_ner

    # Comparar textos OCR mejorados
    arts_orig = _get_articulos(bashkar_original)
    arts_mod  = _get_articulos(bashkar_modificado)
    cambios_ocr = {}
    for art_id, art in arts_mod.items():
        orig_txt = arts_orig.get(art_id, {}).get("texto_limpio", "")
        mod_txt  = art.get("texto_limpio", "")
        if orig_txt != mod_txt and mod_txt:
            # Texto COMPLETO, no un recorte: `aplicar_parche` escribe
            # "despues" como el texto del articulo, asi que truncar aqui a 200
            # caracteres borraba el resto del articulo en el proyecto receptor.
            cambios_ocr[art_id] = {
                "antes": orig_txt,
                "despues": mod_txt,
            }
    if cambios_ocr:
        cambios["ocr"] = cambios_ocr

    # Correcciones manuales de OCR de un proyecto v11 (tabla `normalizaciones`
    # del SQLite). El bloque de arriba solo ve texto embebido en el dict, que un
    # .bashkar real no trae: sin esto, un parche de un proyecto v11 salía
    # siempre sin una sola corrección de OCR.
    norm_mod = _normalizaciones(bashkar_modificado)
    if norm_mod:
        db_orig = _ruta_db_de(bashkar_original)
        db_mod = _ruta_db_de(bashkar_modificado)
        # Cuando ambos lados son la MISMA base no hay contra qué diferenciar: el
        # aporte del investigador es, por definición, toda corrección suya que
        # se aparta del crudo (cada fila trae su propio antes/después). Si son
        # bases distintas, se omite lo que el otro proyecto ya tiene igual.
        previas = _normalizaciones(bashkar_original) if db_orig != db_mod else {}
        cambios_norm = {
            clave: valor for clave, valor in norm_mod.items()
            if previas.get(clave, {}).get("despues") != valor["despues"]
        }
        if cambios_norm:
            cambios["normalizaciones"] = cambios_norm

    # Hash del estado original para validación.
    #
    # Se excluyen las claves privadas (las que empiezan por "_", como "_ruta"):
    # son contexto en memoria del equipo que abrió el proyecto, no parte del
    # documento. Incluirlas daba un hash distinto en cada máquina para el MISMO
    # proyecto, que es justo lo contrario de lo que un hash de validación debe
    # hacer.
    base_hash = {k: v for k, v in bashkar_original.items()
                 if not str(k).startswith("_")}
    hash_orig = hashlib.md5(
        json.dumps(base_hash, sort_keys=True, ensure_ascii=False,
                   default=str).encode()
    ).hexdigest()[:12]

    return {
        "_version_parche": PATCH_VERSION,
        "_hash_base": hash_orig,
        "_investigador": investigador,
        "_fecha": datetime.now().isoformat(),
        "_notas": notas,
        "cambios": cambios,
    }


def exportar_parche(parche: dict, ruta: Path) -> Path:
    """Guarda el parche como archivo .bashkar.patch."""
    ruta = Path(ruta)
    if not ruta.suffix == ".patch":
        ruta = ruta.with_suffix(".bashkar.patch")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(parche, indent=2, ensure_ascii=False), encoding="utf-8")
    return ruta


# ── Importar parche ───────────────────────────────────────────────────────────

def cargar_parche(ruta: Path) -> dict:
    """Carga un archivo .bashkar.patch."""
    ruta = Path(ruta)
    return json.loads(ruta.read_text(encoding="utf-8"))


def aplicar_parche(
    bashkar: dict,
    parche: dict,
    estrategia_conflicto: str = "mas_reciente",
    callback: Callable | None = None,
) -> dict:
    """
    Aplica un parche a un proyecto .bashkar.
    estrategia_conflicto: 'mas_reciente' | 'manual'
    Retorna el proyecto actualizado.
    """
    import copy
    resultado = copy.deepcopy(bashkar)
    cambios = parche.get("cambios", {})
    investigador = parche.get("_investigador", "desconocido")

    def _log(msg: str):
        if callback:
            callback(msg)

    # Aplicar cambios NER
    #
    # Se escribe en resultados.indice_ner_global, que es de donde
    # project_manager.cargar_proyecto lee el índice. Escribirlo en la raíz
    # —como se hacía— dejaba el parche aplicado invisible: al reabrir el
    # proyecto la GUI leía `resultados` y encontraba el índice viejo, mientras
    # la copia parcheada quedaba en una clave raíz que nadie lee (y que además
    # es la que confundía a crear_parche, bug 6a24d4e).
    if "ner" in cambios:
        ner = _get_indice_ner(resultado)
        resultado.setdefault("resultados", {})["indice_ner_global"] = ner
        if "indice_ner_global" in resultado:
            # El archivo ya traía la copia en la raíz: se mantiene apuntando al
            # mismo objeto para que las dos no se separen.
            resultado["indice_ner_global"] = ner
        for cat, ops in cambios["ner"].items():
            cat_dict = ner.setdefault(cat, {})
            for ent, arts in ops.get("agregadas", {}).items():
                cat_dict[ent] = arts
                _log(f"NER +{cat}/{ent} [{investigador}]")
            for ent in ops.get("eliminadas", {}).keys():
                cat_dict.pop(ent, None)
                _log(f"NER -{cat}/{ent} [{investigador}]")
            for ent, arts in ops.get("modificadas", {}).items():
                cat_dict[ent] = arts
                _log(f"NER ~{cat}/{ent} [{investigador}]")

    # Aplicar cambios OCR
    if "ocr" in cambios:
        arts = _get_articulos(resultado)
        if arts:
            resultado["articulos"] = arts
        for art_id, cambio in cambios["ocr"].items():
            if art_id in arts:
                arts[art_id]["texto_limpio"] = cambio["despues"]
                arts[art_id]["_editado_por"] = investigador
                _log(f"OCR ~{art_id} [{investigador}]")

    # Aplicar correcciones manuales de OCR (v11: van al SQLite, no al dict).
    #
    # `estrategia_conflicto` decide qué pasa cuando el receptor ya corrigió esa
    # misma página: "mas_reciente" compara `ts_usuario` y deja ganar al más
    # nuevo; "manual" no pisa nada de lo que el receptor ya tenga.
    n_norm = 0
    if "normalizaciones" in cambios:
        n_norm = _aplicar_normalizaciones(
            resultado, cambios["normalizaciones"], investigador,
            estrategia_conflicto, _log,
        )

    # Registrar contribución
    resultado.setdefault("_contribuciones", []).append({
        "investigador": investigador,
        "fecha": parche.get("_fecha"),
        "notas": parche.get("_notas", ""),
        "n_cambios_ner": sum(
            len(ops.get("agregadas", {})) + len(ops.get("eliminadas", {})) + len(ops.get("modificadas", {}))
            for ops in cambios.get("ner", {}).values()
        ),
        "n_cambios_ocr": len(cambios.get("ocr", {})),
        "n_cambios_normalizacion": n_norm,
    })

    return resultado


def _aplicar_normalizaciones(bashkar: dict, entradas: dict, investigador: str,
                             estrategia: str, log) -> int:
    """Escribe las correcciones de OCR del parche en la tabla `normalizaciones`.

    Devuelve cuántas se aplicaron de verdad. Si no se puede ubicar la base, no
    se inventa: se avisa y se devuelve 0, en vez de reportar un éxito falso.
    """
    db = _ruta_db_de(bashkar)
    if db is None:
        log("⚠ No se encontró el SQLite del proyecto: "
            "correcciones de OCR NO aplicadas.")
        return 0

    import sqlite3
    aplicadas = 0
    con = sqlite3.connect(str(db), timeout=30)
    try:
        con.execute("PRAGMA journal_mode = WAL")
        # Un proyecto que nunca pasó por el panel de Normalizar no tiene la
        # tabla todavía; sin esto el parche reventaba al recibirlo.
        from datos.schema import SCHEMA_NORMALIZACIONES
        con.executescript(SCHEMA_NORMALIZACIONES)
        for entrada in entradas.values():
            numero = entrada.get("numero", "")
            pagina = entrada.get("pagina", "")
            texto = entrada.get("despues", "")
            if not numero or not pagina or not texto:
                continue
            fila = con.execute(
                "SELECT norm_usuario, ts_usuario, ocr_crudo FROM normalizaciones "
                "WHERE numero = ? AND pagina = ?", (numero, pagina),
            ).fetchone()
            if fila and (fila[0] or ""):
                if estrategia == "manual":
                    log(f"↷ conflicto sin resolver: {numero} {pagina}")
                    continue
                if (fila[1] or "") >= (entrada.get("ts_usuario") or ""):
                    log(f"↷ {numero} {pagina}: la versión local es más reciente")
                    continue
            crudo = (fila[2] if fila else None) or entrada.get("antes", "")
            con.execute(
                "INSERT INTO normalizaciones "
                "  (numero, pagina, ocr_crudo, norm_usuario, ts_usuario) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(numero, pagina) DO UPDATE SET "
                "  norm_usuario = excluded.norm_usuario, "
                "  ts_usuario   = excluded.ts_usuario",
                (numero, pagina, crudo, texto, entrada.get("ts_usuario", "")),
            )
            aplicadas += 1
            log(f"OCR ~{numero} {pagina} [{investigador}]")
        con.commit()
    finally:
        con.close()
    return aplicadas


# ── Reporte de trazabilidad ───────────────────────────────────────────────────

def reporte_trazabilidad(bashkar: dict) -> str:
    """Genera un reporte de texto con todas las contribuciones al proyecto."""
    contribs = bashkar.get("_contribuciones", [])
    if not contribs:
        return "Sin contribuciones registradas."

    lineas = ["=== Trazabilidad de colaboraciones ===\n"]
    for c in contribs:
        lineas.append(
            f"Investigador : {c.get('investigador', '?')}\n"
            f"Fecha        : {c.get('fecha', '?')}\n"
            f"Cambios NER  : {c.get('n_cambios_ner', 0)}\n"
            f"Cambios OCR  : {c.get('n_cambios_ocr', 0)}\n"
            f"Notas        : {c.get('notas', '')}\n"
            + "-" * 40
        )
    return "\n".join(lineas)


def exportar_trazabilidad_html(bashkar: dict, ruta: Path) -> Path:
    """Genera HTML con reporte de trazabilidad."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)

    contribs = bashkar.get("_contribuciones", [])
    filas = ""
    for c in contribs:
        filas += (
            f"<tr><td>{c.get('investigador','?')}</td>"
            f"<td>{c.get('fecha','?')[:16]}</td>"
            f"<td>{c.get('n_cambios_ner',0)}</td>"
            f"<td>{c.get('n_cambios_ocr',0)}</td>"
            f"<td>{c.get('n_cambios_normalizacion',0)}</td>"
            f"<td>{c.get('notas','')}</td></tr>"
        )

    html = f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><title>Trazabilidad — Bashkar Station</title>
<style>
body{{font-family:'Segoe UI',sans-serif;background:#0f0f23;color:#e0e0e0;padding:20px}}
h1{{color:#a78bfa}}
table{{width:100%;border-collapse:collapse}}
th{{background:#1e293b;color:#7dd3fc;padding:8px}}
td{{padding:6px 8px;border-bottom:1px solid #1e293b}}
</style></head>
<body>
<h1>Trazabilidad de colaboraciones</h1>
<p>Proyecto: {bashkar.get('nombre','')}</p>
<table>
<tr><th>Investigador</th><th>Fecha</th><th>Cambios NER</th><th>Cambios OCR</th><th>Correcciones OCR</th><th>Notas</th></tr>
{filas or '<tr><td colspan="6">Sin contribuciones registradas</td></tr>'}
</table>
</body></html>"""

    ruta.write_text(html, encoding="utf-8")
    return ruta
