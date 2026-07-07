"""core/explainer.py — Relevancia explicable en búsqueda semántica (estilo NewsEye).

Dado un resultado de búsqueda (artículo, entidad, página), explica POR QUÉ
fue considerado relevante: qué términos contribuyeron, qué entidades coinciden,
qué tan similar es semánticamente, y de qué sección/número proviene.

No requiere IA externa: la explicación se construye a partir de las señales
ya disponibles en el índice (FAISS, NER, TF-IDF).
"""

from __future__ import annotations

import math
import re
from collections import Counter

_RE_TOKEN = re.compile(r'\b[a-záéíóúüñ]{4,}\b', re.IGNORECASE)


def _tokenizar(texto: str) -> list[str]:
    return _RE_TOKEN.findall(texto.lower())


def _tfidf_local(query_tokens: list[str], doc_tokens: list[str],
                 corpus_freq: Counter | None = None,
                 n_docs: int = 100) -> dict[str, float]:
    """TF-IDF del query sobre el documento. corpus_freq para IDF global."""
    doc_freq   = Counter(doc_tokens)
    total_doc  = len(doc_tokens) or 1
    scores     = {}
    for tok in set(query_tokens):
        tf  = doc_freq.get(tok, 0) / total_doc
        idf = math.log((n_docs + 1) / ((corpus_freq.get(tok, 0) if corpus_freq else 1) + 1)) + 1
        scores[tok] = round(tf * idf, 5)
    return scores


def explicar_resultado(
    query: str,
    resultado: dict,
    indice_ner: dict | None = None,
    corpus_freq: Counter | None = None,
    n_docs: int = 100,
) -> dict:
    """
    Explica por qué un artículo/página fue devuelto como resultado relevante.

    query:       texto de la búsqueda
    resultado:   dict con al menos {texto, titulo, similitud, numero, seccion, ...}
    indice_ner:  {categoria: {entidad: [art_ids]}} para cruzar entidades
    corpus_freq: Counter global de términos para IDF

    Retorna dict con:
      similitud_semantica, terminos_relevantes, entidades_compartidas,
      procedencia, resumen_explicacion
    """
    texto_doc   = resultado.get("texto", "") or ""
    similitud   = resultado.get("similitud", 0.0)
    titulo      = resultado.get("titulo", "")
    numero      = resultado.get("numero", "")
    seccion     = resultado.get("seccion", "")
    art_id      = resultado.get("art_id", resultado.get("id", ""))

    query_tokens = _tokenizar(query)
    doc_tokens   = _tokenizar(texto_doc)

    # Términos del query que aparecen en el documento
    doc_set  = set(doc_tokens)
    presentes = [t for t in set(query_tokens) if t in doc_set]

    # TF-IDF para rankear cuáles contribuyeron más
    scores = _tfidf_local(query_tokens, doc_tokens, corpus_freq, n_docs)
    terminos_relevantes = sorted(
        [{"termino": t, "score": scores.get(t, 0), "freq": doc_tokens.count(t)}
         for t in presentes],
        key=lambda x: -x["score"]
    )[:10]

    # Entidades compartidas (si el query menciona entidades conocidas)
    entidades_compartidas = []
    if indice_ner and art_id:
        for cat, ents in indice_ner.items():
            for ent, art_ids in ents.items():
                if art_id in art_ids and ent.lower() in query.lower():
                    entidades_compartidas.append({"entidad": ent, "categoria": cat})

    # Fragmento más relevante del texto (primera oración con el mayor número de hits)
    oraciones = re.split(r'[.!?]', texto_doc)
    mejor_oracion = ""
    mejor_hits    = 0
    for oracion in oraciones:
        hits = sum(1 for t in query_tokens if t in oracion.lower())
        if hits > mejor_hits:
            mejor_hits    = hits
            mejor_oracion = oracion.strip()

    # Resumen narrativo de la explicación
    partes = []
    if similitud >= 0.8:
        partes.append(f"Alta similitud semántica ({similitud:.2f})")
    elif similitud >= 0.5:
        partes.append(f"Similitud moderada ({similitud:.2f})")
    else:
        partes.append(f"Baja similitud semántica ({similitud:.2f})")

    if terminos_relevantes:
        tops = ", ".join(t["termino"] for t in terminos_relevantes[:4])
        partes.append(f"términos en común: {tops}")

    if entidades_compartidas:
        ents = ", ".join(e["entidad"] for e in entidades_compartidas[:3])
        partes.append(f"entidades compartidas: {ents}")

    if numero:
        partes.append(f"proviene del número {numero}")
    if seccion:
        partes.append(f"sección: {seccion}")

    resumen = ". ".join(p.capitalize() for p in partes) + "."

    return {
        "similitud_semantica":   round(similitud, 4),
        "terminos_relevantes":   terminos_relevantes,
        "entidades_compartidas": entidades_compartidas,
        "fragmento_relevante":   mejor_oracion[:200],
        "procedencia": {
            "titulo":  titulo,
            "numero":  numero,
            "seccion": seccion,
            "art_id":  art_id,
        },
        "resumen_explicacion": resumen,
    }


def explicar_lote(
    query: str,
    resultados: list[dict],
    indice_ner: dict | None = None,
    corpus_freq: Counter | None = None,
    n_docs: int = 100,
) -> list[dict]:
    """
    Explica todos los resultados de una búsqueda.
    Agrega el campo 'explicacion' a cada resultado.
    """
    explicados = []
    for res in resultados:
        exp = explicar_resultado(query, res, indice_ner, corpus_freq, n_docs)
        resultado_enriquecido = dict(res)
        resultado_enriquecido["explicacion"] = exp
        explicados.append(resultado_enriquecido)
    return explicados


def construir_corpus_freq(textos: list[str]) -> Counter:
    """Construye frecuencia global de términos para usar en IDF."""
    freq: Counter = Counter()
    for texto in textos:
        freq.update(set(_tokenizar(texto)))
    return freq


def resumir_busqueda(
    query: str,
    resultados_explicados: list[dict],
    top_n: int = 5,
) -> str:
    """
    Genera un párrafo de síntesis sobre los resultados de búsqueda.
    Sin IA — basado en señales estadísticas de los resultados.
    """
    if not resultados_explicados:
        return f"No se encontraron resultados relevantes para: '{query}'."

    n = len(resultados_explicados)
    sim_media = sum(
        r.get("explicacion", {}).get("similitud_semantica", 0)
        for r in resultados_explicados
    ) / n

    # Términos más frecuentes en los resultados
    todos_terminos: Counter = Counter()
    for r in resultados_explicados:
        for t in r.get("explicacion", {}).get("terminos_relevantes", []):
            todos_terminos[t["termino"]] += 1
    top_terminos = [w for w, _ in todos_terminos.most_common(5)]

    # Números representados
    numeros = list(dict.fromkeys(
        r.get("explicacion", {}).get("procedencia", {}).get("numero", "")
        for r in resultados_explicados if r.get("explicacion", {}).get("procedencia", {}).get("numero")
    ))[:4]

    partes = [f"La búsqueda '{query}' retornó {n} resultado(s)"]
    if sim_media >= 0.6:
        partes.append(f"con alta relevancia semántica (similitud media: {sim_media:.2f})")
    elif sim_media >= 0.35:
        partes.append(f"con relevancia moderada (similitud media: {sim_media:.2f})")
    else:
        partes.append(f"con baja similitud semántica (media: {sim_media:.2f})")

    if top_terminos:
        partes.append(f"Los términos más presentes son: {', '.join(top_terminos)}")

    if numeros:
        partes.append(f"Los resultados provienen principalmente de los números: {', '.join(numeros)}")

    return ". ".join(partes) + "."
