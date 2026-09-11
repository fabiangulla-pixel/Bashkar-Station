"""Resume `elgrafico_resultados.jsonl` en la tabla que va al informe de la beca.

Lee el checkpoint que deja `medir_elgrafico_completo.py` y produce:
  · las cifras agregadas de la colección,
  · la evolución por década (¿empeora el papel con los años?),
  · los números que el sistema marcaría para revisión,
  · la comparación con la línea base de *Estampa*.

No mide nada: solo lee. Se puede correr con la medición a medias.
"""

from __future__ import annotations

import json
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

SALIDA = Path(__file__).parent / "elgrafico_resultados.jsonl"

# Línea base: Estampa 1939 por su ruta buena, medido el 10-sep-2026 con el
# mismo módulo (`validar_calidad_ocr.py`). Es el corpus sobre el que está hecho
# todo el análisis publicado del proyecto.
ESTAMPA_FRAG = 4.7
ESTAMPA_FUSION = 0.16


def cargar() -> tuple[list[dict], list[dict]]:
    if not SALIDA.exists():
        return [], []
    filas = []
    for linea in SALIDA.read_text(encoding="utf-8").splitlines():
        try:
            filas.append(json.loads(linea))
        except Exception:
            continue
    return ([f for f in filas if not f.get("error")],
            [f for f in filas if f.get("error")])


def _anio(nombre: str) -> int | None:
    """Año desde `ps20_elgrafico_abr_1911.pdf`."""
    for trozo in nombre.replace(".pdf", "").split("_"):
        if len(trozo) == 4 and trozo.isdigit():
            n = int(trozo)
            if 1900 <= n <= 1935:
                return n
    return None


def main() -> None:
    ok, err = cargar()
    if not ok:
        print("Sin resultados todavía.")
        return

    print("=" * 72)
    print(f"EL GRÁFICO — Tesseract español · {len(ok)} números medidos"
          + (f" · {len(err)} con error" if err else ""))
    print("=" * 72)

    confs = [f["confianza"] for f in ok if f.get("confianza")]
    frags = [f["pct_fragmentacion"] for f in ok]
    fus = [f["pct_fusion"] for f in ok]
    paginas = sum(f.get("n_paginas", 0) for f in ok)
    tokens = sum(f.get("tokens", 0) for f in ok)

    print(f"\nColección: {paginas:,} páginas · {tokens:,} tokens medidos")
    print(f"  Confianza Tesseract  {st.mean(confs):6.2f} %  "
          f"(mediana {st.median(confs):.2f}, "
          f"rango {min(confs):.1f}–{max(confs):.1f})")
    print(f"  Fragmentación        {st.mean(frags):6.2f} %  "
          f"(mediana {st.median(frags):.2f}, "
          f"rango {min(frags):.1f}–{max(frags):.1f})  "
          f"· Estampa {ESTAMPA_FRAG} %")
    print(f"  Fusión               {st.mean(fus):6.3f} %  "
          f"(máx {max(fus):.2f})  · Estampa {ESTAMPA_FUSION} %")

    print("\nVeredicto de abstención:")
    cuenta = Counter(f["veredicto"] for f in ok)
    for v in ("utilizable", "revisar", "no_utilizable"):
        n = cuenta.get(v, 0)
        print(f"  {v:15s} {n:>3} números ({100*n/len(ok):5.1f} %)")

    por_decada: dict[str, list[float]] = defaultdict(list)
    for f in ok:
        a = _anio(f["archivo"])
        if a:
            por_decada[f"{a//10*10}s"].append(f["pct_fragmentacion"])
    if por_decada:
        print("\nFragmentación por década (¿se degrada con los años?):")
        for dec in sorted(por_decada):
            vals = por_decada[dec]
            print(f"  {dec}  {len(vals):>3} números · media {st.mean(vals):5.2f} %")

    dudosos = [f for f in ok if f["veredicto"] != "utilizable"]
    if dudosos:
        print(f"\nNúmeros que el sistema marca para revisión ({len(dudosos)}):")
        for f in sorted(dudosos, key=lambda x: -x["pct_fragmentacion"]):
            print(f"  {f['archivo'][:40]:40s} frag {f['pct_fragmentacion']:5.2f} % "
                  f"· conf {f.get('confianza', 0):.1f} % · {f['veredicto']}")

    if err:
        print(f"\nNúmeros con error ({len(err)}):")
        for f in err:
            print(f"  {f['archivo'][:40]:40s} {f['error'][:60]}")

    peor = max(ok, key=lambda f: f["pct_fragmentacion"])
    mejor = min(ok, key=lambda f: f["pct_fragmentacion"])
    print(f"\nMejor: {mejor['archivo']} ({mejor['pct_fragmentacion']:.2f} %)")
    print(f"Peor:  {peor['archivo']} ({peor['pct_fragmentacion']:.2f} %)")


if __name__ == "__main__":
    main()
