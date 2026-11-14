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

VISION_SALIDA = _ROOT / "vision_ocr" / "salida"

# Procedencia del texto: lote de scripts/ocr_vision_lote.py (agosto de 2026,
# workflow ocr_vision_lote.yml) con su modelo por defecto. No se registró el
# modelo página por página; se declara el del lote.
METODO_OCR = "claude_vision"
MODELO_OCR = "claude-sonnet-5"

PERIODO = "enero–mayo de 1939"

# Créditos que declaran las exportaciones (core/metadatos_exportacion).
# Fórmula institucional del documento E-RIHS del 14-oct-2026: el ICyC fue
# institución mentora de la beca; no hay afiliación.
EXPORTACION_ESTAMPA = {
    "lugar": "Bogotá",
    "creditos": [
        {"rol": "Financiación",
         "nombre": "Beca a Nuevos Investigadores en Estudios Editoriales, Ministerio "
                   "de las Culturas, las Artes y los Saberes de Colombia"},
        {"rol": "Institución mentora de la beca (sin afiliación)",
         "nombre": "Instituto Caro y Cuervo"},
        {"rol": "Digitalización de la fuente", "nombre": "Biblioteca Nacional de Colombia"},
    ],
    # Redacción provisional (hito B3 de PLAN_MVP.md); se ajusta a los términos
    # exactos de la autorización en el hito E2.
    "disponibilidad": "Las imágenes y los textos de Estampa se publican con "
                      "autorización de la Biblioteca Nacional de Colombia.",
}


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


def escribir_metadatos_ocr(datos_dir: Path) -> int:
    """``04_analisis/ocr_metadatos.csv`` con el método real de cada página.

    Sin él, la app reconstruye los metadatos marcando todo como «conversor».
    """
    import csv
    filas = []
    for num_dir in sorted((datos_dir / "03_ocr").iterdir()):
        if not num_dir.is_dir():
            continue
        for txt in sorted(num_dir.glob("*.txt")):
            palabras = len(txt.read_text(encoding="utf-8", errors="replace").split())
            filas.append({"numero": num_dir.name, "pagina": txt.stem,
                          "txt_path": str(txt), "palabras": palabras, "confianza": "",
                          "revision": False, "metodo": METODO_OCR})
    ad = datos_dir / "04_analisis"
    ad.mkdir(parents=True, exist_ok=True)
    with open(ad / "ocr_metadatos.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]) if filas else ["numero"])
        w.writeheader()
        w.writerows(filas)
    return len(filas)


def escribir_bashkar(ruta_bashkar: Path, datos_dir: Path, nombre: str,
                     pdf_dir: Path | None = None) -> None:
    """Escribe un .bashkar mínimo pero válido para core.project_manager.
    cargar_proyecto() — mismo esquema, sin necesitar instanciar Estado.

    ``archivos_sel`` queda vacío a propósito: si la app encuentra el PDF de un
    número, segmenta desde su capa de texto de la BNC (Paper Capture, peor
    que Vision) en vez de desde estas transcripciones. ``pdf_dir`` solo se
    anota como referencia de dónde están las imágenes.
    """
    from core.project_manager import VERSION
    ahora = datetime.now().isoformat()
    contenido = {
        "version": VERSION,
        "nombre": nombre,
        "publicacion": "Estampa",
        "periodo": PERIODO,
        "creado": ahora,
        "modificado": ahora,
        "config": {
            "publicacion": "Estampa",
            "periodo": PERIODO,
            "pdf_dir": str(pdf_dir) if pdf_dir else "",
            "out_dir": str(datos_dir),
            "input_tipo": "pdf",
            "archivos_sel": [],
            "max_ia": 15,
            "campos_semillas": {},
            "exportacion": EXPORTACION_ESTAMPA,
        },
        "progreso": {"ocr": True, "seg": False, "anal": False, "vis": False, "comp": False},
        "resultados": {},
        # El OCR se hizo con IA en la nube: que las exportaciones lo declaren.
        "historial_ia": [{"proveedor": "anthropic", "modelo": MODELO_OCR, "etapa": "ocr",
                          "nota": "Transcripción de las 792 páginas con "
                                  "scripts/ocr_vision_lote.py (agosto de 2026)."}],
        "db": str(ruta_bashkar.with_suffix(".db")),
    }
    ruta_bashkar.write_text(json.dumps(contenido, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nombre", default="Estampa 1939 (Vision OCR completo)")
    parser.add_argument("--proyectos-dir", type=Path,
                         default=Path.home() / "Documents" / "BashkarStation" / "proyectos")
    parser.add_argument("--forzar", action="store_true", help="Sobrescribir .txt ya copiados")
    parser.add_argument("--pdf-dir", type=Path, default=None,
                        help="Carpeta con los PDF originales de los 5 números (referencia)")
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

    n_meta = escribir_metadatos_ocr(datos_dir)
    escribir_bashkar(ruta_bashkar, datos_dir, args.nombre, args.pdf_dir)
    print(f"Metadatos de OCR: {n_meta} páginas ({METODO_OCR})")

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
