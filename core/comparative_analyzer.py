"""
core/comparative_analyzer.py — Comparación de perfiles temáticos entre publicaciones.

Funcionalidad:
  · Cargar corpus de referencia (carpetas con .txt por publicación).
  · TF-IDF + distintividad mediante log-likelihood (Dunning).
  · Perfil de campos semánticos comparado.
  · Similaridad coseno entre publicaciones.
"""

import re, gc
from pathlib import Path
from collections import Counter

import numpy as np
import pandas as pd

_RE_TOKEN = re.compile(r"[a-záéíóúüñ]{3,}")

STOPWORDS_ES = {
    "que","con","para","una","por","los","las","del","este","esta","estos","estas",
    "como","más","pero","sus","los","sin","sobre","también","entre","cuando","muy",
    "fue","ser","han","hay","donde","puede","tiene","siendo","siendo","todo","toda",
    "todos","todas","cada","otro","otra","otros","otras","mismo","misma","así","aún",
    "año","años","vez","día","días","hacer","gran","bien","solo","sino","cuyo","cuya",
}


def _tokenizar(texto: str) -> list[str]:
    return [t for t in _RE_TOKEN.findall(texto.lower())
            if t not in STOPWORDS_ES and len(t) >= 4]


def _cargar_corpus(carpeta: Path) -> str:
    """Lee todos los .txt de una carpeta y concatena."""
    partes = []
    for f in carpeta.rglob("*.txt"):
        try:
            partes.append(f.read_text("utf-8", errors="replace"))
        except Exception:
            pass
    return "\n".join(partes)


def cargar_corpora(
    dir_referencia: Path,
    corpus_principal: dict[str, str] | None = None,
) -> dict[str, str]:
    """
    Carga los corpora de referencia desde subcarpetas de dir_referencia.
    Opcionalmente incluye el corpus principal analizado.
    
    Estructura esperada de dir_referencia:
      referencia/
        El_Tiempo/     ← subcarpeta por publicación
          p001.txt
          p002.txt
        Cromos/
          ...
    
    Retorna {nombre_publicacion: texto_concatenado}.
    """
    corpora = {}
    if dir_referencia.exists():
        for sub in sorted(dir_referencia.iterdir()):
            if sub.is_dir():
                texto = _cargar_corpus(sub)
                if texto.strip():
                    corpora[sub.name] = texto
    if corpus_principal:
        corpora.update(corpus_principal)
    return corpora


def _tf(tokens: list[str]) -> dict[str, float]:
    total = max(len(tokens), 1)
    c = Counter(tokens)
    return {t: n/total for t, n in c.items()}


def _idf(corpora_tokens: list[list[str]]) -> dict[str, float]:
    N = len(corpora_tokens)
    df = Counter()
    for tokens in corpora_tokens:
        for t in set(tokens):
            df[t] += 1
    import math
    return {t: math.log(N / max(df[t], 1)) for t in df}


def perfil_tfidf(corpora: dict[str, str], top_n: int = 200) -> pd.DataFrame:
    """
    Calcula el perfil TF-IDF de cada corpus.
    Retorna DataFrame: términos en filas, publicaciones en columnas.
    """
    tok = {n: _tokenizar(t) for n, t in corpora.items()}
    idf = _idf(list(tok.values()))
    
    # Unión de vocabulario relevante
    vocab = sorted({t for tokens in tok.values()
                    for t in Counter(tokens).most_common(top_n * 5)}, key=lambda x: x)
    vocab = [t for t in vocab if idf.get(t, 0) > 0.1][:top_n * len(corpora)]
    
    rows = {}
    for nombre, tokens in tok.items():
        tf = _tf(tokens)
        rows[nombre] = {t: round(tf.get(t, 0) * idf.get(t, 0), 5) for t in vocab}
    
    df = pd.DataFrame(rows).fillna(0)
    # Filtrar filas con algún valor > 0
    df = df[df.max(axis=1) > 0]
    return df


def palabras_distintivas(
    nombre_foco: str,
    corpora: dict[str, str],
    top_n: int = 40,
) -> dict[str, list[tuple[str, float]]]:
    """
    Encuentra palabras estadísticamente distintivas de 'nombre_foco'
    respecto a cada otra publicación usando log-likelihood (Dunning G²).
    
    Retorna {nombre_referencia: [(palabra, g2_score), ...]}.
    """
    tok_foco = Counter(_tokenizar(corpora.get(nombre_foco, "")))
    n_foco   = max(sum(tok_foco.values()), 1)
    
    resultados = {}
    for nombre, texto in corpora.items():
        if nombre == nombre_foco:
            continue
        tok_ref = Counter(_tokenizar(texto))
        n_ref   = max(sum(tok_ref.values()), 1)
        
        vocab_union = set(tok_foco) | set(tok_ref)
        scores = []
        
        for palabra in vocab_union:
            a = tok_foco.get(palabra, 0)   # foco: sí
            b = tok_ref.get(palabra, 0)    # ref:  sí
            c = n_foco - a                  # foco: no
            d = n_ref  - b                  # ref:  no
            N = a + b + c + d
            if N == 0 or (a + b) == 0 or (c + d) == 0:
                continue
            # G² de Dunning (log-likelihood)
            def _ll(obs, exp):
                if obs == 0 or exp <= 0: return 0
                import math; return 2 * obs * math.log(obs / exp)
            
            e1 = (a+b) * (a+c) / N
            e2 = (a+b) * (b+d) / N
            e3 = (c+d) * (a+c) / N
            e4 = (c+d) * (b+d) / N
            g2 = _ll(a,e1) + _ll(b,e2) + _ll(c,e3) + _ll(d,e4)
            # Signo: positivo si más frecuente en foco que en referencia
            ratio = (a/n_foco) / max(b/n_ref, 1e-9)
            if ratio < 1:
                g2 = -g2
            scores.append((palabra, round(g2, 1)))
        
        # Top N más distintivas para foco (positivas)
        scores.sort(key=lambda x: -x[1])
        resultados[nombre] = scores[:top_n]
    
    return resultados


def similaridad_coseno_tfidf(df_tfidf: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula matriz de similaridad coseno entre publicaciones usando TF-IDF.
    df_tfidf: salida de perfil_tfidf (términos × publicaciones).
    """
    cols = df_tfidf.columns.tolist()
    mat  = df_tfidf.values.T  # publicaciones × términos
    normas = np.linalg.norm(mat, axis=1, keepdims=True)
    normas[normas == 0] = 1
    mat_n = mat / normas
    sim   = mat_n @ mat_n.T
    return pd.DataFrame(sim, index=cols, columns=cols).round(3)


def comparar_campos_semanticos(
    corpora: dict[str, str],
    campos: dict[str, list[str]],
) -> pd.DataFrame:
    """
    Calcula la densidad de cada campo semántico (menciones/1000 palabras)
    en cada corpus. Facilita la comparación visual directa.
    """
    filas = []
    for nombre, texto in corpora.items():
        tl = texto.lower()
        tokens = _tokenizar(tl)
        n = max(len(tokens), 1)
        fila = {"publicacion": nombre}
        for campo, terminos in campos.items():
            menciones = sum(tl.count(t) for t in terminos)
            fila[campo] = round(menciones / n * 1000, 2)
        filas.append(fila)
    return pd.DataFrame(filas).set_index("publicacion")


def generar_reporte_comparativo(
    nombre_foco: str,
    corpora: dict[str, str],
    campos: dict[str, list[str]],
) -> dict:
    """
    Genera un reporte completo de análisis comparativo.
    Retorna dict con: similitudes, distintivas, perfil_campos.
    """
    if not corpora:
        return {}
    
    df_tfidf  = perfil_tfidf(corpora, top_n=300)
    sim       = similaridad_coseno_tfidf(df_tfidf)
    dist      = palabras_distintivas(nombre_foco, corpora, top_n=30)
    campos_df = comparar_campos_semanticos(corpora, campos)
    
    gc.collect()
    
    return {
        "similaridad":     sim,
        "palabras_distintivas": dist,
        "perfil_campos":   campos_df,
        "n_corpora":       len(corpora),
    }
