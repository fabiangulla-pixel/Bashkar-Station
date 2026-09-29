"""Benchmark OCR con línea base.

Uso:
    python scripts/benchmark_ocr_regresion.py evaluar  benchmark/estampa-1939
    python scripts/benchmark_ocr_regresion.py generar  benchmark/estampa-1939 --ruta zonas
    python scripts/benchmark_ocr_regresion.py base     benchmark/estampa-1939   # congela línea base
    python scripts/benchmark_ocr_regresion.py verificar benchmark/estampa-1939  # sale con 1 si empeora

Ver core/benchmark_regresion.py y benchmark/README.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import benchmark_regresion as BR  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("accion", choices=["evaluar", "generar", "base", "verificar"])
    ap.add_argument("carpeta", type=Path)
    ap.add_argument("--tolerancia", type=float, default=BR.TOLERANCIA)
    ap.add_argument("--ruta", default="tesseract",
                    help="ruta de OCR para 'generar': tesseract, zonas, churro, pero")
    ap.add_argument("--json", action="store_true", help="imprimir el resultado completo")
    a = ap.parse_args(argv)
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")

    try:
        if a.accion == "generar":
            n = BR.generar_salidas(a.carpeta, a.ruta)
            print(f"{n} páginas procesadas con la ruta '{a.ruta}'")
            return 0
        res = BR.evaluar(a.carpeta)
    except BR.ReferenciaNoHumana as e:
        print(f"✗ {e}", file=sys.stderr)
        return 2
    except FileNotFoundError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 2

    print(json.dumps(res, ensure_ascii=False, indent=2) if a.json else BR.tabla_markdown(res))
    if a.accion == "base":
        print(f"\nLínea base: {BR.guardar_linea_base(a.carpeta, res)}")
    elif a.accion == "verificar":
        ruta_base = a.carpeta / BR.LINEA_BASE
        if not ruta_base.exists():
            print("✗ No hay línea base; créala con la acción 'base'.", file=sys.stderr)
            return 2
        base = json.loads(ruta_base.read_text(encoding="utf-8"))
        problemas = BR.comparar_con_base(res, base, a.tolerancia)
        if problemas:
            print("\n✗ REGRESIONES:\n  " + "\n  ".join(problemas))
            return 1
        print("\n✓ Sin regresiones respecto de la línea base.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
