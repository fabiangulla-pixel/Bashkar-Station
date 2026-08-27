#!/usr/bin/env python
"""scripts/importar_vision_ocr_a_proyecto.py — Convierte el texto transcrito
por scripts/ocr_vision_lote.py (vision_ocr/salida/<numero>/pXXXX.txt) en un
proyecto real de Bashkar Station: copia los .txt a la estructura
<datos_dir>/03_ocr/<numero>/ que la app espera, y escribe un .bashkar mínimo
válido — para que sea literal "abrir la app, seleccionar el proyecto,
trabajar" en vez de tener el mejor OCR guardado en una carpeta que la app
no sabe abrir.

No requiere tkinter ni el resto de la app (no importa app.py): escribe el
.bashkar directamente con el mismo esquema que core/project_manager.py
espera en cargar_proyecto(), sin necesitar instanciar el objeto Estado.

Uso:
    python scripts/importar_vision_ocr_a_proyecto.py
    python scripts/importar_vision_ocr_a_proyecto.py --nombre "Otro nombre" --forzar
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

NUMEROS = [
    "rev_estampa_ene_1939",
    "rev_estampa_feb_1939",
    "rev_estampa_mar_1939",
    "rev_estampa_abr_1939",
    "rev_estampa_may_1939",
]

PDF_DIR_ORIGEN = Path("D:/Bashkar/Corpus Estampa/sin")
VISION_SALIDA = _ROOT / "vision_ocr" / "salida"


def _copiar_ocr(salida_vision: Path, datos_dir: Path, *, forzar: bool) -> dict:
    """Copia cada <numero>/pXXXX.txt a <datos_dir>/03_ocr/<numero>/. Retorna
    {numero: n_paginas_copiadas}."""
    resumen = {}
    for numero in NUMEROS:
        origen = salida_vision / numero
        if not origen.is_dir():
            resumen[numero] = 0
            continue
        destino = datos_dir / "03_ocr" / numero
        destino.mkdir(parents=True, exist_ok=True)
        n = 0
        for txt in sorted(origen.glob("*.txt")):
            dest_txt = destino / txt.name
            if dest_txt.exists() and not forzar:
                continue
            shutil.copy2(txt, dest_txt)
            n += 1
        resumen[numero] = n
    return resumen


def _archivos_pdf_existentes() -> list[Path]:
    return [PDF_DIR_ORIGEN / f"{n}.pdf" for n in NUMEROS if (PDF_DIR_ORIGEN / f"{n}.pdf").exists()]


def escribir_bashkar(ruta_bashkar: Path, datos_dir: Path, nombre: str) -> None:
    """Escribe un .bashkar mínimo pero válido para core.project_manager.
    cargar_proyecto() — mismo esquema, sin necesitar instanciar Estado."""
    ahora = datetime.now().isoformat()
    contenido = {
        "version": "11",
        "nombre": nombre,
        "publicacion": "Estampa",
        "periodo": "1939 (enero-mayo)",
        "creado": ahora,
        "modificado": ahora,
        "config": {
            "publicacion": "Estampa",
            "periodo": "1939 (enero-mayo)",
            "pdf_dir": str(PDF_DIR_ORIGEN),
            "out_dir": str(datos_dir),
            "input_tipo": "pdf",
            "archivos_sel": [str(p) for p in _archivos_pdf_existentes()],
            "max_ia": 15,
            "campos_semillas": {},
        },
        "progreso": {"ocr": True, "seg": False, "anal": False, "vis": False, "comp": False},
        "resultados": {},
        "historial_ia": [],
        "db": str(ruta_bashkar.with_suffix(".db")),
    }
    ruta_bashkar.write_text(json.dumps(contenido, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nombre", default="Estampa 1939 (Vision OCR completo)")
    parser.add_argument("--proyectos-dir", type=Path,
                         default=Path.home() / "Documents" / "BashkarStation" / "proyectos")
    parser.add_argument("--forzar", action="store_true", help="Sobrescribir .txt ya copiados")
    args = parser.parse_args()

    if not VISION_SALIDA.is_dir():
        print(f"ERROR: no existe {VISION_SALIDA} — corre primero ocr_vision_lote.py "
              "(local o vía el workflow de GitHub) y trae los resultados con git pull.")
        return 1

    args.proyectos_dir.mkdir(parents=True, exist_ok=True)
    slug = "".join(c if c.isalnum() else "_" for c in args.nombre).strip("_")
    ruta_bashkar = args.proyectos_dir / f"{slug}.bashkar"
    datos_dir = args.proyectos_dir / slug

    resumen = _copiar_ocr(VISION_SALIDA, datos_dir, forzar=args.forzar)
    total = sum(resumen.values())
    if total == 0 and not args.forzar:
        print("0 páginas nuevas copiadas (¿ya se había importado? usa --forzar para repetir).")

    escribir_bashkar(ruta_bashkar, datos_dir, args.nombre)

    print(f"Proyecto escrito en: {ruta_bashkar}")
    print(f"Datos en: {datos_dir}")
    for numero, n in resumen.items():
        print(f"  {numero}: {n} páginas")
    print(f"Total: {total} páginas copiadas")
    print("\nAbre Bashkar Station y selecciona este proyecto desde 'Proyectos' —")
    print("el paso de OCR ya queda marcado como hecho; sigue con Normalizar/Segmentar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
