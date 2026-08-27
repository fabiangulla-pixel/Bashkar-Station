#!/usr/bin/env python
"""scripts/ocr_vision_lote.py — Transcripción por Vision LLM a escala de un
número completo de Estampa, para el pase de OCR de mejor calidad posible
sobre el corpus.

Reutiliza core.ocr_llm.ocr_con_vision (el mismo motor y prompt ya validados
en la app de escritorio, Ruta 2), no reimplementa el prompt. Al importar
solo core.ocr_llm/core.inference_provider/core.costos (ninguno de los tres
importa torch/transformers/spacy a nivel de módulo), este script corre en un
runner de CI liviano con `pip install anthropic pymupdf pillow` — nada de la
pila pesada de Bashkar.

Uso:
    python scripts/ocr_vision_lote.py --imagenes-dir vision_ocr/entrada/rev_estampa_ene_1939 \\
        --salida-dir vision_ocr/salida/rev_estampa_ene_1939 --dry-run

    python scripts/ocr_vision_lote.py --imagenes-dir vision_ocr/entrada/rev_estampa_ene_1939 \\
        --salida-dir vision_ocr/salida/rev_estampa_ene_1939 --concurrencia 6

Resumible: una página con .txt ya escrito en --salida-dir se salta (a menos
que --forzar). Costo real medido de verdad (usage del SDK), no solo
estimado — igual que el resto de Bashkar (core/costos.py).
"""
from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _paginas_pendientes(imagenes_dir: Path, salida_dir: Path, *, forzar: bool) -> list[Path]:
    pendientes = []
    for img in sorted(imagenes_dir.glob("*.jpg")):
        destino = salida_dir / f"{img.stem}.txt"
        if destino.exists() and not forzar:
            continue
        pendientes.append(img)
    return pendientes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--imagenes-dir", type=Path, required=True)
    parser.add_argument("--salida-dir", type=Path, required=True)
    parser.add_argument("--modelo", default="claude-sonnet-5")
    parser.add_argument("--concurrencia", type=int, default=6)
    parser.add_argument("--forzar", action="store_true")
    parser.add_argument("--limite", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    import os

    from core import costos, ocr_llm

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key and not args.dry_run:
        print("ERROR: falta ANTHROPIC_API_KEY en el entorno.")
        return 1

    pendientes = _paginas_pendientes(args.imagenes_dir, args.salida_dir, forzar=args.forzar)
    if args.limite:
        pendientes = pendientes[: args.limite]

    if not pendientes:
        print("No hay páginas pendientes de transcribir (usa --forzar para rehacer).")
        return 0

    if args.dry_run:
        est = costos.estimar_lote_ocr(len(pendientes), "claude", args.modelo, n_vision=len(pendientes))
        print(est.resumen())
        print("\nNada se gastó. Corre sin --dry-run para transcribir de verdad.")
        return 0

    args.salida_dir.mkdir(parents=True, exist_ok=True)
    ocr_llm.reset_usages()

    resultados: list[tuple[str, int]] = []  # (pagina_id, palabras)
    errores: list[str] = []
    inicio = time.monotonic()

    def _trabajar(img_path: Path) -> tuple[str, str]:
        texto = ocr_llm.ocr_con_vision(img_path, api_key, modelo=args.modelo, proveedor="claude")
        return img_path.stem, texto

    with ThreadPoolExecutor(max_workers=args.concurrencia) as pool:
        futuros = {pool.submit(_trabajar, img): img.stem for img in pendientes}
        for futuro in as_completed(futuros):
            pid = futuros[futuro]
            try:
                pagina_id, texto = futuro.result()
            except Exception as error:  # noqa: BLE001 — se reporta, no se detiene el lote
                errores.append(f"{pid}: {error}")
                print(f"  [ERROR] {pid}: {error}")
                continue
            if not texto.strip():
                errores.append(f"{pagina_id}: transcripción vacía (posible rechazo del modelo)")
                print(f"  [VACIO] {pagina_id}")
                continue
            (args.salida_dir / f"{pagina_id}.txt").write_text(texto, encoding="utf-8")
            resultados.append((pagina_id, len(texto.split())))
            print(f"  [OK] {pagina_id}: {len(texto.split())} palabras")

    duracion = time.monotonic() - inicio
    usos = ocr_llm.usages()
    costo_real = costos.costo_real_desde_usages("claude", args.modelo, usos)
    print(f"\n{len(resultados)}/{len(pendientes)} páginas transcritas en {duracion/60:.1f} min. "
          f"Costo real: ${costo_real.costo_usd:.4f} USD "
          f"({costo_real.tokens_totales:,} tokens).")
    if errores:
        print(f"{len(errores)} página(s) con error (reintentar con --forzar):")
        for e in errores:
            print(f"  - {e}")

    return 1 if errores and not resultados else 0


if __name__ == "__main__":
    sys.exit(main())
