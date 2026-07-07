"""
core/charts.py — Módulo de visualización para Bashkar Station.

Paleta editorial amplia y contrastada.
Tipos de gráficas:
  barras, columnas, jerarquía (treemap), cascada (waterfall),
  líneas, áreas, histograma, circular/anillo, dispersión/burbujas,
  radial (spider/radar), combinada (barras + línea), heatmap.
"""

import io
import gc
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import to_rgba
from pathlib import Path

# ── Paleta editorial amplia y contrastada ─────────────────────────────────────
PAL = [
    "#1A3A5C",   # azul marino profundo
    "#E8A838",   # ámbar dorado
    "#C0392B",   # rojo colonial
    "#27AE60",   # verde selva
    "#8E44AD",   # violeta oscuro
    "#2980B9",   # azul cielo
    "#E67E22",   # naranja terracota
    "#16A085",   # verde esmeralda
    "#D35400",   # ladrillo
    "#2C3E50",   # gris acero
    "#F39C12",   # amarillo mostaza
    "#7F8C8D",   # gris paloma
]

BG   = "#FAF9F7"   # fondo papel
GRID = "#E8E4DE"   # cuadrícula suave


def _fig_bytes(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor=BG)
    buf.seek(0); data = buf.read()
    plt.close(fig); gc.collect()
    return data


def _base_fig(w=10, h=5):
    fig, ax = plt.subplots(figsize=(w, h))
    fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
    ax.grid(True, color=GRID, linewidth=0.6, zorder=0)
    ax.spines[["top","right"]].set_visible(False)
    ax.spines[["left","bottom"]].set_color("#AAA")
    return fig, ax


def _titulo_estilo(ax, titulo: str, subtitulo: str = ""):
    ax.set_title(titulo, fontsize=13, fontweight="bold", color=PAL[0], pad=10)
    if subtitulo:
        ax.annotate(subtitulo, xy=(0.5, 1.02), xycoords="axes fraction",
                    ha="center", fontsize=9, color="#666")


# ══════════════════════════════════════════════════════════════════════════════
# 1. BARRAS HORIZONTALES (ranking)
# ══════════════════════════════════════════════════════════════════════════════
def barras_horizontales(
    categorias: list, valores: list,
    titulo: str = "", etiqueta_x: str = "",
    colores: list = None, max_items: int = 25,
) -> bytes:
    cats = categorias[:max_items]; vals = valores[:max_items]
    n = len(cats); cols = colores or [PAL[i % len(PAL)] for i in range(n)]
    fig, ax = _base_fig(w=10, h=max(4, n * 0.38))
    bars = ax.barh(range(n), vals, color=cols, edgecolor="white", linewidth=0.5, zorder=3)
    ax.set_yticks(range(n)); ax.set_yticklabels(cats, fontsize=9)
    ax.set_xlabel(etiqueta_x, fontsize=9); _titulo_estilo(ax, titulo)
    ax.bar_label(bars, padding=4, fontsize=8, fmt="%.0f")
    ax.invert_yaxis()
    plt.tight_layout()
    return _fig_bytes(fig)


# ══════════════════════════════════════════════════════════════════════════════
# 2. COLUMNAS VERTICALES
# ══════════════════════════════════════════════════════════════════════════════
def columnas(
    categorias: list, valores: list,
    titulo: str = "", etiqueta_y: str = "",
    colores: list = None,
) -> bytes:
    n    = len(categorias)
    cols = colores or [PAL[i % len(PAL)] for i in range(n)]
    fig, ax = _base_fig(w=max(7, n * 0.7), h=5)
    bars = ax.bar(range(n), valores, color=cols, edgecolor="white", linewidth=0.5, zorder=3, width=0.65)
    ax.set_xticks(range(n))
    ax.set_xticklabels(categorias, rotation=35, ha="right", fontsize=9)
    ax.set_ylabel(etiqueta_y, fontsize=9); _titulo_estilo(ax, titulo)
    ax.bar_label(bars, padding=3, fontsize=8, fmt="%.1f")
    plt.tight_layout()
    return _fig_bytes(fig)


# ══════════════════════════════════════════════════════════════════════════════
# 3. TREEMAP (jerarquía)
# ══════════════════════════════════════════════════════════════════════════════
def treemap(etiquetas: list, valores: list, titulo: str = "") -> bytes:
    try:
        import squarify
    except ImportError:
        # Fallback: pie chart si squarify no está instalado
        return circular(etiquetas, valores, titulo=titulo)

    total = max(sum(valores), 1)
    fig, ax = plt.subplots(figsize=(11, 6))
    fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
    cols = [PAL[i % len(PAL)] for i in range(len(etiquetas))]
    squarify.plot(
        sizes=valores,
        label=[f"{e}\n{v:,.0f}\n({v/total*100:.1f}%)" for e, v in zip(etiquetas, valores)],
        color=cols, alpha=0.88, linewidth=2, edgecolor="white",
        text_kwargs={"fontsize": 8, "color": "white", "fontweight": "bold"},
        ax=ax,
    )
    ax.axis("off")
    _titulo_estilo(ax, titulo)
    plt.tight_layout()
    return _fig_bytes(fig)


# ══════════════════════════════════════════════════════════════════════════════
# 4. WATERFALL / CASCADA
# ══════════════════════════════════════════════════════════════════════════════
def waterfall(
    etiquetas: list, valores: list,
    titulo: str = "", etiqueta_y: str = "",
) -> bytes:
    n = len(etiquetas)
    running = 0; bottoms = []; colors = []
    for v in valores:
        bottoms.append(running)
        colors.append(PAL[2] if v < 0 else PAL[0])
        running += v
    # Barra total al final
    etiquetas = list(etiquetas) + ["Total"]
    valores    = list(valores)    + [running]
    bottoms    = bottoms           + [0]
    colors     = colors            + [PAL[7]]

    fig, ax = _base_fig(w=max(8, n*0.8+1), h=5)
    bars = ax.bar(range(len(etiquetas)), valores, bottom=bottoms,
                  color=colors, edgecolor="white", linewidth=0.5, zorder=3, width=0.65)
    ax.set_xticks(range(len(etiquetas)))
    ax.set_xticklabels(etiquetas, rotation=35, ha="right", fontsize=9)
    ax.set_ylabel(etiqueta_y, fontsize=9); _titulo_estilo(ax, titulo)
    # Valores sobre cada barra
    for i, (b, v) in enumerate(zip(bottoms, valores)):
        ax.text(i, b + v + max(abs(running)*0.01, 0.5), f"{v:+.1f}",
                ha="center", va="bottom", fontsize=8, color="#333")
    ax.axhline(0, color="#AAA", linewidth=0.8, zorder=2)
    plt.tight_layout()
    return _fig_bytes(fig)


# ══════════════════════════════════════════════════════════════════════════════
# 5. LÍNEAS (evolución temporal)
# ══════════════════════════════════════════════════════════════════════════════
def lineas(
    x: list, series: dict,
    titulo: str = "", etiqueta_x: str = "", etiqueta_y: str = "",
    markers: bool = True,
) -> bytes:
    fig, ax = _base_fig(w=12, h=5)
    for i, (nombre, vals) in enumerate(series.items()):
        mk = "o" if markers else None
        ax.plot(x, vals, color=PAL[i % len(PAL)], linewidth=2.2,
                marker=mk, markersize=5, label=nombre, zorder=3)
    ax.set_xlabel(etiqueta_x, fontsize=9); ax.set_ylabel(etiqueta_y, fontsize=9)
    ax.set_xticks(range(len(x))); ax.set_xticklabels(x, rotation=35, ha="right", fontsize=9)
    _titulo_estilo(ax, titulo)
    if len(series) > 1:
        ax.legend(fontsize=9, framealpha=0.9, edgecolor=GRID)
    plt.tight_layout()
    return _fig_bytes(fig)


# ══════════════════════════════════════════════════════════════════════════════
# 6. ÁREAS APILADAS
# ══════════════════════════════════════════════════════════════════════════════
def areas_apiladas(
    x: list, series: dict,
    titulo: str = "", etiqueta_y: str = "",
) -> bytes:
    fig, ax = _base_fig(w=12, h=5)
    nombres = list(series.keys()); xs = range(len(x))
    cols = [PAL[i % len(PAL)] for i in range(len(nombres))]
    ax.stackplot(xs, [series[n] for n in nombres],
                 labels=nombres, colors=cols, alpha=0.82, zorder=3)
    ax.set_xticks(xs); ax.set_xticklabels(x, rotation=35, ha="right", fontsize=9)
    ax.set_ylabel(etiqueta_y, fontsize=9); _titulo_estilo(ax, titulo)
    ax.legend(loc="upper left", fontsize=9, framealpha=0.9, edgecolor=GRID)
    plt.tight_layout()
    return _fig_bytes(fig)


# ══════════════════════════════════════════════════════════════════════════════
# 7. HISTOGRAMA
# ══════════════════════════════════════════════════════════════════════════════
def histograma(
    valores: list, titulo: str = "",
    etiqueta_x: str = "", bins: int = 15,
) -> bytes:
    fig, ax = _base_fig(w=9, h=5)
    n, edges, patches = ax.hist(valores, bins=bins, edgecolor="white",
                                 linewidth=0.6, zorder=3)
    # Colorear por cuantiles
    cmap = plt.get_cmap("Blues_r")
    for i, patch in enumerate(patches):
        patch.set_facecolor(PAL[0] if i % 2 == 0 else PAL[1])
    ax.set_xlabel(etiqueta_x, fontsize=9); ax.set_ylabel("Frecuencia", fontsize=9)
    _titulo_estilo(ax, titulo)
    plt.tight_layout()
    return _fig_bytes(fig)


# ══════════════════════════════════════════════════════════════════════════════
# 8. CIRCULAR Y DE ANILLO (pie/donut)
# ══════════════════════════════════════════════════════════════════════════════
def circular(
    etiquetas: list, valores: list,
    titulo: str = "", anillo: bool = False,
) -> bytes:
    fig, ax = plt.subplots(figsize=(8, 6))
    fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
    cols = [PAL[i % len(PAL)] for i in range(len(etiquetas))]
    wedges, texts, autotexts = ax.pie(
        valores, labels=etiquetas, autopct="%1.1f%%",
        colors=cols, startangle=90,
        pctdistance=0.80, labeldistance=1.08,
        wedgeprops={"linewidth": 1.5, "edgecolor": "white"},
    )
    for t in texts:
        t.set_fontsize(9)
    for at in autotexts:
        at.set_fontsize(8); at.set_color("white"); at.set_fontweight("bold")
    if anillo:
        circle = plt.Circle((0, 0), 0.55, color=BG)
        ax.add_artist(circle)
    _titulo_estilo(ax, titulo)
    plt.tight_layout()
    return _fig_bytes(fig)


# ══════════════════════════════════════════════════════════════════════════════
# 9. DISPERSIÓN / BURBUJAS
# ══════════════════════════════════════════════════════════════════════════════
def dispersion(
    x: list, y: list,
    etiquetas: list = None, tamanos: list = None,
    titulo: str = "", etiqueta_x: str = "", etiqueta_y: str = "",
) -> bytes:
    fig, ax = _base_fig(w=9, h=6)
    s = [max(40, v * 2) for v in tamanos] if tamanos else 80
    scatter = ax.scatter(x, y, c=range(len(x)), cmap="Blues",
                          s=s, alpha=0.8, edgecolors=PAL[0],
                          linewidth=0.8, zorder=3)
    if etiquetas:
        for xi, yi, lbl in zip(x, y, etiquetas):
            ax.annotate(lbl, (xi, yi), textcoords="offset points",
                        xytext=(5, 4), fontsize=8, color="#333")
    ax.set_xlabel(etiqueta_x, fontsize=9); ax.set_ylabel(etiqueta_y, fontsize=9)
    _titulo_estilo(ax, titulo)
    plt.tight_layout()
    return _fig_bytes(fig)


# ══════════════════════════════════════════════════════════════════════════════
# 10. RADIAL / SPIDER / RADAR
# ══════════════════════════════════════════════════════════════════════════════
def radial(
    categorias: list, series: dict,
    titulo: str = "",
) -> bytes:
    N = len(categorias)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angles += angles[:1]   # cerrar el polígono

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw={"polar": True})
    fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
    ax.set_thetagrids(np.degrees(angles[:-1]), categorias, fontsize=9)
    ax.yaxis.set_tick_params(labelsize=7)
    ax.grid(color=GRID, linewidth=0.7)

    for i, (nombre, vals) in enumerate(series.items()):
        v = list(vals) + [vals[0]]
        ax.plot(angles, v, color=PAL[i % len(PAL)], linewidth=2, label=nombre)
        ax.fill(angles, v, color=PAL[i % len(PAL)], alpha=0.18)

    if len(series) > 1:
        ax.legend(loc="lower right", fontsize=9, framealpha=0.9, edgecolor=GRID)
    ax.set_title(titulo, fontsize=12, fontweight="bold", color=PAL[0], pad=20)
    plt.tight_layout()
    return _fig_bytes(fig)


# ══════════════════════════════════════════════════════════════════════════════
# 11. COMBINADA (barras + línea)
# ══════════════════════════════════════════════════════════════════════════════
def combinada(
    x: list,
    barras_vals: list, barras_label: str,
    linea_vals:  list, linea_label:  str,
    titulo: str = "",
) -> bytes:
    fig, ax1 = _base_fig(w=12, h=5)
    bars = ax1.bar(range(len(x)), barras_vals, color=PAL[0],
                    alpha=0.82, width=0.65, label=barras_label, zorder=3)
    ax1.set_ylabel(barras_label, color=PAL[0], fontsize=9)
    ax1.set_xticks(range(len(x)))
    ax1.set_xticklabels(x, rotation=35, ha="right", fontsize=9)
    ax1.tick_params(axis="y", colors=PAL[0])

    ax2 = ax1.twinx()
    ax2.plot(range(len(x)), linea_vals, color=PAL[1], linewidth=2.5,
             marker="o", markersize=6, label=linea_label, zorder=4)
    ax2.set_ylabel(linea_label, color=PAL[1], fontsize=9)
    ax2.tick_params(axis="y", colors=PAL[1])
    ax2.set_facecolor(BG)

    _titulo_estilo(ax1, titulo)
    # Leyenda combinada
    handles1, labs1 = ax1.get_legend_handles_labels()
    handles2, labs2 = ax2.get_legend_handles_labels()
    ax1.legend(handles1+handles2, labs1+labs2, loc="upper left",
               fontsize=9, framealpha=0.9, edgecolor=GRID)
    plt.tight_layout()
    return _fig_bytes(fig)


# ══════════════════════════════════════════════════════════════════════════════
# 12. HEATMAP (mapa de calor)
# ══════════════════════════════════════════════════════════════════════════════
def heatmap(
    df: pd.DataFrame,
    titulo: str = "",
    cmap: str = "YlOrRd",
    anotaciones: bool = True,
) -> bytes:
    import seaborn as sns
    fig, ax = plt.subplots(figsize=(max(8, len(df.columns)*0.9),
                                     max(5, len(df)*0.55)))
    fig.patch.set_facecolor(BG)
    sns.heatmap(
        df, ax=ax, cmap=cmap, annot=anotaciones, fmt=".1f",
        linewidths=0.5, linecolor="white",
        cbar_kws={"shrink": 0.75, "label": "valor"},
        annot_kws={"size": 8},
    )
    _titulo_estilo(ax, titulo)
    ax.tick_params(axis="x", labelsize=8, rotation=40)
    ax.tick_params(axis="y", labelsize=8, rotation=0)
    plt.tight_layout()
    return _fig_bytes(fig)
