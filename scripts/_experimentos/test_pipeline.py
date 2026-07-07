"""
test_pipeline.py — Prueba standalone del pipeline de Bashkar Station
=====================================================================
Procesa un PDF del corpus y reporta resultados de:
  1. Extracción de texto (digital o OCR)
  2. Normalización OCR
  3. Segmentación de artículos
  4. Análisis visual de elementos gráficos (si hay imágenes)

Uso:
    cd bashkar_station
    python test_pipeline.py

El PDF de prueba está fijo en el corpus de investigación.
Los resultados se imprimen en consola y se guardan en:
    ~/Documents/BashkarStation/test_output/
"""

import sys
from pathlib import Path

# Agregar directorio raíz al path para poder importar core/
sys.path.insert(0, str(Path(__file__).parent))

PDF_PRUEBA = Path(r"I:\Mi unidad\15_Becas y premios\24-2025-2\Beca mincultura 25\corpus de investigación\rev_estampa_ene_1939.pdf")
SALIDA_DIR = Path.home() / "Documents" / "BashkarStation" / "test_output"


def sep(titulo: str, ancho: int = 65):
    print("\n" + "=" * ancho)
    print(f"  {titulo}")
    print("=" * ancho)


def sub(titulo: str):
    print(f"\n-- {titulo} " + "-" * max(0, 50 - len(titulo)))


def main():
    SALIDA_DIR.mkdir(parents=True, exist_ok=True)

    sep("BASHKAR STATION - TEST PIPELINE v10.2")
    print(f"  PDF: {PDF_PRUEBA.name}")
    print(f"  Salida: {SALIDA_DIR}")

    if not PDF_PRUEBA.exists():
        print(f"\n[ERROR] No se encontró el PDF: {PDF_PRUEBA}")
        sys.exit(1)

    # ── 1. DETECCIÓN DE MODO ─────────────────────────────────────────────────
    sep("1. DETECCIÓN DE MODO DEL PDF")
    from core.text_extractor import detectar_modo
    modo = detectar_modo(PDF_PRUEBA)
    print(f"  Modo detectado: {modo}")

    # ── 2. EXTRACCIÓN DE TEXTO ───────────────────────────────────────────────
    sep("2. EXTRACCIÓN DE TEXTO")
    txt_dir = SALIDA_DIR / "textos"
    txt_dir.mkdir(exist_ok=True)

    def prog(i, n): print(f"  Página {i+1}/{n}...", end="\r")

    if modo == "paper_capture":
        from core.text_extractor import extraer_pdf_paper_capture
        print("  [INFO] Adobe Acrobat Paper Capture: reconstruyendo orden de lectura...")
        filas = extraer_pdf_paper_capture(PDF_PRUEBA, txt_dir, callback_pagina=prog)
        print(f"\n  Reconstruccion posicional completada.")
    elif modo == "digital":
        from core.text_extractor import extraer_pdf_digital
        filas = extraer_pdf_digital(PDF_PRUEBA, txt_dir, callback_pagina=prog)
    else:
        print(f"  [INFO] Modo '{modo}': usando reconstructor posicional como fallback")
        # Para PDFs escaneados con OCR embebido, intentar alto_reconstructor
        try:
            from core.text_extractor import extraer_pdf_paper_capture
            filas = extraer_pdf_paper_capture(PDF_PRUEBA, txt_dir, callback_pagina=prog)
            print(f"\n  Reconstruccion posicional completada.")
        except Exception as e:
            print(f"\n  [WARN] Fallback PyMuPDF directo: {e}")
            import fitz
            doc = fitz.open(str(PDF_PRUEBA))
            filas = []
            for i in range(doc.page_count):
                txt = doc[i].get_text()
                txt_path = txt_dir / f"p{i+1:04d}.txt"
                txt_path.write_text(txt, encoding="utf-8")
                filas.append({"pagina": f"p{i+1:04d}", "palabras": len(txt.split())})
                print(f"  Página {i+1}/{doc.page_count}...", end="\r")
            doc.close()

    print(f"\n  Páginas extraídas: {len(filas)}")
    total_palabras = sum(f.get("palabras", 0) for f in filas)
    print(f"  Total palabras (sin normalizar): {total_palabras:,}")

    # ── 3. NORMALIZACIÓN OCR ─────────────────────────────────────────────────
    sep("3. NORMALIZACIÓN OCR")
    from core.ocr_normalizer import normalizar_texto_ocr

    stats_norm = {"chars_cambiados": 0, "guiones_unidos": 0, "paginas": 0}
    muestra_antes = muestra_despues = ""

    archivos_txt = sorted(txt_dir.glob("*.txt"))
    for i, tp in enumerate(archivos_txt):
        original = tp.read_text("utf-8", errors="replace")
        normalizado = normalizar_texto_ocr(original)

        # Guardar normalizado (sobreescribir)
        tp.write_text(normalizado, encoding="utf-8")

        # Estadísticas
        ch = sum(1 for a, b in zip(original, normalizado) if a != b)
        stats_norm["chars_cambiados"] += ch
        stats_norm["paginas"] += 1

        # Guardar muestra de la primera página
        if i == 0 and original.strip():
            muestra_antes    = original[:500]
            muestra_despues  = normalizado[:500]

    print(f"  Páginas normalizadas: {stats_norm['paginas']}")
    print(f"  Caracteres corregidos (total): {stats_norm['chars_cambiados']:,}")

    if muestra_antes:
        sub("Muestra página 1 — ANTES de normalizar")
        print(muestra_antes[:300])
        sub("Muestra página 1 — DESPUÉS de normalizar")
        print(muestra_despues[:300])

    # ── 4. SEGMENTACIÓN DE ARTÍCULOS ─────────────────────────────────────────
    sep("4. SEGMENTACIÓN DE ARTÍCULOS")
    from core.article_segmenter import segmentar_numero_pdf, segmentar_texto_ocr

    # Intentar con PDF primero
    articulos = []
    try:
        articulos = segmentar_numero_pdf(PDF_PRUEBA)
        fuente_seg = "PDF digital (PyMuPDF)"
    except Exception as e:
        fuente_seg = f"Error PDF: {e}"

    # Fallback a OCR si no hay resultados
    if not articulos:
        fuente_seg = "textos OCR"
        for tp in archivos_txt:
            texto = tp.read_text("utf-8", errors="replace")
            arts  = segmentar_texto_ocr(texto, tp.stem)
            articulos.extend(arts)

    print(f"  Fuente: {fuente_seg}")
    print(f"  Artículos/secciones detectados: {len(articulos)}")

    if articulos:
        # Estadísticas de secciones
        from collections import Counter
        secciones_cnt = Counter(a.get("seccion", "?") for a in articulos)
        tipos_pagina  = Counter(a.get("tipo_pagina", "?") for a in articulos)
        autores       = [a["autor"] for a in articulos if a["autor"] != "Anónimo / Sin atribuir"]

        sub("Distribución por sección")
        for sec, n in secciones_cnt.most_common():
            print(f"  {sec:<25} {n:>3} artículo(s)")

        sub("Tipos de página detectados")
        for tp_pag, n in tipos_pagina.most_common():
            print(f"  {tp_pag:<25} {n:>3}")

        sub("Autores identificados")
        if autores:
            for a in sorted(set(autores)):
                print(f"  · {a}")
        else:
            print("  (ninguno identificado)")

        sub("Muestra — primeros 3 artículos")
        for art in articulos[:3]:
            print(f"\n  [{art.get('seccion','?')}] {art['titulo']}")
            print(f"  Autor: {art['autor']} (conf: {art['confianza_autor']})")
            print(f"  Página: {art.get('pagina','?')}  |  Palabras: {art['palabras']}")
            print(f"  Texto (primeras 150 chars): {art['texto'][:150]}...")

        # Guardar resultados
        import json
        salida_json = SALIDA_DIR / "articulos_segmentados.json"
        with open(salida_json, "w", encoding="utf-8") as f:
            # Guardar versión resumida (sin texto completo para no inflar)
            resumen = [{k: v for k, v in a.items() if k != "texto"} for a in articulos]
            json.dump(resumen, f, ensure_ascii=False, indent=2)
        print(f"\n  JSON guardado: {salida_json}")

    # ── 5. ANÁLISIS VISUAL (tipografía desde PDF) ────────────────────────────
    sep("5. ANÁLISIS VISUAL / TIPOGRÁFICO")
    try:
        from core.visual_analyzer import analizar_tipografia_numero
        tip = analizar_tipografia_numero(PDF_PRUEBA)
        if tip:
            print(f"  Páginas analizadas: {tip.get('n_paginas', 0)}")
            print(f"  Fuente principal: {tip.get('fuente_principal', 'N/D')}")
            print(f"  Clasificación: {tip.get('clasificacion_fuente', 'N/D')}")
            print(f"  Número de fuentes distintas: {tip.get('n_fuentes', 0)}")
            print(f"  Tamaño cuerpo promedio: {tip.get('tam_cuerpo_medio', 0)} pt")
            print(f"  Tamaño título promedio: {tip.get('tam_titulo_medio', 0)} pt")
            print(f"  Columnas (moda): {tip.get('columnas_moda', 1)}")
            print(f"  % Negrita: {tip.get('negrita_pct', 0)}")
            print(f"  Imágenes embebidas detectadas: {tip.get('imagenes_total', 0)}")

            sub("Fuentes detectadas")
            for f in tip.get("fuentes_resumen", [])[:5]:
                print(f"  · {f['fuente']:<30} {f['clasificacion']:<20} {f['chars_total']:>6} chars")
        else:
            print("  (no se pudo analizar tipografía)")
    except Exception as e:
        print(f"  [ERROR tipografía] {e}")

    # ── 5b. CORRECTOR ORTOGRÁFICO ────────────────────────────────────────────
    sep("5b. VERIFICACIÓN CORRECTOR ORTOGRÁFICO")
    try:
        from core.spell_corrector import verificar_instalacion
        v = verificar_instalacion()
        print(f"  spylls instalado:    {'SI' if v['spylls_disponible'] else 'NO'}")
        print(f"  Diccionario es_ES:   {'SI' if v['diccionario_es'] else 'NO'}")
        print(f"  Ruta:                {v['ruta_diccionario'] or 'N/D'}")
        if v['spylls_disponible'] and v['diccionario_es']:
            from core.spell_corrector import SpellCorrector
            sc = SpellCorrector()
            sc._cargar_diccionario()
            muestra_spell = "La sema11a pasada el Gober11ador d1jo que la industrio nacional"
            corregida = sc.corregir_texto(muestra_spell)
            print(f"\n  Prueba rapida:")
            print(f"    Entrada:  {muestra_spell}")
            print(f"    Salida:   {corregida}")
        else:
            print("  [WARN] Corrector no disponible — instalar: pip install spylls")
    except Exception as e:
        print(f"  [ERROR] {e}")

    # ── 6. DIAGNÓSTICO DE INCONSISTENCIAS ───────────────────────────────────
    sep("6. DIAGNÓSTICO DE POSIBLES INCONSISTENCIAS")

    inconsistencias = []

    if total_palabras < 500:
        inconsistencias.append("[!] Muy pocas palabras extraídas — posible PDF escaneado sin texto")

    if len(articulos) == 0:
        inconsistencias.append("[!] Segmentación produjo 0 artículos — revisar umbrales")
    elif len(articulos) == 1:
        inconsistencias.append("[!] Solo 1 artículo detectado — probable falla en detección de títulos")

    if articulos:
        sin_titulo = sum(1 for a in articulos if a["titulo"] == "Sin título")
        pct_sin_titulo = sin_titulo / len(articulos) * 100
        if pct_sin_titulo > 60:
            inconsistencias.append(
                f"[!] {pct_sin_titulo:.0f}% de artículos sin título — "
                "OCR de baja calidad o umbral muy alto")

        palabras_lista = [a["palabras"] for a in articulos]
        if palabras_lista:
            max_pal = max(palabras_lista)
            if max_pal > 5000:
                inconsistencias.append(
                    f"[!] Artículo con {max_pal} palabras — "
                    "probable artículo que no se dividió bien")

        anonimos = sum(1 for a in articulos if a["autor"] == "Anónimo / Sin atribuir")
        pct_anon = anonimos / len(articulos) * 100
        print(f"  Artículos anónimos: {anonimos}/{len(articulos)} ({pct_anon:.0f}%)")
        print(f"  (Normal para prensa 1930-50: 60-80% anónimos)")

    if inconsistencias:
        for inc in inconsistencias:
            print(f"\n  {inc}")
    else:
        print("\n  [OK] No se detectaron inconsistencias graves.")

    sep("RESUMEN FINAL")
    print(f"  PDF procesado: {PDF_PRUEBA.name}")
    print(f"  Páginas: {len(filas)}")
    print(f"  Palabras extraídas: {total_palabras:,}")
    print(f"  Artículos segmentados: {len(articulos)}")
    print(f"  Salida guardada en: {SALIDA_DIR}")
    print()


if __name__ == "__main__":
    main()
