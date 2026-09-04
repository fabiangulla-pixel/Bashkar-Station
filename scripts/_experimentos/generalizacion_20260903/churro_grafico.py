"""CHURRO-3B sobre El Gráfico, comparado contra Tesseract en las MISMAS páginas.

*El Gráfico* (1910) es la única publicación de la muestra sin capa de texto, y es
el primer contraste colombiano del plan de la beca. Tesseract, una vez instalado
el idioma español que faltaba, dio 3,1 % de fragmentación y 0 % de fusión sobre
tres páginas — mejor que la línea base de *Estampa* (6,8 %) por su ruta buena.

La pregunta que responde este script: ¿aporta CHURRO lo suficiente como para
justificar sus 7,5 GB y sus ~3 min/página frente a los ~35 s/página de Tesseract?

Se comparan las MISMAS páginas (6 y 11, las que tienen cuerpo de texto) con las
MISMAS métricas, para que la comparación sea justa.

Advertencia metodológica que hay que mantener a la vista: fragmentación baja no
es lo mismo que OCR correcto. Estas métricas dicen si los tokens están bien
FORMADOS, no si dicen lo que dice la página. Para afirmar exactitud hace falta
una transcripción de referencia y reportar CER — que es lo que el plan promete y
lo que todavía no existe para esta publicación.
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

RAIZ = r"I:\Mi unidad\00_Programas y macros\Bashkar Station\bashkar_station"
sys.path.insert(0, RAIZ)

IMGS = Path(r"C:\build_rf\generalizacion\tesseract_grafico\img")
SALIDA = Path(r"C:\build_rf\generalizacion\churro_grafico")
PAGINAS = ["p0006"]

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
        return {"tokens": 0, "fus": 0.0, "frag": 0.0, "largo": 0.0}
    return {
        "tokens": n,
        "fus": 100 * sum(1 for t in tokens if len(t) > 16) / n,
        "frag": 100 * sum(1 for t in tokens
                          if len(t) <= 2 and t.lower() not in CORTAS_OK) / n,
        "largo": sum(len(t) for t in tokens) / n,
    }


def main() -> None:
    from core import ocr_churro

    if not ocr_churro.esta_descargado():
        sys.exit("El modelo CHURRO no esta completo en cache.")

    SALIDA.mkdir(parents=True, exist_ok=True)
    print("Cargando CHURRO-3B (7,5 GB) en memoria...", flush=True)
    t0 = time.time()

    print(f"{'PAGINA':10s} {'SEG':>7} {'TOKENS':>7} {'FUSION':>8} {'FRAG':>7} "
          f"{'LARGO':>6}", flush=True)
    print("-" * 52, flush=True)

    textos = []
    for nombre in PAGINAS:
        img = IMGS / f"{nombre}.png"
        if not img.exists():
            print(f"{nombre:10s}  falta la imagen {img}", flush=True)
            continue
        t = time.time()
        try:
            texto = ocr_churro.ocr_pagina(img)
        except Exception as e:
            print(f"{nombre:10s}  ERROR: {type(e).__name__}: {str(e)[:50]}",
                  flush=True)
            continue
        if isinstance(texto, tuple):
            texto = texto[0]
        dt = time.time() - t
        m = medir(str(texto))
        textos.append(str(texto))
        print(f"{nombre:10s} {dt:>7.1f} {m['tokens']:>7} {m['fus']:>7.2f}% "
              f"{m['frag']:>6.1f}% {m['largo']:>6.2f}", flush=True)
        (SALIDA / f"{nombre}.txt").write_text(str(texto), encoding="utf-8")

    if not textos:
        print("Sin resultados.", flush=True)
        return

    total = medir("\n".join(textos))
    print(flush=True)
    print(f"CHURRO agregado: {total['tokens']} tokens · fusion {total['fus']:.2f}% "
          f"· fragmento {total['frag']:.1f}% · largo {total['largo']:.2f}", flush=True)
    print("Tesseract (mismas paginas): fusion 0,00% · fragmento ~3,0% · largo ~4,6",
          flush=True)
    print(f"Tiempo total CHURRO: {time.time()-t0:.0f}s "
          f"(Tesseract: ~75s las dos paginas)", flush=True)
    print(flush=True)
    print("Muestra:", flush=True)
    print("-" * 60, flush=True)
    print("\n".join(textos)[:700], flush=True)


if __name__ == "__main__":
    main()
