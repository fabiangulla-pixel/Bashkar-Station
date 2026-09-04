"""Tesseract sobre El Gráfico: ¿qué da la ruta sin capa de texto?

*El Gráfico* es la única publicación de la muestra sin capa de texto (44
caracteres por página, que son marca de agua). Es también el primer contraste
colombiano elegido en el plan de la beca, así que la ruta "OCR desde cero" tiene
que resolverse sí o sí.

Esta prueba establece el **punto de partida barato**: qué produce Tesseract, que
ya está instalado y es gratis. Si el resultado es usable, CHURRO pasa a ser una
mejora; si es basura, CHURRO es un rescate y justifica sus 7 GB y sus 3 min/página.

Se mide con los mismos criterios que el resto del estudio (fusión >16 caracteres,
fragmento de 1-2 caracteres fuera de una lista de palabras cortas legítimas) para
que las cifras sean comparables con la tabla de las otras ocho publicaciones.

Comparador incluido: la misma medida sobre *Estampa* por su ruta buena, para
tener a la vista qué significa "aceptable" en este corpus.
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

RAIZ = r"I:\Mi unidad\00_Programas y macros\Bashkar Station\bashkar_station"
sys.path.insert(0, RAIZ)

from core import ocr_engine  # noqa: E402

PDF = Path(r"C:\build_rf\generalizacion\muestra\El_Gráfico.pdf")
TRABAJO = Path(r"C:\build_rf\generalizacion\tesseract_grafico")
N_PAGINAS = 3
DPI = 300

CORTAS_OK = {
    "a", "y", "o", "e", "u", "de", "la", "el", "en", "un", "es", "se", "no",
    "lo", "al", "su", "si", "ya", "me", "te", "le", "mi", "tu", "ni", "os",
    "da", "va", "ha", "he", "fe", "df",
}
_RE_TOKEN = re.compile(r"[^\W\d_]+", re.UNICODE)


def medir(texto: str) -> dict:
    tokens = _RE_TOKEN.findall(texto)
    n = len(tokens)
    if not n:
        return {"tokens": 0, "fusion_pct": 0.0, "frag_pct": 0.0, "largo_medio": 0.0}
    fus = sum(1 for t in tokens if len(t) > 16)
    frag = sum(1 for t in tokens if len(t) <= 2 and t.lower() not in CORTAS_OK)
    return {
        "tokens": n,
        "fusion_pct": 100 * fus / n,
        "frag_pct": 100 * frag / n,
        "largo_medio": sum(len(t) for t in tokens) / n,
    }


def main() -> None:
    TRABAJO.mkdir(parents=True, exist_ok=True)
    print(f"Convirtiendo {PDF.name} a imagenes a {DPI} dpi...", flush=True)
    t0 = time.time()
    imgs = ocr_engine.pdf_a_imagenes(PDF, TRABAJO / "img", DPI)
    print(f"  {len(imgs)} paginas en {time.time()-t0:.0f}s", flush=True)

    # Paginas repartidas, no las primeras: la portada no representa el cuerpo.
    paso = max(1, len(imgs) // N_PAGINAS)
    elegidas = imgs[::paso][:N_PAGINAS]

    textos = []
    print(flush=True)
    print(f"{'PAGINA':22s} {'SEG':>6} {'CONF':>6} {'TOKENS':>7} {'FUSION':>8} "
          f"{'FRAG':>7} {'LARGO':>6}", flush=True)
    print("-" * 70, flush=True)
    for img in elegidas:
        t = time.time()
        texto, conf = ocr_engine.ocr_pagina(img, lang="spa")
        dt = time.time() - t
        m = medir(texto)
        textos.append(texto)
        print(f"{img.stem[:22]:22s} {dt:>6.1f} {conf:>6.1f} {m['tokens']:>7} "
              f"{m['fusion_pct']:>7.2f}% {m['frag_pct']:>6.1f}% "
              f"{m['largo_medio']:>6.2f}", flush=True)

    total = medir("\n".join(textos))
    print(flush=True)
    print("EL GRAFICO por Tesseract (agregado):", flush=True)
    print(f"  tokens {total['tokens']} · fusion {total['fusion_pct']:.2f}% · "
          f"fragmento {total['frag_pct']:.1f}% · largo medio "
          f"{total['largo_medio']:.2f}", flush=True)

    veredicto = ("USABLE" if total["frag_pct"] < 10 else
                 "DEGRADADO" if total["frag_pct"] < 20 else
                 "NO USABLE sin otra ruta")
    print(f"  veredicto: {veredicto}  (linea base Estampa: 6,8% fragmento)",
          flush=True)

    muestra = "\n".join(textos)[:700]
    print(flush=True)
    print("Muestra del texto obtenido:", flush=True)
    print("-" * 70, flush=True)
    print(muestra, flush=True)

    salida = TRABAJO / "texto_tesseract.txt"
    salida.write_text("\n\n".join(textos), encoding="utf-8")
    print(f"\nTexto completo en {salida}", flush=True)


if __name__ == "__main__":
    main()
