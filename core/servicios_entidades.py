"""core/servicios_entidades.py — Operaciones sobre el índice de entidades.

Extraído de ``app.py`` (sesión 71), donde vivía dentro de métodos de la GUI:

- ``fuente_para_validar`` / ``calificar_entidades`` ← ``_valid_calcular``.
  El original calculaba el semáforo de confianza con
  ``llm_conf = conf + 0.05``: una "confianza de LLM" que ningún modelo
  produjo y que pesaba el 45 % del puntaje. Aquí se pasa ``None`` y el
  puntaje se reparte entre las señales que sí existen.
- ``indice_por_numero`` ← ``_red_calcular_evolucion``.
- ``buscar_lexico`` ← ``_bsem_buscar_lexico``. El original buscaba por
  subcadena ("ley" encontraba "leyenda", "arte" encontraba "parte"); aquí
  un término debe coincidir con una palabra completa o con su plural
  ("gobierno" encuentra "gobiernos", "ley" encuentra "leyes").
"""

from __future__ import annotations

import re
from collections.abc import Callable

# Categorías cortas del Repositorio → nombre del índice NER.
CATEGORIAS_REPO = {
    "PER": "personas", "LOC": "lugares", "ORG": "organizaciones",
    "EVE": "eventos_historicos", "OBRA": "obras_publicaciones",
    "CARGO": "personas",
}
# Sin confianza medida (índice en memoria, fila sin el dato) se usa None: la
# señal no cuenta. Antes se rellenaba con 0.75, otro número que nadie midió.
CONFIANZA_SIN_DATO = None


def _conf(valor):
    try:
        return None if valor in (None, "") else float(valor)
    except (TypeError, ValueError):
        return None


def fuente_para_validar(filas_repo=None, indice_ner=None) -> tuple[dict, str]:
    """{categoria: {entidad: {"arts": [...], "confianza": float}}} y su origen.

    Prefiere la base del proyecto (trae la confianza real del NER); si está
    vacía, usa el índice en memoria. El origen es "DB", "memoria" o "".
    """
    fuente: dict = {}
    for fila in filas_repo or []:
        cat = CATEGORIAS_REPO.get(fila.get("categoria", ""), fila.get("categoria") or "otros")
        texto = str(fila.get("texto", "")).strip()
        if not texto:
            continue
        reg = fuente.setdefault(cat, {}).setdefault(
            texto, {"arts": [], "confianza": _conf(fila.get("confianza"))})
        art = fila.get("articulo_id", "?")
        if art not in reg["arts"]:
            reg["arts"].append(art)
    if fuente:
        return fuente, "DB"
    for cat, ents in (indice_ner or {}).items():
        if isinstance(ents, dict):
            fuente[cat] = {e: {"arts": list(a), "confianza": CONFIANZA_SIN_DATO}
                           for e, a in ents.items()}
    return fuente, ("memoria" if fuente else "")


def calificar_entidades(fuente: dict,
                        en_base: Callable[[str, str], bool] | None = None) -> list[dict]:
    """Semáforo de confianza por entidad: [{entidad, categoria, score, nivel}].

    ``en_base(entidad, categoria)`` consulta la base de conocimiento; sin ella,
    esa señal no cuenta (no se supone ni presente ni ausente).
    """
    from core.confianza_engine import nivel_confianza, score_ner_entidad
    salida = []
    for cat, ents in fuente.items():
        for ent, meta in ents.items():
            conf = meta.get("confianza", CONFIANZA_SIN_DATO) if isinstance(meta, dict) \
                else CONFIANZA_SIN_DATO
            sc = score_ner_entidad(
                en_kb=bool(en_base(ent, cat)) if en_base else None,
                verificada=False,
                spacy_conf=conf,
                llm_conf=None,   # no hay validación por LLM: no se inventa
            )
            salida.append({"entidad": ent, "categoria": cat, "score": sc,
                           "nivel": nivel_confianza(sc)})
    return salida


def indice_por_numero(corpus_meta, indice_ner) -> dict:
    """{numero: {categoria: {entidad: [art_ids]}}} para la evolución de la red.

    Espera ``corpus_meta`` como dict {art_id: {...}} (flujo del conversor); un
    DataFrame (flujo de OCR) se trata como no disponible.
    """
    if not isinstance(corpus_meta, dict):
        return {}
    indice_ner = indice_ner or {}
    por_numero: dict = {}
    for art_id, meta in corpus_meta.items():
        numero = (meta.get("numero") or meta.get("pagina", "")[:7]
                  if isinstance(meta, dict) else "sin_numero")
        destino = por_numero.setdefault(numero, {cat: {} for cat in indice_ner})
        for cat, ents in indice_ner.items():
            if not isinstance(ents, dict):
                continue
            for ent, arts in ents.items():
                if art_id in arts:
                    destino[cat].setdefault(ent, []).append(art_id)
    return por_numero


def buscar_lexico(corpus_txt, consulta: str, k: int = 10, corpus_meta=None) -> list[dict]:
    """Búsqueda léxica (sin FAISS): [{rank, articulo_id, similitud, titulo}].

    Un término cuenta si aparece como palabra completa o en plural. Score = fracción de
    términos hallados, ×1,5 (tope 1) si aparecen todos.
    """
    terminos = [t.lower() for t in consulta.split() if len(t) > 2]
    if not terminos:
        return []
    patrones = [re.compile(r"\b" + re.escape(t) + r"(?:e?s)?\b", re.IGNORECASE)
                for t in terminos]
    meta = corpus_meta if isinstance(corpus_meta, dict) else {}
    resultados = []
    for i, texto in enumerate(corpus_txt or []):
        if not texto:
            continue
        hallados = sum(1 for p in patrones if p.search(texto))
        if not hallados:
            continue
        score = hallados / len(patrones)
        if len(patrones) > 1 and hallados == len(patrones):
            score = min(score * 1.5, 1.0)
        m = meta.get(str(i), {})
        resultados.append({"rank": 0, "articulo_id": str(i), "similitud": score,
                           "titulo": m.get("titulo", "") if isinstance(m, dict) else ""})
    resultados.sort(key=lambda r: -r["similitud"])
    for j, r in enumerate(resultados[:k], 1):
        r["rank"] = j
    return resultados[:k]
