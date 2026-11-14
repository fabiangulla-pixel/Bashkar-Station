"""core/metadatos_exportacion.py — Lo que las exportaciones dicen del proyecto.

Hasta el 14-nov-2026 el TEI, el BibTeX y el Excel llevaban metadatos fijos:
«Corpus Estampa», «Instituto Caro y Cuervo» como editor, «Bogotá»,
«1930-1940», «enero–junio 1939» y «NER híbrido (spaCy + Claude)» aunque no se
hubiera usado IA. Para otro corpus —o para el propio Estampa— eso es
proveniencia falsa.

Aquí se reúne lo que el proyecto sabe de sí mismo. Lo que no se sabe queda
vacío o como ``desconocido`` (la convención de core/proveniencia): nunca se
rellena con un valor plausible.

Claves que el proyecto puede declarar en ``config`` del ``.bashkar``:

- ``creditos``: lista de ``{"rol": ..., "nombre": ...}`` (financiación,
  institución mentora, digitalización…).
- ``responsable``: quien publica la exportación (persona o entidad).
- ``disponibilidad``: condiciones de uso del corpus (texto).
- ``lugar``: lugar de publicación de la fuente.
"""
from __future__ import annotations

DESCONOCIDO = "desconocido"
_PLACEHOLDERS = {"", "mi publicación", "nan", "none"}


def _limpio(valor) -> str:
    v = str(valor or "").strip()
    return "" if v.lower() in _PLACEHOLDERS else v


def motores_ocr(corpus_meta) -> list[str]:
    """Métodos de extracción realmente usados, según ``corpus_meta``."""
    try:
        if corpus_meta is None or getattr(corpus_meta, "empty", True):
            return []
        if "metodo" not in corpus_meta.columns:
            return []
        return sorted({_limpio(m) for m in corpus_meta["metodo"].dropna() if _limpio(m)})
    except Exception:
        return []


def proveedores_ia(historial_ia) -> list[str]:
    """Proveedores de IA con uso registrado en el historial del proyecto."""
    vistos = []
    for h in historial_ia or []:
        if not isinstance(h, dict):
            continue
        p = _limpio(h.get("proveedor") or h.get("modelo") or "")
        if p and p not in vistos:
            vistos.append(p)
    return vistos


def metadatos_proyecto(st, nombre_proyecto: str = "", historial_ia=None,
                       config: dict | None = None) -> dict:
    """Metadatos reales para exportar, a partir del estado del proyecto."""
    config = config if config is not None else (getattr(st, "config_exportacion", None) or {})
    publicacion = _limpio(getattr(st, "publicacion", ""))
    perfil = getattr(st, "perfil_corpus", None) or {}
    creditos = [c for c in (config.get("creditos") or [])
                if isinstance(c, dict) and _limpio(c.get("nombre"))]
    return {
        "proyecto": _limpio(nombre_proyecto) or publicacion or "Corpus",
        "publicacion": publicacion,
        "periodo": _limpio(getattr(st, "periodo", "")),
        "lugar": _limpio(config.get("lugar") or perfil.get("lugar", "")),
        "responsable": _limpio(config.get("responsable", "")),
        "disponibilidad": _limpio(config.get("disponibilidad", "")),
        "creditos": creditos,
        "idioma": _limpio(perfil.get("idioma", "")) or "Español",
        "herramientas": {
            "ocr": motores_ocr(getattr(st, "corpus_meta", None)),
            "ner": _limpio(getattr(st, "ner_motor", "")),
            "ia": proveedores_ia(historial_ia),
        },
    }


def metadatos_desde_config(config: dict, nombre_proyecto: str = "",
                           ner_motor: str = "") -> dict:
    """Lo mismo que metadatos_proyecto, desde el ``config`` crudo del .bashkar.

    Para la CLI, que no carga un ``Estado``. Sin ``corpus_meta`` a mano, el
    método de extracción queda como desconocido.
    """
    from types import SimpleNamespace
    st = SimpleNamespace(
        publicacion=config.get("publicacion", ""), periodo=config.get("periodo", ""),
        perfil_corpus=config.get("perfil_corpus") or {}, corpus_meta=None,
        ner_motor=ner_motor, config_exportacion=config.get("exportacion") or {})
    return metadatos_proyecto(st, nombre_proyecto)


def declaracion_editorial(herramientas: dict) -> str:
    """Frase para ``editorialDecl``: solo lo que consta que se hizo."""
    ocr = ", ".join(herramientas.get("ocr") or []) or DESCONOCIDO
    ner = herramientas.get("ner") or DESCONOCIDO
    frase = (f"Texto obtenido con Bashkar Station (método de extracción: {ocr}). "
             f"Entidades nombradas identificadas automáticamente (motor: {ner}).")
    ia = herramientas.get("ia") or []
    if ia:
        frase += f" Se usó IA de: {', '.join(ia)}."
    else:
        frase += " No consta uso de servicios de IA en la nube."
    return frase
