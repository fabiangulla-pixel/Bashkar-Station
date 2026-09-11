"""¿Sirven de algo los flags `bold`/`italic` que calcula `alto_reconstructor`?

`alto_reconstructor.reconstruir_texto_pagina` calcula `bold` e `italic` por
línea desde los flags de PyMuPDF, y **nadie los consume**: se computan en cada
línea de cada página del corpus y se tiran. El roadmap "estilo FineReader" los
tenía apuntados como pendiente de detectar, cuando en realidad ya se detectan y
lo que falta es un consumidor.

El consumidor natural sería la detección de títulos (`es_titulo`), que hoy
decide solo por tamaño de fuente: un título de prensa suele ir en negrita, así
que la negrita podría rescatar títulos que el umbral de tamaño se pierde. Antes
de cambiar esa heurística —que mueve la segmentación de todo el corpus, y con
ella los ids y los análisis— hay que medir si la señal existe.

Medido el 10-sep-2026 sobre 8 páginas de un ejemplar de cada publicación:

    PUBLICACION               LINEAS    BOLD    ITAL    TIT  TIT&BOLD  BOLD~TIT
    Agitación Femenina           640    2.0%    4.8%     32        13         0
    El Día                      2050    0.5%   11.7%    110         8         3
    El Gráfico                     8    0.0%    0.0%      0         0         0
    El Nuevo Tiempo             2048    0.1%   20.5%    528         1         2
    Estampa (1939)               782    1.4%   26.6%     61        11         0
    La Mujer                     457    2.0%    9.4%     24         3         6
    La Semana Cómica             739    5.4%    8.1%     54        19        21
    Panida                       311    4.5%   12.5%     23         6         8
    Rin-Rin                      205    1.0%    6.8%      6         0         2

## Conclusión: no cablear la negrita a `es_titulo`

**`italic` no es señal, es ruido.** Marca hasta el 26,6 % de las líneas de
*Estampa* y el 20,5 % de *El Nuevo Tiempo*. En una capa de Paper Capture eso no
puede ser cursiva real de la página: es cómo el OCR clasificó la tipografía.
No usarlo para nada.

**`bold` es preciso pero no aporta.** Donde aparece suele ser título de verdad
—en *Estampa* y *Agitación Femenina*, el 100 % de las líneas en negrita ya
estaban marcadas como título—, pero justo por eso **no rescata nada**: los
títulos que la negrita señala son los que el umbral de tamaño ya detecta. En
*Estampa* cubriría 11 de 61 títulos, todos ya detectados. Y donde no coincide,
mete ruido: en *La Semana Cómica*, 21 líneas en negrita no son título, más que
las 19 que sí lo son; en *La Mujer*, 6 de 9.

Añadir `bold` como criterio alternativo (`es_titulo = tamaño O negrita`)
empeoraría *La Semana Cómica*, *Panida*, *La Mujer* y *Rin-Rin* sin mejorar
*Estampa* ni *Agitación Femenina*. Como criterio de refuerzo
(`tamaño Y negrita`) descartaría el 80 % de los títulos correctos.

**Esta línea del roadmap se cierra con evidencia, no se deja abierta.** Si
alguna vez se quiere volver a ella, lo que haría falta primero es una verdad de
referencia humana de títulos —marcar a mano los títulos reales de unas cuantas
páginas—, porque aquí se está midiendo contra `es_titulo`, que es la propia
heurística que se quería mejorar, no contra la realidad de la página.

Reproducir: `python senal_tipografica.py` (necesita el corpus en
`C:\build_rf\bashkar_corpus`, ver `copiar_corpus.py`).
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import fitz  # noqa: E402

from core import alto_reconstructor as ar  # noqa: E402

CORPUS = Path(r"C:\build_rf\bashkar_corpus")
N_PAGINAS = 8


def medir(pdf: Path) -> Counter:
    tot: Counter = Counter()
    doc = fitz.open(str(pdf))
    try:
        paso = max(1, len(doc) // N_PAGINAS)
        for i in list(range(0, len(doc), paso))[:N_PAGINAS]:
            try:
                datos = ar.reconstruir_texto_pagina(doc[i], ignorar_ocr_basura=True)
            except Exception:
                continue
            for linea in datos.get("lineas", []):
                negrita = bool(linea.get("bold"))
                titulo = bool(linea.get("es_titulo"))
                tot["n"] += 1
                tot["bold"] += negrita
                tot["ital"] += bool(linea.get("italic"))
                tot["tit"] += titulo
                if titulo and negrita:
                    tot["tit_bold"] += 1
                if negrita and not titulo:
                    tot["bold_no_tit"] += 1
    finally:
        doc.close()
    return tot


def main() -> None:
    if not CORPUS.exists():
        print(f"No existe {CORPUS}. Copia el corpus con copiar_corpus.py primero.")
        return

    print(f"{'PUBLICACION':24s} {'LINEAS':>7} {'BOLD':>7} {'ITAL':>7} "
          f"{'TIT':>6} {'TIT&BOLD':>9} {'BOLD~TIT':>9}")
    print("-" * 76)

    for carpeta in sorted(p for p in CORPUS.iterdir() if p.is_dir()):
        pdf = next(iter(sorted(carpeta.glob("*.pdf"))), None)
        if pdf is None:
            continue
        t = medir(pdf)
        n = max(t["n"], 1)
        print(f"{carpeta.name[:24]:24s} {t['n']:>7} "
              f"{100*t['bold']/n:>6.1f}% {100*t['ital']/n:>6.1f}% "
              f"{t['tit']:>6} {t['tit_bold']:>9} {t['bold_no_tit']:>9}")


if __name__ == "__main__":
    main()
