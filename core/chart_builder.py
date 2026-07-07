"""core/chart_builder.py — Constructor flexible de gráficos para análisis editorial.

El investigador elige qué dato graficar y con qué tipo de gráfico.
Todas las funciones retornan una Figure de matplotlib lista para incrustar
en Tkinter o guardar como PNG/SVG.

Fuentes de datos soportadas:
  "tono"        — distribución y evolución de tono editorial
  "ocr"         — confianza OCR por página/número
  "ner"         — frecuencia de entidades nombradas
  "tópicos"     — distribución LDA
  "corpus"      — métricas generales (longitud, secciones, palabras)
  "estilo"      — clusters estilométricos
  "comparativo" — diferencias entre números

Tipos de gráfico soportados por fuente:
  Ver CATALOGO al final del módulo.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
from collections import Counter

import matplotlib.pyplot as plt
import numpy as np

# Paleta consistente con el resto de la app
PALETA = [
    "#3B82F6", "#EF4444", "#22C55E", "#F59E0B", "#8B5CF6",
    "#EC4899", "#0EA5E9", "#F97316", "#14B8A6", "#6366F1",
]

COLORES_TONO = {
    "celebratorio": "#22C55E",
    "crítico":      "#EF4444",
    "neutro":       "#6B7280",
    "elegíaco":     "#8B5CF6",
    "polémico":     "#F59E0B",
    "informativo":  "#3B82F6",
}

_FONDO = "#1E1E2E"
_TEXTO = "#CDD6F4"
_GRID  = "#313244"


def _fig(ancho=9, alto=5):
    fig, ax = plt.subplots(figsize=(ancho, alto))
    fig.patch.set_facecolor(_FONDO)
    ax.set_facecolor(_FONDO)
    ax.tick_params(colors=_TEXTO, labelsize=8)
    ax.xaxis.label.set_color(_TEXTO)
    ax.yaxis.label.set_color(_TEXTO)
    ax.title.set_color(_TEXTO)
    for spine in ax.spines.values():
        spine.set_edgecolor(_GRID)
    ax.grid(color=_GRID, linestyle="--", linewidth=0.5, alpha=0.6)
    return fig, ax


def _fig_multi(filas=1, cols=1, ancho=10, alto=5):
    fig, axes = plt.subplots(filas, cols, figsize=(ancho, alto))
    fig.patch.set_facecolor(_FONDO)
    axs = axes.flatten() if hasattr(axes, "flatten") else [axes]
    for ax in axs:
        ax.set_facecolor(_FONDO)
        ax.tick_params(colors=_TEXTO, labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor(_GRID)
        ax.grid(color=_GRID, linestyle="--", linewidth=0.5, alpha=0.6)
    return fig, axs


# ══════════════════════════════════════════════════════════════════════════════
# FUENTE: TONO EDITORIAL
# ══════════════════════════════════════════════════════════════════════════════

def tono_barras(resultados: dict, titulo: str = "") -> plt.Figure:
    """Barras horizontales de frecuencia por tono."""
    from collections import Counter
    conteo = Counter(r.get("tono_principal", "neutro") for r in resultados.values())
    tonos  = list(COLORES_TONO.keys())
    vals   = [conteo.get(t, 0) for t in tonos]

    fig, ax = _fig(8, 4)
    bars = ax.barh(tonos, vals, color=[COLORES_TONO[t] for t in tonos], height=0.6)
    ax.bar_label(bars, padding=4, color=_TEXTO, fontsize=9)
    ax.set_xlabel("Número de artículos")
    ax.set_title(titulo or "Distribución de tono editorial")
    ax.invert_yaxis()
    plt.tight_layout()
    return fig


def tono_pie(resultados: dict, titulo: str = "") -> plt.Figure:
    """Gráfico de torta de tonos."""
    conteo = Counter(r.get("tono_principal", "neutro") for r in resultados.values())
    tonos  = [t for t in COLORES_TONO if conteo.get(t, 0) > 0]
    vals   = [conteo[t] for t in tonos]
    colores = [COLORES_TONO[t] for t in tonos]

    fig, ax = _fig(7, 5)
    ax.axis("off")
    wedges, texts, autotexts = ax.pie(
        vals, labels=tonos, colors=colores,
        autopct="%1.1f%%", startangle=140,
        textprops={"color": _TEXTO, "fontsize": 9},
    )
    for at in autotexts:
        at.set_color(_FONDO)
        at.set_fontweight("bold")
    ax.set_title(titulo or "Proporción de tonos en el corpus", color=_TEXTO)
    plt.tight_layout()
    return fig


def tono_heatmap(resultados: dict, titulo: str = "") -> plt.Figure:
    """Heatmap tono × número."""
    from collections import defaultdict
    por_numero: dict[str, Counter] = defaultdict(Counter)
    for r in resultados.values():
        num  = str(r.get("numero", "sin_número"))
        tono = r.get("tono_principal", "neutro")
        por_numero[num][tono] += 1

    numeros = sorted(por_numero.keys())
    tonos   = list(COLORES_TONO.keys())
    matriz  = np.array([[por_numero[n].get(t, 0) for n in numeros] for t in tonos],
                        dtype=float)
    # Normalizar por columna (% dentro de cada número)
    col_sum = matriz.sum(axis=0)
    col_sum[col_sum == 0] = 1
    matriz = matriz / col_sum * 100

    fig, ax = _fig(max(7, len(numeros) * 0.9 + 2), max(4, len(tonos) * 0.7 + 1))
    im = ax.imshow(matriz, cmap="RdYlGn", aspect="auto", vmin=0, vmax=100)
    ax.set_xticks(range(len(numeros))); ax.set_xticklabels(numeros, rotation=35, ha="right")
    ax.set_yticks(range(len(tonos)));   ax.set_yticklabels(tonos)
    for i in range(len(tonos)):
        for j in range(len(numeros)):
            val = matriz[i, j]
            ax.text(j, i, f"{val:.0f}%", ha="center", va="center",
                    fontsize=7, color="black" if val > 50 else _TEXTO)
    plt.colorbar(im, ax=ax, label="% artículos", shrink=0.8)
    ax.set_title(titulo or "Heatmap de tono editorial por número")
    plt.tight_layout()
    return fig


def tono_area_apilada(resultados: dict, titulo: str = "") -> plt.Figure:
    """Área apilada de tonos a lo largo del tiempo."""
    from collections import defaultdict
    por_numero: dict[str, Counter] = defaultdict(Counter)
    for r in resultados.values():
        num  = str(r.get("numero", "sin_número"))
        tono = r.get("tono_principal", "neutro")
        por_numero[num][tono] += 1

    numeros = sorted(por_numero.keys())
    if len(numeros) < 2:
        return tono_barras(resultados, titulo)

    tonos = list(COLORES_TONO.keys())
    datos = []
    for tono in tonos:
        fila = []
        for num in numeros:
            total = sum(por_numero[num].values()) or 1
            fila.append(por_numero[num].get(tono, 0) / total * 100)
        datos.append(fila)

    fig, ax = _fig(max(8, len(numeros) * 0.8 + 2), 5)
    ax.stackplot(numeros, datos, labels=tonos,
                 colors=[COLORES_TONO[t] for t in tonos], alpha=0.85)
    ax.set_ylabel("% artículos")
    ax.set_title(titulo or "Evolución del tono editorial (área apilada)")
    ax.legend(loc="upper left", facecolor=_GRID, labelcolor=_TEXTO, fontsize=8)
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    return fig


def tono_radar(resultados: dict, titulo: str = "") -> plt.Figure:
    """Radar chart (spider) de distribución de tonos."""
    conteo = Counter(r.get("tono_principal", "neutro") for r in resultados.values())
    tonos  = list(COLORES_TONO.keys())
    vals   = [conteo.get(t, 0) for t in tonos]
    total  = sum(vals) or 1
    vals_pct = [v / total * 100 for v in vals]

    N = len(tonos)
    angulos = [n / N * 2 * np.pi for n in range(N)]
    angulos += angulos[:1]
    vals_pct += vals_pct[:1]

    fig = plt.figure(figsize=(6, 6))
    fig.patch.set_facecolor(_FONDO)
    ax = fig.add_subplot(111, polar=True)
    ax.set_facecolor(_FONDO)
    ax.plot(angulos, vals_pct, color="#3B82F6", linewidth=2)
    ax.fill(angulos, vals_pct, color="#3B82F6", alpha=0.25)
    ax.set_xticks(angulos[:-1])
    ax.set_xticklabels(tonos, color=_TEXTO, fontsize=9)
    ax.tick_params(colors=_TEXTO)
    ax.yaxis.label.set_color(_TEXTO)
    ax.set_title(titulo or "Radar de tonos editoriales", color=_TEXTO, pad=20)
    plt.tight_layout()
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# FUENTE: OCR — CALIDAD Y CONFIANZA
# ══════════════════════════════════════════════════════════════════════════════

def ocr_boxplot(corpus_confianza: dict, titulo: str = "") -> plt.Figure:
    """Boxplot de confianza OCR por número."""
    por_numero: dict[str, list] = {}
    for pag, info in corpus_confianza.items():
        num  = str(info.get("numero", "sin_número"))
        conf = info.get("confianza", 0.0)
        por_numero.setdefault(num, []).append(conf)

    numeros = sorted(por_numero.keys())
    datos   = [por_numero[n] for n in numeros]

    fig, ax = _fig(max(7, len(numeros) * 0.9 + 2), 5)
    bp = ax.boxplot(datos, labels=numeros, patch_artist=True,
                    medianprops={"color": "#F59E0B", "linewidth": 2})
    for patch, color in zip(bp["boxes"], PALETA):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax.set_ylabel("Confianza OCR (0–1)")
    ax.set_ylim(0, 1.05)
    ax.set_title(titulo or "Distribución de confianza OCR por número")
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    return fig


def ocr_scatter(corpus_confianza: dict, titulo: str = "") -> plt.Figure:
    """Scatter: confianza vs. longitud de página."""
    xs, ys, colores = [], [], []
    for info in corpus_confianza.values():
        conf = info.get("confianza", 0.0)
        long = info.get("palabras", 0)
        num  = info.get("numero", "")
        xs.append(long)
        ys.append(conf)
        colores.append(hash(num) % len(PALETA))

    fig, ax = _fig(8, 5)
    scatter = ax.scatter(xs, ys,
                         c=[PALETA[c] for c in colores],
                         alpha=0.6, s=30, edgecolors="none")
    ax.axhline(0.6, color="#EF4444", linestyle="--", linewidth=1, label="umbral 0.6")
    ax.set_xlabel("Palabras en la página")
    ax.set_ylabel("Confianza OCR")
    ax.set_ylim(0, 1.05)
    ax.legend(facecolor=_GRID, labelcolor=_TEXTO, fontsize=8)
    ax.set_title(titulo or "Confianza OCR vs. longitud de página")
    plt.tight_layout()
    return fig


def ocr_histograma(corpus_confianza: dict, titulo: str = "") -> plt.Figure:
    """Histograma de distribución de confianza OCR."""
    vals = [info.get("confianza", 0.0) for info in corpus_confianza.values()]
    fig, ax = _fig(7, 4)
    ax.hist(vals, bins=20, color="#3B82F6", alpha=0.8, edgecolor=_GRID)
    ax.axvline(np.mean(vals), color="#F59E0B", linestyle="--",
               label=f"media: {np.mean(vals):.2f}")
    ax.axvline(0.6, color="#EF4444", linestyle=":", label="umbral 0.6")
    ax.set_xlabel("Confianza OCR"); ax.set_ylabel("Páginas")
    ax.legend(facecolor=_GRID, labelcolor=_TEXTO, fontsize=8)
    ax.set_title(titulo or "Distribución de confianza OCR")
    plt.tight_layout()
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# FUENTE: ENTIDADES NOMBRADAS (NER)
# ══════════════════════════════════════════════════════════════════════════════

def ner_frecuencia(indice_ner: dict, categoria: str = "PER",
                   top_n: int = 20, titulo: str = "") -> plt.Figure:
    """Barras horizontales de entidades más frecuentes en una categoría."""
    cat_data = indice_ner.get(categoria, {})
    if not cat_data:
        fig, ax = _fig(6, 3)
        ax.text(0.5, 0.5, f"Sin datos para categoría '{categoria}'",
                ha="center", va="center", color=_TEXTO, transform=ax.transAxes)
        return fig

    conteo = {ent: len(arts) for ent, arts in cat_data.items()}
    top = sorted(conteo.items(), key=lambda x: x[1], reverse=True)[:top_n]
    entidades, freqs = zip(*top) if top else ([], [])

    fig, ax = _fig(8, max(4, len(entidades) * 0.35 + 1))
    color = PALETA[list(indice_ner.keys()).index(categoria) % len(PALETA)] if categoria in indice_ner else PALETA[0]
    bars = ax.barh(list(entidades), list(freqs), color=color, alpha=0.8, height=0.6)
    ax.bar_label(bars, padding=3, color=_TEXTO, fontsize=8)
    ax.set_xlabel("Frecuencia (artículos)")
    ax.set_title(titulo or f"Entidades más frecuentes — {categoria}")
    ax.invert_yaxis()
    plt.tight_layout()
    return fig


def ner_categorias(indice_ner: dict, titulo: str = "") -> plt.Figure:
    """Comparación de volumen entre categorías NER."""
    cats   = list(indice_ner.keys())
    totals = [sum(len(v) for v in indice_ner[c].values()) for c in cats]

    fig, ax = _fig(7, 4)
    bars = ax.bar(cats, totals,
                  color=PALETA[:len(cats)], alpha=0.85, width=0.6)
    ax.bar_label(bars, padding=3, color=_TEXTO, fontsize=9)
    ax.set_ylabel("Menciones totales")
    ax.set_title(titulo or "Volumen de entidades por categoría")
    plt.tight_layout()
    return fig


def ner_evolucion(indice_ner: dict, entidades: list[str],
                  campo_numero: str = "numero", titulo: str = "") -> plt.Figure:
    """Evolución de menciones de entidades específicas por número."""
    fig, ax = _fig(9, 5)
    for i, ent in enumerate(entidades[:8]):
        por_num: Counter = Counter()
        for cat_data in indice_ner.values():
            art_ids = cat_data.get(ent, [])
            for aid in art_ids:
                por_num[aid] += 1
        if not por_num:
            continue
        nums = sorted(por_num.keys())
        vals = [por_num[n] for n in nums]
        ax.plot(nums, vals, marker="o", label=ent,
                color=PALETA[i % len(PALETA)], linewidth=1.8)

    ax.set_ylabel("Menciones"); ax.set_xlabel("Número")
    ax.legend(facecolor=_GRID, labelcolor=_TEXTO, fontsize=8)
    ax.set_title(titulo or "Evolución de menciones por número")
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# FUENTE: CORPUS — MÉTRICAS GENERALES
# ══════════════════════════════════════════════════════════════════════════════

def corpus_palabras_por_numero(articulos: list, titulo: str = "") -> plt.Figure:
    """Barras de palabras totales por número."""
    por_numero: Counter = Counter()
    for art in articulos:
        num  = str(art.get("numero", "sin_número"))
        text = art.get("texto", "") or ""
        por_numero[num] += len(text.split())

    numeros = sorted(por_numero.keys())
    vals    = [por_numero[n] for n in numeros]

    fig, ax = _fig(max(7, len(numeros) * 0.8 + 2), 4)
    bars = ax.bar(numeros, vals, color=PALETA[:len(numeros)], alpha=0.85, width=0.6)
    ax.bar_label(bars, padding=3, color=_TEXTO, fontsize=8,
                 labels=[f"{v:,}" for v in vals])
    ax.set_ylabel("Palabras"); ax.set_xlabel("Número")
    ax.set_title(titulo or "Palabras por número del corpus")
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    return fig


def corpus_secciones(articulos: list, titulo: str = "") -> plt.Figure:
    """Treemap de artículos por sección."""
    try:
        import squarify
        _tiene_squarify = True
    except ImportError:
        _tiene_squarify = False

    conteo = Counter(art.get("tipo", "sin_sección") or "sin_sección"
                     for art in articulos)
    top = conteo.most_common(12)
    labels, vals = zip(*top) if top else ([], [])

    fig, ax = _fig(9, 5)
    if _tiene_squarify and vals:
        squarify.plot(sizes=vals,
                      label=[f"{l}\n{v}" for l, v in zip(labels, vals)],
                      color=PALETA[:len(vals)], alpha=0.85, ax=ax,
                      text_kwargs={"color": "white", "fontsize": 8})
        ax.axis("off")
    else:
        bars = ax.barh(list(labels), list(vals),
                       color=PALETA[:len(vals)], alpha=0.85)
        ax.bar_label(bars, padding=3, color=_TEXTO, fontsize=8)
        ax.invert_yaxis()
        ax.set_xlabel("Artículos")
    ax.set_title(titulo or "Artículos por sección")
    plt.tight_layout()
    return fig


def corpus_zipf(corpus_txt: list, titulo: str = "") -> plt.Figure:
    """Curva de Zipf del corpus (ley de potencia en frecuencia de palabras)."""
    import re
    from collections import Counter as C
    conteo: C = C()
    for texto in corpus_txt:
        if texto:
            tokens = re.findall(r"\b[a-záéíóúüñ]{3,}\b", texto.lower())
            conteo.update(tokens)

    freqs = sorted(conteo.values(), reverse=True)[:500]
    ranks = list(range(1, len(freqs) + 1))

    fig, ax = _fig(7, 4)
    ax.loglog(ranks, freqs, color="#3B82F6", linewidth=1.5, label="corpus")
    # Línea de referencia Zipf ideal (f ∝ 1/r)
    zipf_ideal = [freqs[0] / r for r in ranks]
    ax.loglog(ranks, zipf_ideal, color="#EF4444", linestyle="--",
              linewidth=1, label="Zipf ideal")
    ax.set_xlabel("Rango"); ax.set_ylabel("Frecuencia")
    ax.legend(facecolor=_GRID, labelcolor=_TEXTO, fontsize=8)
    ax.set_title(titulo or "Curva de Zipf del corpus")
    plt.tight_layout()
    return fig


def corpus_longitud_articulos(articulos: list, titulo: str = "") -> plt.Figure:
    """Histograma de longitud de artículos en palabras."""
    longitudes = []
    for art in articulos:
        texto = art.get("texto", "") or ""
        longitudes.append(len(texto.split()))

    fig, ax = _fig(7, 4)
    ax.hist(longitudes, bins=30, color="#8B5CF6", alpha=0.8, edgecolor=_GRID)
    media = np.mean(longitudes) if longitudes else 0
    ax.axvline(media, color="#F59E0B", linestyle="--",
               label=f"media: {media:.0f} palabras")
    ax.set_xlabel("Palabras por artículo"); ax.set_ylabel("Artículos")
    ax.legend(facecolor=_GRID, labelcolor=_TEXTO, fontsize=8)
    ax.set_title(titulo or "Distribución de longitud de artículos")
    plt.tight_layout()
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# FUENTE: ESTILOMETRÍA
# ══════════════════════════════════════════════════════════════════════════════

def estilo_pca(articulos: list, titulo: str = "") -> plt.Figure:
    """PCA de artículos en espacio TF-IDF — cada punto es un artículo."""
    try:
        from sklearn.decomposition import PCA
        from sklearn.feature_extraction.text import TfidfVectorizer
    except ImportError:
        fig, ax = _fig(6, 4)
        ax.text(0.5, 0.5, "Instala scikit-learn para PCA\npip install scikit-learn",
                ha="center", va="center", color=_TEXTO, transform=ax.transAxes)
        return fig

    textos  = [art.get("texto", "") or "" for art in articulos]
    secciones = [art.get("tipo", "desconocido") or "desconocido" for art in articulos]
    if len(textos) < 3:
        fig, ax = _fig(6, 4)
        ax.text(0.5, 0.5, "Se necesitan al menos 3 artículos para PCA",
                ha="center", va="center", color=_TEXTO, transform=ax.transAxes)
        return fig

    vec = TfidfVectorizer(max_features=500, ngram_range=(1, 2), min_df=2)
    X   = vec.fit_transform(textos).toarray()
    pca = PCA(n_components=2)
    coords = pca.fit_transform(X)

    cats_unicas = list(dict.fromkeys(secciones))
    color_map   = {c: PALETA[i % len(PALETA)] for i, c in enumerate(cats_unicas)}

    fig, ax = _fig(8, 6)
    for cat in cats_unicas:
        idx = [i for i, s in enumerate(secciones) if s == cat]
        ax.scatter(coords[idx, 0], coords[idx, 1],
                   label=cat, color=color_map[cat], alpha=0.7, s=40)
    ax.legend(facecolor=_GRID, labelcolor=_TEXTO, fontsize=7, ncol=2)
    ax.set_xlabel(f"PC1 ({pca.explained_variance_ratio_[0]*100:.1f}%)")
    ax.set_ylabel(f"PC2 ({pca.explained_variance_ratio_[1]*100:.1f}%)")
    ax.set_title(titulo or "PCA de artículos (espacio TF-IDF)")
    plt.tight_layout()
    return fig


def estilo_dendrograma(articulos: list, max_arts: int = 40, titulo: str = "") -> plt.Figure:
    """Dendrograma de clustering jerárquico por estilo."""
    try:
        from scipy.cluster.hierarchy import dendrogram, linkage
        from scipy.spatial.distance import pdist
        from sklearn.feature_extraction.text import TfidfVectorizer
    except ImportError:
        fig, ax = _fig(6, 4)
        ax.text(0.5, 0.5, "Instala scikit-learn y scipy\npip install scikit-learn scipy",
                ha="center", va="center", color=_TEXTO, transform=ax.transAxes)
        return fig

    muestra = articulos[:max_arts]
    textos  = [art.get("texto", "") or "" for art in muestra]
    labels  = [art.get("titulo", f"art{i}")[:25] for i, art in enumerate(muestra)]
    if len(textos) < 3:
        fig, ax = _fig(6, 4)
        ax.text(0.5, 0.5, "Se necesitan al menos 3 artículos",
                ha="center", va="center", color=_TEXTO, transform=ax.transAxes)
        return fig

    vec = TfidfVectorizer(max_features=300, ngram_range=(2, 3), analyzer="char_wb")
    X   = vec.fit_transform(textos).toarray()
    Z   = linkage(pdist(X, metric="cosine"), method="ward")

    fig, ax = _fig(10, max(5, len(muestra) * 0.25 + 2))
    dendrogram(Z, labels=labels, orientation="left", ax=ax,
               color_threshold=0.7 * max(Z[:, 2]),
               above_threshold_color=_TEXTO,
               leaf_font_size=7)
    ax.set_title(titulo or f"Dendrograma estilométrico (n={len(muestra)})")
    plt.tight_layout()
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# FUENTE: COMPARATIVO
# ══════════════════════════════════════════════════════════════════════════════

def comparativo_divergente(delta: dict, etiqueta_a: str = "A",
                            etiqueta_b: str = "B", titulo: str = "") -> plt.Figure:
    """Barras divergentes: delta de distribución de tonos entre dos números."""
    tonos = list(delta.keys())
    deltas = [delta[t]["delta"] for t in tonos]
    colores = ["#22C55E" if d >= 0 else "#EF4444" for d in deltas]

    fig, ax = _fig(7, 4)
    bars = ax.barh(tonos, deltas, color=colores, alpha=0.85, height=0.6)
    ax.axvline(0, color=_TEXTO, linewidth=1)
    ax.bar_label(bars, padding=3, color=_TEXTO, fontsize=8,
                 labels=[f"{d:+.1f}%" for d in deltas])
    ax.set_xlabel(f"Δ% ({etiqueta_b} − {etiqueta_a})")
    ax.set_title(titulo or f"Diferencia de tono: {etiqueta_b} vs {etiqueta_a}")
    ax.invert_yaxis()
    plt.tight_layout()
    return fig


def comparativo_radar_multi(resultados_por_numero: dict, titulo: str = "") -> plt.Figure:
    """Radar superpuesto comparando varios números."""
    from core.sentiment_engine import estadisticas_tono
    tonos   = ["celebratorio", "crítico", "neutro", "elegíaco", "polémico", "informativo"]
    N       = len(tonos)
    angulos = [n / N * 2 * np.pi for n in range(N)] + [0]

    fig = plt.figure(figsize=(7, 6))
    fig.patch.set_facecolor(_FONDO)
    ax = fig.add_subplot(111, polar=True)
    ax.set_facecolor(_FONDO)
    ax.tick_params(colors=_TEXTO)

    for i, (num, resultados) in enumerate(list(resultados_por_numero.items())[:6]):
        stats  = estadisticas_tono(resultados)["distribucion"]
        vals   = [stats.get(t, {}).get("porcentaje", 0) for t in tonos] + \
                 [stats.get(tonos[0], {}).get("porcentaje", 0)]
        color  = PALETA[i % len(PALETA)]
        ax.plot(angulos, vals, color=color, linewidth=1.8, label=num)
        ax.fill(angulos, vals, color=color, alpha=0.1)

    ax.set_xticks(angulos[:-1])
    ax.set_xticklabels(tonos, color=_TEXTO, fontsize=8)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1),
              facecolor=_GRID, labelcolor=_TEXTO, fontsize=8)
    ax.set_title(titulo or "Comparación de tonos entre números", color=_TEXTO, pad=20)
    plt.tight_layout()
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# CATÁLOGO — define qué gráficos están disponibles para cada fuente
# ══════════════════════════════════════════════════════════════════════════════

CATALOGO: dict[str, list[dict]] = {
    "Tono editorial": [
        {"id": "tono_barras",   "label": "Barras de frecuencia",
         "desc": "Frecuencia de cada categoría de tono en el corpus. "
                 "Útil para mostrar el perfil editorial dominante.",
         "fn": tono_barras,     "param": "resultados"},
        {"id": "tono_pie",      "label": "Gráfico de torta",
         "desc": "Proporción de cada tono. Efectivo cuando hay un tono muy dominante.",
         "fn": tono_pie,        "param": "resultados"},
        {"id": "tono_heatmap",  "label": "Heatmap tono × número",
         "desc": "Intensidad de cada tono por número. "
                 "El gráfico más informativo para mostrar evolución editorial en el paper.",
         "fn": tono_heatmap,    "param": "resultados"},
        {"id": "tono_area",     "label": "Área apilada temporal",
         "desc": "Composición de tonos a lo largo del tiempo. "
                 "Permite ver si el perfil editorial cambia entre períodos.",
         "fn": tono_area_apilada, "param": "resultados"},
        {"id": "tono_radar",    "label": "Radar de tonos",
         "desc": "Perfil del corpus en seis ejes de tono. "
                 "Útil para comparación visual con otras publicaciones.",
         "fn": tono_radar,      "param": "resultados"},
    ],
    "Calidad OCR": [
        {"id": "ocr_boxplot",   "label": "Boxplot por número",
         "desc": "Distribución de confianza OCR por número. "
                 "Muestra variabilidad interna y outliers (páginas problemáticas).",
         "fn": ocr_boxplot,     "param": "confianza"},
        {"id": "ocr_scatter",   "label": "Scatter confianza vs. longitud",
         "desc": "¿Las páginas más largas tienen mejor OCR? "
                 "Permite detectar correlaciones entre densidad textual y calidad.",
         "fn": ocr_scatter,     "param": "confianza"},
        {"id": "ocr_hist",      "label": "Histograma de confianza",
         "desc": "Distribución general de la calidad OCR. "
                 "Muestra qué porcentaje del corpus está por debajo del umbral aceptable.",
         "fn": ocr_histograma,  "param": "confianza"},
    ],
    "Entidades (NER)": [
        {"id": "ner_freq",      "label": "Frecuencia por categoría",
         "desc": "Las entidades más mencionadas en una categoría (PER, LOC, ORG...). "
                 "El gráfico central para análisis de actores en el corpus.",
         "fn": ner_frecuencia,  "param": "ner"},
        {"id": "ner_cats",      "label": "Volumen por categoría",
         "desc": "Cuántas entidades distintas hay en cada categoría. "
                 "Muestra si el corpus es rico en personas, lugares u organizaciones.",
         "fn": ner_categorias,  "param": "ner"},
    ],
    "Corpus general": [
        {"id": "corp_palabras", "label": "Palabras por número",
         "desc": "Volumen textual de cada número. "
                 "Permite ver si hay números más densos o incompletos en el corpus.",
         "fn": corpus_palabras_por_numero, "param": "articulos"},
        {"id": "corp_secciones","label": "Artículos por sección",
         "desc": "Distribución temática del corpus. "
                 "Muestra qué tipo de contenido domina la publicación.",
         "fn": corpus_secciones, "param": "articulos"},
        {"id": "corp_zipf",     "label": "Curva de Zipf",
         "desc": "¿El corpus sigue la ley de Zipf? "
                 "Demuestra que la distribución de palabras es típica de textos naturales.",
         "fn": corpus_zipf,     "param": "corpus_txt"},
        {"id": "corp_longitud", "label": "Longitud de artículos",
         "desc": "Distribución de extensión de artículos. "
                 "Permite distinguir notas breves, crónicas y artículos extensos.",
         "fn": corpus_longitud_articulos, "param": "articulos"},
    ],
    "Estilometría": [
        {"id": "estilo_pca",    "label": "PCA de artículos",
         "desc": "Cada punto es un artículo proyectado en 2D según su estilo TF-IDF. "
                 "Agrupa artículos similares y puede revelar clusters de autoría.",
         "fn": estilo_pca,      "param": "articulos"},
        {"id": "estilo_dendro", "label": "Dendrograma jerárquico",
         "desc": "Árbol de similitud estilística entre artículos. "
                 "Muestra qué artículos comparten patrones de escritura.",
         "fn": estilo_dendrograma, "param": "articulos"},
    ],
    "Comparativo": [
        {"id": "comp_diverg",   "label": "Barras divergentes (delta tono)",
         "desc": "¿En qué tonos difieren más dos números? "
                 "Las barras apuntan a la derecha si el tono aumentó, a la izquierda si bajó.",
         "fn": comparativo_divergente, "param": "delta"},
        {"id": "comp_radar",    "label": "Radar multi-número",
         "desc": "Superpone el perfil de tono de varios números en un mismo gráfico. "
                 "Permite comparar visualmente la evolución editorial.",
         "fn": comparativo_radar_multi, "param": "resultados_por_numero"},
    ],
}
