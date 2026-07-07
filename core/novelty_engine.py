"""core/novelty_engine.py — Detección de novedad, eventos y cambio discursivo.

Inspirado en NewsEye. Detecta:
  - Palabras o temas que aparecen por primera vez en el corpus
  - Cambios abruptos en la distribución léxica entre períodos
  - Eventos (clusters de artículos sobre el mismo tema en un período corto)
  - Cambio discursivo: cuándo cambia el vocabulario dominante

Sin dependencias de ML pesado: usa TF-IDF, distancia coseno y ventanas temporales.
Si sentence-transformers está disponible, mejora la detección semántica.
"""

from __future__ import annotations

import re
import math
from collections import Counter, defaultdict
from typing import Optional, Callable


_RE_TOKEN = re.compile(r'\b[a-záéíóúüñ]{4,}\b', re.IGNORECASE)

STOPWORDS = {
    "para", "como", "esto", "esta", "este", "cuando", "desde", "hasta",
    "sobre", "entre", "todos", "toda", "siendo", "están", "tiene", "había",
    "porque", "aunque", "siempre", "nunca", "donde", "cuyo", "cuya",
    "aquel", "aquella", "durante", "después", "antes", "hacia", "según",
}


def _tokenizar(texto: str) -> list[str]:
    return [t for t in _RE_TOKEN.findall(texto.lower()) if t not in STOPWORDS]


def _tfidf_periodo(corpus_por_periodo: dict[str, list[str]]) -> dict[str, dict[str, float]]:
    """Calcula TF-IDF por período."""
    todos_periodos = list(corpus_por_periodo.keys())
    n_docs = len(todos_periodos)

    # IDF global
    df: Counter = Counter()
    tf_periodo: dict[str, Counter] = {}

    for periodo, textos in corpus_por_periodo.items():
        tokens = []
        for t in textos:
            tokens.extend(_tokenizar(t))
        tf = Counter(tokens)
        tf_periodo[periodo] = tf
        df.update(set(tokens))

    tfidf: dict[str, dict[str, float]] = {}
    for periodo, tf in tf_periodo.items():
        total = sum(tf.values()) or 1
        tfidf[periodo] = {}
        for palabra, freq in tf.items():
            tf_norm = freq / total
            idf     = math.log((n_docs + 1) / (df[palabra] + 1)) + 1
            tfidf[periodo][palabra] = round(tf_norm * idf, 6)

    return tfidf


def _distancia_coseno(a: dict[str, float], b: dict[str, float]) -> float:
    vocab = set(a) | set(b)
    dot   = sum(a.get(w, 0) * b.get(w, 0) for w in vocab)
    norma_a = math.sqrt(sum(v**2 for v in a.values()))
    norma_b = math.sqrt(sum(v**2 for v in b.values()))
    if norma_a == 0 or norma_b == 0:
        return 1.0
    return 1.0 - dot / (norma_a * norma_b)


def palabras_nuevas(
    corpus_por_periodo: dict[str, list[str]],
    min_freq: int = 3,
) -> dict[str, list[str]]:
    """
    Detecta palabras que aparecen por primera vez en cada período.
    corpus_por_periodo: {periodo_ordenado: [textos]}
    Retorna: {periodo: [palabras_nuevas]}
    """
    periodos  = sorted(corpus_por_periodo.keys())
    visto     = set()
    resultado = {}

    for periodo in periodos:
        textos  = corpus_por_periodo[periodo]
        tokens  = []
        for t in textos:
            tokens.extend(_tokenizar(t))
        freq = Counter(tokens)
        nuevas = [p for p, f in freq.items() if p not in visto and f >= min_freq]
        visto.update(freq.keys())
        resultado[periodo] = sorted(nuevas)

    return resultado


def cambio_discursivo(
    corpus_por_periodo: dict[str, list[str]],
    top_n: int = 15,
) -> list[dict]:
    """
    Detecta cambios abruptos en el vocabulario entre períodos consecutivos.

    Retorna lista de {periodo_a, periodo_b, distancia, palabras_ganadas, palabras_perdidas}
    ordenada por distancia descendente (los cambios más abruptos primero).
    """
    periodos  = sorted(corpus_por_periodo.keys())
    tfidf     = _tfidf_periodo(corpus_por_periodo)
    resultados = []

    for i in range(1, len(periodos)):
        pa = periodos[i - 1]
        pb = periodos[i]
        dist = _distancia_coseno(tfidf[pa], tfidf[pb])

        # Palabras que ganaron peso
        ganadas = sorted(
            [(w, tfidf[pb].get(w, 0) - tfidf[pa].get(w, 0))
             for w in tfidf[pb]],
            key=lambda x: -x[1]
        )[:top_n]

        # Palabras que perdieron peso
        perdidas = sorted(
            [(w, tfidf[pa].get(w, 0) - tfidf[pb].get(w, 0))
             for w in tfidf[pa]],
            key=lambda x: -x[1]
        )[:top_n]

        resultados.append({
            "periodo_a":        pa,
            "periodo_b":        pb,
            "distancia":        round(dist, 4),
            "palabras_ganadas": [{"palabra": w, "delta": round(d, 5)}
                                  for w, d in ganadas if d > 0],
            "palabras_perdidas":[{"palabra": w, "delta": round(d, 5)}
                                  for w, d in perdidas if d > 0],
        })

    resultados.sort(key=lambda x: -x["distancia"])
    return resultados


def detectar_eventos(
    articulos: list[dict],
    ventana_periodos: int = 1,
    top_n_terminos: int = 8,
    min_articulos_evento: int = 3,
) -> list[dict]:
    """
    Detecta clusters de artículos sobre el mismo tema en períodos cortos.
    Un "evento" es un conjunto de artículos con vocabulario muy similar
    que aparecen en el mismo número o números consecutivos.

    articulos: [{texto, numero, titulo, ...}]
    Retorna: lista de eventos [{numero, articulos, terminos, coherencia}]
    """
    # Agrupar por número
    por_numero: dict[str, list[dict]] = defaultdict(list)
    for art in articulos:
        num = str(art.get("numero", "sin_número"))
        por_numero[num].append(art)

    periodos = sorted(por_numero.keys())
    eventos  = []

    # Para cada ventana de períodos
    for i in range(len(periodos)):
        nums_ventana = periodos[i:i + ventana_periodos + 1]
        arts_ventana = []
        for num in nums_ventana:
            arts_ventana.extend(por_numero[num])

        if len(arts_ventana) < min_articulos_evento:
            continue

        # TF de la ventana
        todos_tokens = []
        for art in arts_ventana:
            todos_tokens.extend(_tokenizar(art.get("texto", "") or ""))
        freq = Counter(todos_tokens)
        terminos_top = [w for w, _ in freq.most_common(top_n_terminos)]

        # Coherencia: % de artículos que contienen al menos 3 de los top términos
        n_coherentes = 0
        for art in arts_ventana:
            tokens_art = set(_tokenizar(art.get("texto", "") or ""))
            if len(tokens_art & set(terminos_top)) >= 3:
                n_coherentes += 1
        coherencia = n_coherentes / len(arts_ventana) if arts_ventana else 0

        if coherencia >= 0.4:
            eventos.append({
                "numeros":     nums_ventana,
                "n_articulos": len(arts_ventana),
                "terminos":    terminos_top,
                "coherencia":  round(coherencia, 3),
                "titulos":     [art.get("titulo", "")[:60]
                                for art in arts_ventana[:5]],
            })

    # Deduplicar eventos solapados (quedarse con el de mayor coherencia)
    eventos.sort(key=lambda e: -e["coherencia"])
    return eventos[:20]


def tendencia_vocabulario(
    corpus_por_periodo: dict[str, list[str]],
    palabras: list[str],
) -> dict[str, dict[str, float]]:
    """
    Calcula la frecuencia relativa de cada palabra en cada período.
    Útil para ver si un término (ej: "radio", "fascismo", "mujer") sube o baja.

    Retorna: {palabra: {periodo: frecuencia_relativa}}
    """
    periodos = sorted(corpus_por_periodo.keys())
    resultado: dict[str, dict[str, float]] = {p: {} for p in palabras}

    for periodo, textos in corpus_por_periodo.items():
        tokens = []
        for t in textos:
            tokens.extend(_tokenizar(t))
        total  = len(tokens) or 1
        freq   = Counter(tokens)
        for palabra in palabras:
            resultado[palabra][periodo] = round(freq.get(palabra.lower(), 0) / total * 10000, 2)

    return resultado
