"""core/morfologia_historica.py — Análisis morfológico del español histórico (1900-1950).

El español de los años 30 presenta formas que los lematizadores modernos
(spaCy, stanza) normalizan incorrectamente o ignoran. Este módulo:

  1. Normaliza formas gráficas históricas antes de la lematización.
  2. Agrega excepciones de lematización para formas arcaicas.
  3. Analiza morfología de tokens con marcadores históricos.
  4. Clasifica el texto por "densidad histórica" (qué tan arcaico es).

Funciones:
  normalizar_formas_historicas()  — preprocesa texto antes de NLP
  lematizar_historico()           — lematiza con excepciones históricas
  analizar_morfologia_token()     — análisis morfológico de un token
  analizar_densidad_historica()   — cuántas formas arcaicas hay en el texto
  glosario_arcaismos()            — diccionario de formas → formas modernas
"""

from __future__ import annotations

import re

# ── Mapa de normalización gráfica ─────────────────────────────────────────────
# Formas gráficas históricas → forma ortográfica moderna (solo grafía, no significado)
# Orden: más largo primero para evitar sustituciones parciales

_NORMALIZACION_GRAFICA: list[tuple[str, str]] = [
    # Acentuación histórica con acento grave o tilde en formas que ya no lo llevan
    (r'\bfué\b',       'fue'),
    (r'\bfuí\b',       'fui'),
    (r'\bví\b',        'vi'),
    (r'\bdí\b',        'di'),
    (r'\bsé\b',        'sé'),   # esta sí lleva tilde en español moderno
    (r'\bvió\b',       'vio'),
    (r'\bdió\b',       'dio'),
    # á átona en proposición
    (r'\bá\b(?=\s+[a-záéíóúñ])',  'a'),
    # ó entre números (confusión con 0)
    (r'(\d)\s*ó\s*(\d)', r'\1 o \2'),
    # Consonantismo histórico
    (r'\bsetiembre\b',  'septiembre'),
    (r'\boscuro\b',     'oscuro'),
    (r'\boscuridad\b',  'oscuridad'),
    # Formas con -cion vs -ción (para lematización)
    (r'cion\b',         'ción'),
    # Uso de "i" por "y" conjunción
    (r'\bi\b(?=\s+[a-záéíóúñ])', 'y'),
    # Clíticos arcaicos (dásele, tráigasele, etc.) → se normalizan con espacio
    # NO se tocan (son formas válidas)
]

_RE_NORM = [(re.compile(p, re.IGNORECASE), r) for p, r in _NORMALIZACION_GRAFICA]


# ── Excepciones de lematización ───────────────────────────────────────────────
# {forma_en_texto: lema_moderno}
# Verbos con conjugaciones que spaCy no reconoce bien para el español de los 30

EXCEPCIONES_LEMAS: dict[str, str] = {
    # Ser/estar
    "habia":    "haber",
    "había":    "haber",
    "habias":   "haber",
    "habían":   "haber",
    "hubiera":  "haber",
    "hubiese":  "haber",
    "hubo":     "haber",
    "hubieron": "haber",
    "hube":     "haber",
    "sea":      "ser",
    "seas":     "ser",
    "sean":     "ser",
    "fuera":    "ser",
    "fuese":    "ser",
    "fueran":   "ser",
    "fuesen":   "ser",
    "fuéramos": "ser",
    "fuésemos": "ser",
    # Ir
    "iba":   "ir",
    "ibas":  "ir",
    "iban":  "ir",
    "fuimos": "ir",
    "vayan": "ir",
    "vaya":  "ir",
    # Tener
    "tenia":   "tener",
    "tenía":   "tener",
    "tenian":  "tener",
    "tenían":  "tener",
    "tuviese": "tener",
    "tuviera": "tener",
    "tuvieras": "tener",
    "tuvo":    "tener",
    "tuvieron":"tener",
    "tuve":    "tener",
    # Hacer
    "hacia":   "hacer",   # CUIDADO: 'hacía' ≠ 'hacia' (preposición)
    "hacía":   "hacer",
    "hiciera": "hacer",
    "hiciese": "hacer",
    "hicieron":"hacer",
    "hizo":    "hacer",
    "hice":    "hacer",
    # Dar
    "daba":    "dar",
    "dabas":   "dar",
    "daban":   "dar",
    "diera":   "dar",
    "diese":   "dar",
    "dieron":  "dar",
    # Decir
    "decia":   "decir",
    "decía":   "decir",
    "decian":  "decir",
    "decían":  "decir",
    "dijera":  "decir",
    "dijese":  "decir",
    "dijeron": "decir",
    "dijo":    "decir",
    # Venir
    "venia":   "venir",
    "venía":   "venir",
    "venian":  "venir",
    "venían":  "venir",
    "viniera": "venir",
    "viniese": "venir",
    "vinieron":"venir",
    "vino":    "venir",
    # Poder
    "podia":   "poder",
    "podía":   "poder",
    "podian":  "poder",
    "podían":  "poder",
    "pudiera": "poder",
    "pudiese": "poder",
    "pudieron":"poder",
    "pudo":    "poder",
    # Querer
    "queria":   "querer",
    "quería":   "querer",
    "querian":  "querer",
    "querían":  "querer",
    "quisiera": "querer",
    "quisiese": "querer",
    "quisieron":"querer",
    "quiso":    "querer",
    # Saber
    "sabia":   "saber",
    "sabía":   "saber",
    "sabian":  "saber",
    "sabían":  "saber",
    "supiera": "saber",
    "supiese": "saber",
    "supieron":"saber",
    "supo":    "saber",
    # Sustantivos/adjetivos históricos con variación gráfica
    "patriótico": "patriótico",
    "político":   "político",
    "económico":  "económico",
    # Formas gráficas alternativas
    "espiritu":   "espíritu",
    "publico":    "público",
    "republica":  "república",
    "america":    "América",
    "bogota":     "Bogotá",
    "colombia":   "Colombia",
}


# ── Marcadores morfológicos históricos ────────────────────────────────────────
# Para detectar y etiquetar formas arcaicas

_MARCADORES = {
    # El futuro de subjuntivo aparece tras conjunciones condicionales o
    # relativas ("si hubiere", "cuando llegare", "quien infringiere").
    # Sin ese contexto, el sufijo solo produce falsos positivos masivos:
    # "lugares", "hogares", "millares" terminan en -ares sin ser verbo.
    # El grupo captura la PALABRA COMPLETA, no el sufijo, para que los
    # ejemplos del análisis de densidad sean legibles.
    "futuro_subjuntivo": re.compile(
        r'\b(?:si|cuando|donde|quien|quienes|aunque|mientras|como)\s+'
        r'(\w+(?:are|ares|aren|áremos|areis|iere|ieres|ieren|iéremos|iereis))\b',
        re.IGNORECASE,
    ),
    "voseo": re.compile(
        r'\b(vos|vosotros|vosotras)\b', re.IGNORECASE
    ),
    "vocativo_formal": re.compile(
        r'\b(señor|señora|ilustrísimo|excelentísimo|reverendo|monseñor)\b',
        re.IGNORECASE,
    ),
    "adjetivo_culto": re.compile(
        r'\b(\w+ísim(?:o|a|os|as))\b', re.IGNORECASE
    ),
    "construccion_inversa": re.compile(
        r'\b(díjome|díceme|llamóle|tráiganme|llevóle|trájome)\b',
        re.IGNORECASE,
    ),
    "acusativo_preposicional_arcaico": re.compile(
        r'\bá\s+[A-ZÁÉÍÓÚ][a-záéíóú]+\b'
    ),
}


# ── API pública ───────────────────────────────────────────────────────────────

def normalizar_formas_historicas(texto: str) -> str:
    """
    Normaliza grafías históricas del texto SIN cambiar el significado.
    Útil como preprocesamiento antes de NLP moderno.
    """
    for patron, reemplazo in _RE_NORM:
        texto = patron.sub(reemplazo, texto)
    return texto


def lematizar_historico(
    tokens: list[str],
    usar_excepciones: bool = True,
    nlp=None,
) -> list[dict]:
    """
    Lematiza una lista de tokens aplicando primero las excepciones históricas
    y luego spaCy para los tokens no encontrados.

    Retorna lista de {token, lema, fuente: 'excepcion' | 'spacy' | 'original'}.
    """
    resultado = []

    for tok in tokens:
        tok_lower = tok.lower()
        if usar_excepciones and tok_lower in EXCEPCIONES_LEMAS:
            resultado.append({
                "token":  tok,
                "lema":   EXCEPCIONES_LEMAS[tok_lower],
                "fuente": "excepcion",
            })
        elif nlp is not None:
            try:
                doc = nlp(tok)
                lema = doc[0].lemma_ if doc else tok_lower
                resultado.append({
                    "token":  tok,
                    "lema":   lema,
                    "fuente": "spacy",
                })
            except Exception:
                resultado.append({"token": tok, "lema": tok_lower, "fuente": "original"})
        else:
            resultado.append({"token": tok, "lema": tok_lower, "fuente": "original"})

    return resultado


def analizar_morfologia_token(token: str, nlp=None) -> dict:
    """
    Análisis morfológico detallado de un token:
      {token, lema, fuente_lema, pos, morph, es_arcaismo, tipo_arcaismo}

    Detecta si el token es una forma arcaica y de qué tipo.
    """
    tok_lower = token.lower()
    es_arcaismo = tok_lower in EXCEPCIONES_LEMAS
    lema = EXCEPCIONES_LEMAS.get(tok_lower, tok_lower)
    fuente = "excepcion" if es_arcaismo else "original"

    pos = ""
    morph = ""
    if nlp is not None:
        try:
            doc = nlp(token)
            if doc:
                t = doc[0]
                if not es_arcaismo:
                    lema = t.lemma_
                    fuente = "spacy"
                pos = t.pos_
                morph = str(t.morph)
        except Exception:
            pass

    # Detectar tipo de arcaísmo
    tipo_arcaismo = None
    for tipo, patron in _MARCADORES.items():
        if patron.search(token):
            tipo_arcaismo = tipo
            break

    return {
        "token":         token,
        "lema":          lema,
        "fuente_lema":   fuente,
        "pos":           pos,
        "morph":         morph,
        "es_arcaismo":   es_arcaismo or tipo_arcaismo is not None,
        "tipo_arcaismo": tipo_arcaismo,
    }


def analizar_densidad_historica(texto: str) -> dict:
    """
    Mide la "densidad histórica" de un texto: qué proporción de tokens
    son formas arcaicas o históricamente marcadas.

    Retorna:
      {score_0_1, n_arcaismos, n_tokens, marcadores_detectados,
       ejemplos: [{token, tipo}]}
    """
    if not texto:
        return {"score": 0.0, "n_arcaismos": 0, "n_tokens": 0,
                "marcadores_detectados": {}, "ejemplos": []}

    palabras = re.findall(r'\b[a-záéíóúüñ]+\b', texto.lower())
    n_tokens = len(palabras) or 1

    # Contar excepciones léxicas
    arcaismos_lexicos = [(p, "forma_irregular") for p in palabras
                         if p in EXCEPCIONES_LEMAS]

    # Contar marcadores morfosintácticos
    marcadores_hallados: dict[str, int] = {}
    ejemplos_marc: list[dict] = []
    for tipo, patron in _MARCADORES.items():
        matches = patron.findall(texto)
        if matches:
            marcadores_hallados[tipo] = len(matches)
            ejemplos_marc.extend(
                {"token": m if isinstance(m, str) else m[0], "tipo": tipo}
                for m in matches[:3]
            )

    total_arcaismos = len(arcaismos_lexicos) + sum(marcadores_hallados.values())
    score = min(1.0, total_arcaismos / n_tokens)

    ejemplos = [{"token": t, "tipo": tp} for t, tp in arcaismos_lexicos[:5]]
    ejemplos.extend(ejemplos_marc[:5])

    return {
        "score":                round(score, 4),
        "n_arcaismos":          total_arcaismos,
        "n_tokens":             n_tokens,
        "marcadores_detectados": marcadores_hallados,
        "ejemplos":             ejemplos[:10],
    }


def glosario_arcaismos() -> list[dict]:
    """
    Retorna el glosario completo de excepciones como lista de
    [{forma_historica, lema_moderno}] ordenada alfabéticamente.
    """
    return sorted(
        [{"forma_historica": k, "lema_moderno": v}
         for k, v in EXCEPCIONES_LEMAS.items()],
        key=lambda x: x["forma_historica"],
    )


def enriquecer_corpus_con_lemas(
    corpus: list[str],
    nlp=None,
    callback: callable | None = None,
) -> list[dict]:
    """
    Procesa cada texto del corpus y retorna stats de arcaísmos.
    Útil para un resumen del corpus histórico completo.

    Retorna lista de {doc_idx, n_tokens, n_arcaismos, score, top_arcaismos}.
    """
    resultados = []
    total = len(corpus)

    for i, texto in enumerate(corpus):
        if callback:
            callback(i + 1, total)
        d = analizar_densidad_historica(texto)

        # Top formas arcaicas
        palabras = re.findall(r'\b[a-záéíóúüñ]+\b', texto.lower())
        freq_arc: dict[str, int] = {}
        for p in palabras:
            if p in EXCEPCIONES_LEMAS:
                freq_arc[p] = freq_arc.get(p, 0) + 1
        top = sorted(freq_arc.items(), key=lambda x: -x[1])[:5]

        resultados.append({
            "doc_idx":           i,
            "n_tokens":          d["n_tokens"],
            "n_arcaismos":       d["n_arcaismos"],
            "score":             d["score"],
            "top_arcaismos":     [{"forma": f, "n": n} for f, n in top],
            "marcadores":        d["marcadores_detectados"],
            "ejemplos":          d["ejemplos"],
        })

    return resultados
