"""Sentimiento discriminante — polaridad pos/neg/neutro más fina que el léxico
de 8 emociones (NRC) de ``sentiment_engine``.

PROBLEMA QUE RESUELVE (documentado en la auditoría del corpus Estampa): el
análisis de 8 emociones sesga casi todo a "confianza" porque palabras como
*paz, orden, nación, patria* disparan esa emoción en el léxico NRC. Para el paper
interesa también la POLARIDAD del artículo hacia su tema (positiva/negativa/
neutra) y su intensidad, no solo una etiqueta de emoción dominante.

Combina:
  - léxico de polaridad en español (positivo/negativo) con vocabulario de prensa
    de los años 30,
  - negaciones ("no", "sin", "nunca") que invierten la polaridad local,
  - normalización por longitud (densidad emocional),
y deja ``sentiment_engine.analizar_emociones`` (8 emociones) como complemento.

Incluye ``polaridad_hacia(texto, formas_entidad)`` para medir cómo trata el
artículo a una entidad concreta (p. ej. Franco, López, España) — clave para el
análisis de actores. Y ``indice_polarizacion_afectiva`` para medir cuán dividida
está la cobertura de un actor en el corpus.

100% local. El modo transformer (pysentimiento) es opcional y queda inerte en
Python 3.14 (incompatibilidad binaria de torch); solo se activa en entornos 3.12.
Funciones puras texto→dict, en línea con los demás motores de ``core/``.
"""

from __future__ import annotations

import re

_POS = {
    "logro", "logros", "avance", "avances", "mejora", "mejoras", "éxito", "exito",
    "exitoso", "triunfo", "triunfos", "victoria", "gloria", "glorioso", "brillante",
    "esplendor", "esplendoroso", "progreso", "prosperidad", "grandeza", "noble",
    "nobleza", "ilustre", "egregio", "admirable", "magnífic", "magnifico",
    "hermoso", "bello", "belleza", "elegante", "elegancia", "distinguid",
    "homenaje", "elogio", "celebra", "celebración", "aplauso", "honor", "honra",
    "digno", "digna", "dignos", "dignas", "dignidad", "esperanza", "armonía",
    "armonia", "paz", "fe", "entusiasmo", "alegría", "alegria", "festejo",
    "felicidad", "virtud", "talento", "genio", "sabio", "sabia", "sabiduría",
    "sabiduria", "heroico", "heroica", "heroicos", "heroicas", "heroísmo",
    "heroismo", "valiente", "valientes", "valor", "fortuna", "favorable",
    "magnifica", "magnificos", "magnificas", "distinguida", "distinguidos",
    "distinguidas",
}
_NEG = {
    "crisis", "escándalo", "escandalo", "tragedia", "trágic", "tragic",
    "trágico", "tragico", "trágica", "tragica", "trágicos", "tragicos",
    "trágicas", "tragicas", "drama",
    "dolor", "sufrimiento", "miseria", "pobreza", "ruina", "desgracia", "luto",
    "muerte", "muert", "muerto", "muerta", "muertos", "muertas", "sangre",
    "sangrient", "sangriento", "sangrienta", "sangrientos", "sangrientas",
    "violencia", "violent", "violento", "violenta", "violentos", "violentas",
    "guerra",
    "conflicto", "destrucción", "destruccion", "ataque", "ataques", "amenaza",
    "amenazas", "peligro", "miedo", "temor", "terror", "horror", "espanto",
    "fracaso", "derrota", "caída", "caida", "decadencia", "vergüenza",
    "verguenza", "deshonra", "infamia", "traición", "traicion", "crimen",
    "criminal", "delito", "asesinato", "robo", "corrupción", "corrupcion",
    "corrupto", "corrupta", "mentira", "engaño", "engano", "falso", "falsa",
    "fraude", "injusticia",
    "tiranía", "tirania", "opresión", "opresion", "barbarie", "salvaje",
    "cruel", "crueldad", "odio", "rencor", "rencoroso", "rencorosa",
    "enemigo", "enemigos", "ruin", "vil", "mezquino",
    "lamentable", "deplorable", "grave", "funesto", "siniestro", "fatal",
}
_NEGADORES = {"no", "ni", "sin", "nunca", "jamás", "jamas", "tampoco", "nada"}


# ── Modelo transformer opcional (más preciso que el léxico) ─────────────────
# Carga perezosa: solo si el usuario activa "usar transformer" y el entorno lo
# soporta. Inerte en Python 3.14 (torch segfaultea por incompat. binaria).
_MODELO_HF = "pysentimiento/robertuito-sentiment-analysis"
_pipe_cache: dict = {}


def transformer_disponible() -> bool:
    """True solo si transformers+torch están y son estables (no Python 3.14)."""
    import sys
    if sys.version_info[:2] >= (3, 14):
        return False
    try:
        import transformers  # noqa: F401
        return True
    except Exception:
        return False


def _cargar_transformer():
    if "pipe" in _pipe_cache:
        return _pipe_cache["pipe"]
    if not transformer_disponible():
        _pipe_cache["pipe"] = None
        return None
    try:
        from transformers import pipeline
        pipe = pipeline("sentiment-analysis", model=_MODELO_HF,
                        tokenizer=_MODELO_HF, truncation=True, max_length=512)
        _pipe_cache["pipe"] = pipe
        return pipe
    except Exception:
        _pipe_cache["pipe"] = None
        return None


def analizar_polaridad_transformer(texto: str) -> dict | None:
    """Polaridad con modelo transformer en español. None si no está disponible."""
    if not texto or not texto.strip():
        return {"polaridad": "neutro", "score": 0.0, "fuente": "transformer"}
    pipe = _cargar_transformer()
    if pipe is None:
        return None
    try:
        r = pipe(texto[:1500])[0]
        etq = r["label"].upper()
        mapa = {"POS": "positivo", "NEG": "negativo", "NEU": "neutro"}
        pol = mapa.get(etq, "neutro")
        signo = {"positivo": 1, "negativo": -1, "neutro": 0}[pol]
        return {"polaridad": pol, "score": round(signo * float(r["score"]), 3),
                "fuente": "transformer"}
    except Exception:
        return None


def analizar_polaridad(texto: str, usar_transformer: bool = False) -> dict:
    """Polaridad: positivo / negativo / neutro + score ∈ [-1, 1].

    Por defecto usa el léxico (rápido, local). Si ``usar_transformer=True`` y el
    modelo está disponible, usa el transformer y cae al léxico si falla.
    """
    if usar_transformer:
        r = analizar_polaridad_transformer(texto)
        if r is not None:
            return r
    return _analizar_polaridad_lexico(texto)


def _analizar_polaridad_lexico(texto: str) -> dict:
    if not texto or not texto.strip():
        return {"polaridad": "neutro", "score": 0.0, "n_pos": 0, "n_neg": 0,
                "intensidad": 0.0}

    palabras = re.findall(r"\b[a-záéíóúüñ]+\b", texto.lower())
    n_pos = n_neg = 0
    for i, p in enumerate(palabras):
        es_pos = p in _POS
        es_neg = p in _NEG
        if not (es_pos or es_neg):
            continue
        # ¿negación en las 3 palabras previas? invierte
        ventana = palabras[max(0, i - 3):i]
        if any(w in _NEGADORES for w in ventana):
            es_pos, es_neg = es_neg, es_pos
        if es_pos:
            n_pos += 1
        if es_neg:
            n_neg += 1

    total = n_pos + n_neg
    n_palabras = max(1, len(palabras))
    if total == 0:
        return {"polaridad": "neutro", "score": 0.0, "n_pos": 0, "n_neg": 0,
                "intensidad": 0.0}

    score = round((n_pos - n_neg) / total, 3)
    intensidad = round(total / n_palabras * 100, 2)   # densidad emocional %
    # Clasificación: si todos los términos polares son de un solo signo, la
    # polaridad es clara aunque el score esté cerca de 0 por dilución (textos
    # largos con pocas marcas). Solo es neutro cuando hay marcas de AMBOS signos
    # razonablemente balanceadas (|score| ≤ 0.15).
    if n_neg == 0 and n_pos > 0:
        pol = "positivo"
    elif n_pos == 0 and n_neg > 0:
        pol = "negativo"
    elif score > 0.15:
        pol = "positivo"
    elif score < -0.15:
        pol = "negativo"
    else:
        pol = "neutro"
    return {"polaridad": pol, "score": score, "n_pos": n_pos, "n_neg": n_neg,
            "intensidad": intensidad}


def polaridad_hacia(texto: str, entidad_formas: list[str], ventana: int = 25) -> dict:
    """Polaridad del texto SOLO en el entorno de una entidad (X respecto a Y).

    Mide cómo se habla de una entidad concreta: toma ventanas de ±N palabras
    alrededor de cada mención de la entidad y calcula la polaridad ahí. Clave
    para "¿con qué tono trata la revista a Franco / a López / a España?".
    """
    if not texto:
        return {"polaridad": "neutro", "score": 0.0, "n_menciones": 0}
    palabras = re.findall(r"\b[\wáéíóúüñ]+\b", texto.lower())
    formas = [f.lower() for f in (entidad_formas or [])]
    # claves: última palabra significativa de cada forma (apellido/término clave)
    claves = set()
    for f in formas:
        toks = [t for t in f.split() if len(t) > 3]
        claves.add(toks[-1] if toks else f)
    fragmentos = []
    for i, p in enumerate(palabras):
        if p in claves:
            ini = max(0, i - ventana)
            fin = min(len(palabras), i + ventana)
            fragmentos.append(" ".join(palabras[ini:fin]))
    if not fragmentos:
        return {"polaridad": "neutro", "score": 0.0, "n_menciones": 0}
    r = analizar_polaridad(" ".join(fragmentos))
    r["n_menciones"] = len(fragmentos)
    return r


def polaridad_hacia_corpus(textos, entidad_formas: list[str],
                           ventana: int = 25) -> dict:
    """Polaridad hacia una entidad agregada sobre un corpus (lista de textos).

    A diferencia de unir todo el corpus en un solo string, procesa cada artículo
    por separado para que la ventana de contexto NUNCA cruce de un artículo al
    siguiente (evita contaminar la polaridad hacia la entidad con el tono de la
    nota vecina). Agrega las marcas pos/neg de todas las ventanas y clasifica.
    """
    n_pos = n_neg = n_menciones = 0
    n_docs = 0
    for t in textos or []:
        if not t:
            continue
        r = polaridad_hacia(t, entidad_formas, ventana=ventana)
        m = r.get("n_menciones", 0)
        if m:
            n_pos += r.get("n_pos", 0)
            n_neg += r.get("n_neg", 0)
            n_menciones += m
            n_docs += 1
    if n_menciones == 0:
        return {"polaridad": "neutro", "score": 0.0, "n_pos": 0, "n_neg": 0,
                "n_menciones": 0, "n_documentos": 0}
    total = n_pos + n_neg
    score = round((n_pos - n_neg) / total, 3) if total else 0.0
    if n_neg == 0 and n_pos > 0:
        pol = "positivo"
    elif n_pos == 0 and n_neg > 0:
        pol = "negativo"
    elif score > 0.15:
        pol = "positivo"
    elif score < -0.15:
        pol = "negativo"
    else:
        pol = "neutro"
    return {"polaridad": pol, "score": score, "n_pos": n_pos, "n_neg": n_neg,
            "n_menciones": n_menciones, "n_documentos": n_docs}


def indice_polarizacion_afectiva(distrib_polaridad: dict) -> float:
    """Índice de polarización afectiva de la cobertura de un actor (0–1).

    Alto cuando la cobertura se reparte en EXTREMOS (mucho positivo Y mucho
    negativo) en vez de concentrarse o ser neutra. 0 = sin polarización (todo
    neutro o un solo signo); 1 = máxima división pos/neg. Útil para detectar
    actores tratados de forma ambivalente por la revista o entre números.
    """
    pos = distrib_polaridad.get("positivo", 0)
    neg = distrib_polaridad.get("negativo", 0)
    neu = distrib_polaridad.get("neutro", 0)
    total = pos + neg + neu
    if total == 0 or (pos + neg) == 0:
        return 0.0
    no_neutro = (pos + neg) / total
    balance = 1 - abs(pos - neg) / (pos + neg)
    return round(no_neutro * balance, 3)


def distribucion_polaridad(textos) -> dict:
    """Cuenta polaridades sobre un iterable de textos → {positivo, negativo, neutro}.

    Atajo para alimentar ``indice_polarizacion_afectiva`` desde un conjunto de
    artículos (p. ej. todos los que mencionan a una entidad).
    """
    dist = {"positivo": 0, "negativo": 0, "neutro": 0}
    for t in textos or []:
        pol = analizar_polaridad(t).get("polaridad", "neutro")
        dist[pol] = dist.get(pol, 0) + 1
    return dist
