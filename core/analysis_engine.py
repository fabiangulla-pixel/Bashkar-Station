"""core/analysis_engine.py — Análisis textual y visual, número a número."""

import gc
import re
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

SECCIONES = {
    "Editorial":     ["editorial"],
    "Crónica":       ["crónica", "cronica"],
    "Reportaje":     ["reportaje", "gran reportaje"],
    "Cuento":        ["cuento"],
    "Poema/Verso":   ["poema", "versos"],
    "Humor/Sátira":  ["humor", "caricatura"],
    "Notas":         ["notas", "apuntes"],
    "Cine":          ["cine", "película", "cinemat"],
    "Teatro":        ["teatro", "escena"],
    "Libros":        ["libros", "bibliografía", "reseña"],
    "Sociedad":      ["sociedad", "gentes"],
    "Política":      ["política", "gobierno", "congreso"],
    "Internacional": ["europa", "guerra", "mundial", "internacional"],
    "Modas/Hogar":   ["modas", "hogar"],
    "Publicidad":    ["publicidad", "aviso", "anuncio"],
    "Deportes":      ["deportes", "fútbol"],
}

CAMPOS_SEM = {
    "Modernidad":  ["moderno", "modernidad", "progreso", "técnica", "industrial",
                    "máquina", "radio", "cine", "automóvil", "avión", "avance"],
    "Nación":      ["colombia", "colombiano", "patria", "nación", "nacional",
                    "bogotá", "república", "estado", "gobierno", "pueblo", "ciudadano"],
    "Género":      ["mujer", "mujeres", "femenino", "familia", "hogar",
                    "moda", "maternidad", "belleza", "matrimonio"],
    "Ciudad":      ["ciudad", "urbano", "calle", "barrio", "edificio",
                    "capital", "plaza", "parque", "comercio", "tranvía"],
    "Guerra/Eur.": ["guerra", "europa", "español", "alemania", "fascismo",
                    "exilio", "refugiado", "francia", "conflicto", "nazismo"],
    "Cultura":     ["literatura", "arte", "poesía", "novela", "música",
                    "teatro", "escritor", "artista", "libro"],
}


def leer_numero(ocr_dir: Path, nombre: str) -> str:
    """Lee y concatena .txt de un número desde disco. Nunca carga todo el corpus."""
    carpeta = ocr_dir / nombre
    if not carpeta.exists():
        return ""
    partes = []
    for f in sorted(carpeta.glob("*.txt")):
        partes.append(f.read_text("utf-8", errors="replace"))
    texto = "\n\n".join(partes)
    del partes
    gc.collect()
    return texto


def analizar_numero_texto(nombre: str, texto: str, colaboradores: list, nlp, stopwords: set):
    """
    Extrae firmas, secciones, campos semánticos y lematiza para LDA.
    Todo se hace sobre el texto ya cargado; al salir, el caller puede borrarlo.
    """
    tl = texto.lower()
    nw = max(len(texto.split()), 1)

    # Firmas
    firmas = [c for c in colaboradores if c.strip() and c.lower() in tl]
    CHUNK = 80_000
    for i in range(0, min(len(texto), 400_000), CHUNK):
        doc = nlp(texto[i:i + CHUNK])
        for ent in doc.ents:
            if ent.label_ == "PER" and len(ent.text.split()) >= 2:
                firmas.append(ent.text.strip())
        del doc
    for m in re.finditer(r"^([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s\.]{3,40})$", texto, re.M):
        c = m.group(1).strip()
        if 2 <= len(c.split()) <= 5:
            firmas.append(c.title())

    # Secciones
    secciones = {}
    for sec, pats in SECCIONES.items():
        cnt = sum(tl.count(p) for p in pats)
        if cnt:
            secciones[sec] = cnt

    # Campos semánticos
    campos = {campo: round(sum(tl.count(t) for t in terms) / nw * 1000, 2)
              for campo, terms in CAMPOS_SEM.items()}

    # Lematización
    texto_limpio = re.sub(r"\d+", " ", tl)
    texto_limpio = re.sub(r"[^a-záéíóúüñ\s]", " ", texto_limpio)
    doc_lem = nlp(texto_limpio[:90_000])
    lema = " ".join(
        t.lemma_ for t in doc_lem
        if not t.is_stop and not t.is_punct
        and len(t.lemma_) > 3 and t.lemma_ not in stopwords
    )
    del doc_lem
    gc.collect()

    return firmas, secciones, campos, lema


def analizar_layout_pagina(img_path: Path) -> dict:
    """Analiza layout de una página y libera la imagen de RAM."""
    try:
        import cv2
        from scipy.signal import find_peaks

        img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
        if img is None:
            return {}
        h, w = img.shape
        mg = int(min(h, w) * 0.05)
        cont = img[mg:h - mg, mg:w - mg]
        hc, wc = cont.shape
        _, bw = cv2.threshold(cont, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        tinta = float(np.sum(bw == 0) / (hc * wc))
        pv = np.sum(bw == 0, axis=0) / hc
        valles, _ = find_peaks(-pv, height=-0.05, distance=int(wc * 0.05))
        n_cols = min(len(valles) + 1, 10)
        BLQ = max(int(hc / 10), 1)
        bi = sum(
            1 for i in range(0, hc - BLQ, BLQ)
            if np.var(img[mg + i:mg + i + BLQ, mg:w - mg].astype(float)) > 1000
            and np.sum(img[mg + i:mg + i + BLQ, mg:w - mg] < 128) / (BLQ * (w - 2 * mg)) > 0.15
        )
        del img, cont, bw, pv
        gc.collect()
        return dict(columnas=n_cols, prop_imagen=round(bi / 10, 2),
                    prop_texto=round(1 - bi / 10, 2), tinta=round(tinta, 3))
    except Exception:
        return {}


def construir_red(df_firmas: pd.DataFrame, min_apariciones: int):
    """Construye grafo de coautoría y retorna objeto nx.Graph."""
    import networkx as nx

    freq = df_firmas.groupby("firma").size()
    relevantes = set(freq[freq >= min_apariciones].index)
    G = nx.Graph()
    for nombre, grp in df_firmas[df_firmas["firma"].isin(relevantes)].groupby("numero"):
        fs = list(grp["firma"].unique())
        for f1, f2 in combinations(fs, 2):
            if G.has_edge(f1, f2):
                G[f1][f2]["weight"] += 1
            else:
                G.add_edge(f1, f2, weight=1)
    for n in G.nodes():
        G.nodes[n]["apariciones"] = int(freq.get(n, 1))
    return G


def run_lda(lema_docs: list, lema_names: list, n_temas: int):
    """Ejecuta LDA y retorna (df_temas, df_doc_temas)."""
    from sklearn.decomposition import LatentDirichletAllocation
    from sklearn.feature_extraction.text import CountVectorizer

    vec = CountVectorizer(max_df=0.9, min_df=2, max_features=2000, ngram_range=(1, 2))
    dtm = vec.fit_transform(lema_docs)
    vocab = vec.get_feature_names_out()

    lda = LatentDirichletAllocation(
        n_components=n_temas, random_state=42,
        max_iter=15, learning_method="online"
    )
    lda.fit(dtm)

    df_temas = pd.DataFrame([{
        "tema": i + 1,
        "palabras_clave": ", ".join(vocab[j] for j in comp.argsort()[:-16:-1])
    } for i, comp in enumerate(lda.components_)])

    dist = lda.transform(dtm)
    df_doc_temas = pd.DataFrame(
        dist,
        columns=[f"tema_{i+1}" for i in range(n_temas)],
        index=lema_names
    )
    df_doc_temas.index.name = "numero"
    df_doc_temas["tema_dominante"] = dist.argmax(axis=1) + 1

    del dtm, lda, vec, vocab, dist
    gc.collect()
    return df_temas, df_doc_temas


# ── Análisis con campos expandidos por vectores ───────────────────────────────

def analizar_numero_con_campos_expandidos(
    nombre: str,
    texto: str,
    colaboradores: list,
    nlp,
    stopwords: set,
    campos_expandidos: dict | None = None,
) -> tuple:
    """
    Versión extendida que acepta campos semánticos expandidos por Word2Vec.
    Si campos_expandidos es None, usa CAMPOS_SEM por defecto.
    """
    campos_uso = campos_expandidos if campos_expandidos else CAMPOS_SEM
    tl  = texto.lower()
    nw  = max(len(texto.split()), 1)

    # Firmas (igual que antes)
    firmas = [c for c in colaboradores if c.strip() and c.lower() in tl]
    CHUNK  = 80_000
    for i in range(0, min(len(texto), 400_000), CHUNK):
        doc = nlp(texto[i:i + CHUNK])
        for ent in doc.ents:
            if ent.label_ == "PER" and len(ent.text.split()) >= 2:
                firmas.append(ent.text.strip())
        del doc

    import re as _re
    for m in _re.finditer(r"^([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s\\.]{3,40})$", texto, _re.M):
        c = m.group(1).strip()
        if 2 <= len(c.split()) <= 5:
            firmas.append(c.title())

    # Secciones
    secciones = {}
    for sec, pats in SECCIONES.items():
        cnt = sum(tl.count(p) for p in pats)
        if cnt:
            secciones[sec] = cnt

    # Campos semánticos (con lista de términos expandida)
    campos = {}
    for campo, terms in campos_uso.items():
        if isinstance(terms, list):
            campos[campo] = round(sum(tl.count(t) for t in terms) / nw * 1000, 2)
        else:
            # Si ya es un número (compatibilidad), dejarlo
            campos[campo] = terms

    # Lematización para LDA
    texto_limpio = _re.sub(r"\d+", " ", tl)
    texto_limpio = _re.sub(r"[^a-záéíóúüñ\s]", " ", texto_limpio)
    doc_lem = nlp(texto_limpio[:90_000])
    lema = " ".join(
        t.lemma_ for t in doc_lem
        if not t.is_stop and not t.is_punct
        and len(t.lemma_) > 3 and t.lemma_ not in stopwords
    )
    del doc_lem; gc.collect()

    return firmas, secciones, campos, lema
