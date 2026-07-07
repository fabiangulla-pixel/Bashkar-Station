"""core/sintaxis_engine.py — Lingüística computacional: parsing y relaciones.

Funciones:
  analizar_dependencias()     — árbol de dependencias spaCy (quién hace qué a quién)
  concordancias_sintaticas()  — KWIC sintáctico: patrones VERBO+sujeto, SUST+adj, etc.
  extraer_relaciones()        — tripletas sujeto-relación-objeto
  resumir_arbol_dep()         — resumen legible del árbol para la UI
"""

from __future__ import annotations

from collections import defaultdict
from typing import Callable

# ── Helpers ──────────────────────────────────────────────────────────────────

def _cargar_nlp():
    """Carga es_core_news_sm (o sm disponible). Lanza ImportError si no hay."""
    try:
        import spacy
        try:
            return spacy.load("es_core_news_sm")
        except OSError:
            try:
                return spacy.load("es_core_news_md")
            except OSError:
                raise ImportError(
                    "Modelo spaCy no encontrado. "
                    "Ejecuta: python -m spacy download es_core_news_sm"
                )
    except ImportError:
        raise ImportError("Instala spaCy: pip install spacy>=3.7")


# ── Etiquetas de dependencia de spaCy en español ────────────────────────────
# nsubj  = sujeto nominal
# obj    = objeto directo
# iobj   = objeto indirecto
# nmod   = modificador nominal
# amod   = modificador adjetival
# advmod = modificador adverbial
# ROOT   = raíz del árbol (generalmente el verbo principal)

_DEP_ES = {
    "nsubj":   "sujeto",
    "obj":     "objeto_directo",
    "iobj":    "objeto_indirecto",
    "nmod":    "mod_nominal",
    "amod":    "mod_adjetival",
    "advmod":  "mod_adverbial",
    "ROOT":    "raiz",
    "aux":     "auxiliar",
    "cop":     "copula",
    "conj":    "conjunto",
    "cc":      "coordinante",
    "det":     "determinante",
    "prep":    "preposicion",
    "pobj":    "obj_preposicional",
}


# ── 1. Análisis de dependencias ───────────────────────────────────────────────

def analizar_dependencias(
    texto: str,
    nlp=None,
    max_oraciones: int = 20,
) -> list[dict]:
    """
    Analiza las dependencias sintácticas de un texto.

    Retorna lista de oraciones; cada oración contiene:
      {
        "oracion": str,
        "tokens": [{"texto", "lemma", "pos", "dep", "dep_es", "cabeza", "hijos"}],
        "sujeto": str | None,
        "verbo": str | None,
        "objeto": str | None,
      }
    """
    if nlp is None:
        nlp = _cargar_nlp()

    if not texto or not texto.strip():
        return []

    doc = nlp(texto[:30000])
    resultados = []

    for sent in list(doc.sents)[:max_oraciones]:
        tokens_info = []
        sujeto = verbo = objeto = None

        for tok in sent:
            dep_es = _DEP_ES.get(tok.dep_, tok.dep_)
            hijos = [
                {"texto": c.text, "dep": c.dep_, "dep_es": _DEP_ES.get(c.dep_, c.dep_)}
                for c in tok.children
            ]
            tokens_info.append({
                "texto":  tok.text,
                "lemma":  tok.lemma_,
                "pos":    tok.pos_,
                "dep":    tok.dep_,
                "dep_es": dep_es,
                "cabeza": tok.head.text,
                "hijos":  hijos,
            })

            if tok.dep_ == "ROOT" and tok.pos_ in ("VERB", "AUX"):
                verbo = tok.lemma_
            elif tok.dep_ == "nsubj":
                sujeto = tok.text
            elif tok.dep_ in ("obj", "dobj"):
                objeto = tok.text

        resultados.append({
            "oracion": sent.text.strip(),
            "tokens":  tokens_info,
            "sujeto":  sujeto,
            "verbo":   verbo,
            "objeto":  objeto,
        })

    return resultados


def resumir_arbol_dep(oracion_info: dict) -> str:
    """
    Convierte el análisis de una oración en texto legible para la UI.
    Ej: '[sujeto: Franco] [verbo: visitar] [objeto: Bogotá]'
    """
    partes = []
    if oracion_info.get("sujeto"):
        partes.append(f"[sujeto: {oracion_info['sujeto']}]")
    if oracion_info.get("verbo"):
        partes.append(f"[verbo: {oracion_info['verbo']}]")
    if oracion_info.get("objeto"):
        partes.append(f"[objeto: {oracion_info['objeto']}]")
    if not partes:
        return oracion_info.get("oracion", "")[:80]
    return " ".join(partes)


# ── 2. Concordancias sintácticas ─────────────────────────────────────────────

# Patrones disponibles para la UI:
PATRONES_SINTACTICOS = {
    "verbo_sujeto":    "Verbos y sus sujetos (quién hace la acción)",
    "verbo_objeto":    "Verbos y sus objetos (qué/quién recibe la acción)",
    "sustantivo_adj":  "Sustantivos con adjetivos (cómo se describe)",
    "entidad_verbo":   "Entidades nombradas como sujeto de verbos",
    "negacion":        "Oraciones con negación",
    "pregunta":        "Oraciones interrogativas",
}


def concordancias_sintaticas(
    corpus: list[str],
    patron: str = "verbo_sujeto",
    nlp=None,
    max_resultados: int = 100,
    callback: Callable[[int, int], None] | None = None,
) -> list[dict]:
    """
    Extrae concordancias sintácticas según un patrón predefinido.

    patron: clave de PATRONES_SINTACTICOS
    corpus: lista de textos

    Retorna lista de {patron, texto_completo, match_principal,
                      match_secundario, doc_idx, posicion}
    """
    if nlp is None:
        nlp = _cargar_nlp()

    resultados = []
    total = len(corpus)

    for doc_idx, texto in enumerate(corpus):
        if callback:
            callback(doc_idx + 1, total)
        if not texto or not texto.strip():
            continue

        doc = nlp(texto[:20000])

        for sent in doc.sents:
            if len(resultados) >= max_resultados:
                return resultados

            if patron == "verbo_sujeto":
                for tok in sent:
                    if tok.dep_ == "nsubj" and tok.head.pos_ in ("VERB", "AUX"):
                        resultados.append({
                            "patron": patron,
                            "texto_completo": sent.text.strip(),
                            "match_principal": tok.head.lemma_,
                            "match_secundario": tok.text,
                            "descripcion": f"{tok.head.lemma_} ← sujeto: {tok.text}",
                            "doc_idx": doc_idx,
                        })

            elif patron == "verbo_objeto":
                for tok in sent:
                    if tok.dep_ in ("obj", "dobj") and tok.head.pos_ in ("VERB", "AUX"):
                        resultados.append({
                            "patron": patron,
                            "texto_completo": sent.text.strip(),
                            "match_principal": tok.head.lemma_,
                            "match_secundario": tok.text,
                            "descripcion": f"{tok.head.lemma_} → objeto: {tok.text}",
                            "doc_idx": doc_idx,
                        })

            elif patron == "sustantivo_adj":
                for tok in sent:
                    if tok.dep_ == "amod" and tok.head.pos_ == "NOUN":
                        resultados.append({
                            "patron": patron,
                            "texto_completo": sent.text.strip(),
                            "match_principal": tok.head.text,
                            "match_secundario": tok.text,
                            "descripcion": f"{tok.head.text} + adj: {tok.text}",
                            "doc_idx": doc_idx,
                        })

            elif patron == "entidad_verbo":
                ents_sujeto = {tok.i for tok in sent
                               if tok.dep_ == "nsubj" and tok.ent_type_}
                for tok in sent:
                    if tok.i in ents_sujeto:
                        resultados.append({
                            "patron": patron,
                            "texto_completo": sent.text.strip(),
                            "match_principal": tok.text,
                            "match_secundario": tok.head.lemma_,
                            "descripcion": f"entidad '{tok.text}' ({tok.ent_type_}) → {tok.head.lemma_}",
                            "doc_idx": doc_idx,
                        })

            elif patron == "negacion":
                tiene_neg = any(t.dep_ == "neg" for t in sent)
                if tiene_neg:
                    neg_tok = next((t for t in sent if t.dep_ == "neg"), None)
                    resultados.append({
                        "patron": patron,
                        "texto_completo": sent.text.strip(),
                        "match_principal": neg_tok.head.lemma_ if neg_tok else "",
                        "match_secundario": neg_tok.text if neg_tok else "no",
                        "descripcion": f"negación: '{neg_tok.text} {neg_tok.head.text}'",
                        "doc_idx": doc_idx,
                    })

            elif patron == "pregunta":
                if sent.text.strip().endswith("?") or sent.text.strip().startswith("¿"):
                    resultados.append({
                        "patron": patron,
                        "texto_completo": sent.text.strip(),
                        "match_principal": "",
                        "match_secundario": "",
                        "descripcion": "oración interrogativa",
                        "doc_idx": doc_idx,
                    })

    return resultados


# ── 3. Extracción de relaciones ───────────────────────────────────────────────

def extraer_relaciones(
    corpus: list[str],
    nlp=None,
    solo_entidades: bool = True,
    min_confianza: float = 0.5,
    callback: Callable[[int, int], None] | None = None,
) -> list[dict]:
    """
    Extrae tripletas sujeto-relación-objeto del corpus.

    solo_entidades=True: solo sujetos/objetos que sean entidades nombradas.
    min_confianza: umbral basado en heurísticas (0–1).

    Retorna lista de:
      {sujeto, sujeto_tipo, relacion, objeto, objeto_tipo,
       confianza, oracion, doc_idx}
    """
    if nlp is None:
        nlp = _cargar_nlp()

    relaciones = []
    total = len(corpus)

    for doc_idx, texto in enumerate(corpus):
        if callback:
            callback(doc_idx + 1, total)
        if not texto or not texto.strip():
            continue

        doc = nlp(texto[:20000])

        # Mapa token_idx → entidad
        ent_map: dict[int, str] = {}
        ent_tipo_map: dict[int, str] = {}
        for ent in doc.ents:
            for tok in ent:
                ent_map[tok.i] = ent.text
                ent_tipo_map[tok.i] = ent.label_

        for sent in doc.sents:
            # Buscar verbo raíz
            raiz = next((t for t in sent if t.dep_ == "ROOT"), None)
            if raiz is None or raiz.pos_ not in ("VERB", "AUX"):
                continue

            # Sujeto
            sujeto_tok = next(
                (t for t in sent if t.dep_ == "nsubj" and t.head.i == raiz.i), None
            )
            # Objeto
            objeto_tok = next(
                (t for t in sent if t.dep_ in ("obj", "dobj") and t.head.i == raiz.i),
                None,
            )

            if sujeto_tok is None and objeto_tok is None:
                continue

            # Si solo_entidades, al menos uno debe ser entidad
            s_es_ent = sujeto_tok is not None and sujeto_tok.i in ent_map
            o_es_ent = objeto_tok is not None and objeto_tok.i in ent_map

            if solo_entidades and not s_es_ent and not o_es_ent:
                continue

            sujeto    = ent_map.get(sujeto_tok.i, sujeto_tok.text) if sujeto_tok else ""
            suj_tipo  = ent_tipo_map.get(sujeto_tok.i, "") if sujeto_tok else ""
            objeto    = ent_map.get(objeto_tok.i, objeto_tok.text) if objeto_tok else ""
            obj_tipo  = ent_tipo_map.get(objeto_tok.i, "") if objeto_tok else ""
            relacion  = raiz.lemma_

            # Heurística de confianza: más completa la tripleta → mayor confianza
            conf = 0.3
            if sujeto:
                conf += 0.3
            if objeto:
                conf += 0.2
            if s_es_ent or o_es_ent:
                conf += 0.2

            if conf < min_confianza:
                continue

            relaciones.append({
                "sujeto":      sujeto,
                "sujeto_tipo": suj_tipo,
                "relacion":    relacion,
                "objeto":      objeto,
                "objeto_tipo": obj_tipo,
                "confianza":   round(conf, 2),
                "oracion":     sent.text.strip(),
                "doc_idx":     doc_idx,
            })

    return relaciones


def agrupar_relaciones(relaciones: list[dict]) -> dict:
    """
    Agrupa las relaciones por verbo/relación para ver patrones.
    Retorna {relacion: [{sujeto, objeto, confianza, n}]} ordenado por frecuencia.
    """
    por_relacion: dict[str, list] = defaultdict(list)
    for rel in relaciones:
        por_relacion[rel["relacion"]].append(rel)

    # Contar y ordenar
    resultado = {}
    for verbo, items in sorted(por_relacion.items(),
                                key=lambda x: -len(x[1])):
        resultado[verbo] = {
            "n":         len(items),
            "relaciones": items,
        }
    return resultado


def exportar_relaciones_csv(relaciones: list[dict], ruta) -> object:
    """Exporta las relaciones a CSV."""
    import csv
    from pathlib import Path

    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)

    if not relaciones:
        return ruta

    campos = ["sujeto", "sujeto_tipo", "relacion", "objeto", "objeto_tipo",
              "confianza", "oracion", "doc_idx"]

    with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        w.writerows(relaciones)

    return ruta
