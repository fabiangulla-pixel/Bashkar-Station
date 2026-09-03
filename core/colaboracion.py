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
    arts_orig = bashkar_original.get("articulos", {})
    arts_mod  = bashkar_modificado.get("articulos", {})
    cambios_ocr = {}
    for art_id, art in arts_mod.items():
        orig_txt = arts_orig.get(art_id, {}).get("texto_limpio", "")
        mod_txt  = art.get("texto_limpio", "")
        if orig_txt != mod_txt and mod_txt:
            cambios_ocr[art_id] = {
                "antes": orig_txt[:200],
                "despues": mod_txt[:200],
            }
    if cambios_ocr:
        cambios["ocr"] = cambios_ocr

    # Hash del estado original para validación
    hash_orig = hashlib.md5(
        json.dumps(bashkar_original, sort_keys=True, ensure_ascii=False).encode()
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
    if "ner" in cambios:
        ner = resultado.setdefault("indice_ner_global", {})
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
        arts = resultado.setdefault("articulos", {})
        for art_id, cambio in cambios["ocr"].items():
            if art_id in arts:
                arts[art_id]["texto_limpio"] = cambio["despues"]
                arts[art_id]["_editado_por"] = investigador
                _log(f"OCR ~{art_id} [{investigador}]")

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
    })

    return resultado


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
<tr><th>Investigador</th><th>Fecha</th><th>Cambios NER</th><th>Cambios OCR</th><th>Notas</th></tr>
{filas or '<tr><td colspan="5">Sin contribuciones registradas</td></tr>'}
</table>
</body></html>"""

    ruta.write_text(html, encoding="utf-8")
    return ruta
