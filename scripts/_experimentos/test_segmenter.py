"""Script de prueba para el nuevo segmentador."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path
from core.article_segmenter import segmentar_numero, _procesar_pagina_ocr, _limpiar_dict

# Ruta al corpus Estampa
ESTAMPA_ROOT = Path(r"C:\Users\Lenovo\OneDrive - ucatolica.edu.co\Apps\OneDrive - ucatolica.edu.co\Documents\Gulla\Investigaciones ñoñas\Revista Estampa")
OCR_DIR = ESTAMPA_ROOT / "03_ocr"
NOMBRE = "rev_estampa_ene_1939"

def test_pagina_individual():
    """Prueba procesamiento de páginas individuales."""
    carpeta = OCR_DIR / NOMBRE
    paginas_muestra = ["p0008", "p0010", "p0012", "p0015", "p0020", "p0030"]

    print("=== PRUEBA PÁGINAS INDIVIDUALES ===")
    for p in paginas_muestra:
        tf = carpeta / f"{p}.txt"
        if not tf.exists():
            continue
        texto = tf.read_text("utf-8", errors="replace")
        resultado = _procesar_pagina_ocr(texto, p)
        if resultado:
            r = _limpiar_dict(resultado)
            print(f"\n[{p}] {r['palabras']} palabras | tipo={r['tipo_pagina'][:20]} | seccion={r['seccion'][:12]}")
            print(f"  Título: {r['titulo'][:60]}")
            print(f"  Autor:  {r['autor']}")
        else:
            print(f"\n[{p}] -> DESCARTADO (sin contenido)")

def test_numero_completo():
    """Prueba segmentación del número completo."""
    print("\n\n=== PRUEBA NÚMERO COMPLETO: rev_estampa_ene_1939 ===")
    arts = segmentar_numero(OCR_DIR, NOMBRE)
    print(f"Total artículos/unidades: {len(arts)}")
    print()
    for a in arts:
        p = a["pagina"]
        w = a["palabras"]
        tp = a["tipo_pagina"][:18]
        sc = a["seccion"][:12]
        au = a["autor"][:28]
        ti = a["titulo"][:55]
        print(f"[{p:<20}] {w:4d}p | {tp:<18} | {sc:<12} | {au:<28} | {ti}")

def test_stats():
    """Estadísticas sobre la segmentación."""
    arts = segmentar_numero(OCR_DIR, NOMBRE)
    print(f"\n\n=== ESTADÍSTICAS ===")
    print(f"Total unidades: {len(arts)}")
    tipos = {}
    for a in arts:
        t = a["tipo_pagina"]
        tipos[t] = tipos.get(t, 0) + 1
    print("Por tipo:")
    for t, n in sorted(tipos.items(), key=lambda x: -x[1]):
        print(f"  {t}: {n}")

    palabras = [a["palabras"] for a in arts]
    if palabras:
        import statistics
        print(f"\nPalabras por artículo:")
        print(f"  Min: {min(palabras)}")
        print(f"  Max: {max(palabras)}")
        print(f"  Mediana: {statistics.median(palabras):.0f}")
        print(f"  Total corpus: {sum(palabras)}")

if __name__ == "__main__":
    test_pagina_individual()
    test_numero_completo()
    test_stats()
