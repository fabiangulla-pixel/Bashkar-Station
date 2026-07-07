"""
core/methods_reporter.py — Generador automático de sección de Metodología.

Produce un archivo METHODS.md (o .txt) con:
- Versiones de software usadas (Python, Bashkar, Tesseract, spaCy, PyMuPDF…)
- Parámetros del pipeline aplicados (DPI, idioma, modelo NER, umbral…)
- Estadísticas del corpus procesado
- Decisiones metodológicas registradas

El documento es apto para incluir directamente como sección de Metodología
en un paper de humanidades digitales con mínima edición.
"""

from __future__ import annotations

import sys
import subprocess
from datetime import datetime
from pathlib import Path


def _version_paquete(nombre: str) -> str:
    """Retorna la versión instalada de un paquete pip."""
    try:
        import importlib.metadata
        return importlib.metadata.version(nombre)
    except Exception:
        try:
            mod = __import__(nombre.replace("-", "_"))
            return getattr(mod, "__version__", "instalado")
        except Exception:
            return "no instalado"


def _version_tesseract(tesseract_path: str = "tesseract") -> str:
    """Retorna la versión de Tesseract OCR."""
    try:
        r = subprocess.run(
            [tesseract_path, "--version"],
            capture_output=True, text=True, timeout=5)
        primera = (r.stdout or r.stderr or "").strip().splitlines()[0]
        return primera
    except Exception:
        return "no detectado"


def generar_methods_md(
    config: dict,
    estadisticas: dict,
    ruta: Path,
    idioma_doc: str = "es",
) -> Path:
    """
    Genera el archivo METHODS.md con sección de metodología completa.

    config: dict con los parámetros del proyecto (ST serializado)
    estadisticas: dict con métricas del corpus procesado
    ruta: destino del archivo
    """
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)

    fecha = datetime.now().strftime("%d de %B de %Y")
    pub   = config.get("publicacion", "")
    per   = config.get("periodo", "")
    inv   = config.get("investigador", "")
    inst  = config.get("institucion", "")

    # ── Versiones de software ─────────────────────────────────────────────────
    py_ver    = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    bashkar   = config.get("bashkar_version", "11.x")
    tes_path  = config.get("tesseract_path", "tesseract")
    tes_ver   = _version_tesseract(tes_path)

    paquetes = [
        ("pymupdf",            "PyMuPDF"),
        ("pytesseract",        "pytesseract"),
        ("spacy",              "spaCy"),
        ("transformers",       "Transformers"),
        ("sentence-transformers", "sentence-transformers"),
        ("scikit-learn",       "scikit-learn"),
        ("pandas",             "pandas"),
        ("networkx",           "networkx"),
        ("faiss-cpu",          "FAISS"),
    ]
    versiones_paq = [(etiq, _version_paquete(pkg)) for pkg, etiq in paquetes]

    # ── Parámetros pipeline ───────────────────────────────────────────────────
    dpi        = config.get("dpi", "150")
    lang_ocr   = config.get("lang", "spa")
    motor_ocr  = config.get("motor_ocr", "Tesseract")
    lematizar  = config.get("lematizar", True)
    modelos_ia = config.get("modelos_etapa", {})
    n_arch     = len(config.get("archivos_sel", []))

    # ── Estadísticas corpus ───────────────────────────────────────────────────
    n_pags   = estadisticas.get("n_paginas", 0)
    n_words  = estadisticas.get("n_palabras", 0)
    n_arts   = estadisticas.get("n_articulos", 0)
    n_ents   = estadisticas.get("n_entidades", 0)
    conf_ocr = estadisticas.get("confianza_ocr_media", None)

    # ── Construir documento ───────────────────────────────────────────────────
    lineas = [
        f"# Metodología computacional",
        f"",
        f"**Proyecto:** {pub}  ",
        f"**Período:** {per}  ",
        f"**Investigador/a:** {inv}  ",
        f"**Institución:** {inst}  ",
        f"**Fecha de procesamiento:** {fecha}",
        f"",
        f"---",
        f"",
        f"## 1. Software y versiones",
        f"",
        f"El análisis computacional fue realizado con **Bashkar Station v{bashkar}**,",
        f"una aplicación de escritorio desarrollada específicamente para el análisis",
        f"de publicaciones periódicas históricas en español.",
        f"",
        f"| Software | Versión |",
        f"|---|---|",
        f"| Python | {py_ver} |",
        f"| Bashkar Station | {bashkar} |",
        f"| Tesseract OCR | {tes_ver} |",
    ]
    for etiq, ver in versiones_paq:
        lineas.append(f"| {etiq} | {ver} |")

    lineas += [
        f"",
        f"---",
        f"",
        f"## 2. Corpus y preprocesamiento",
        f"",
        f"- **Archivos procesados:** {n_arch} número(s) de la publicación",
        f"- **Páginas analizadas:** {n_pags:,}",
        f"- **Palabras extraídas:** {n_words:,}",
        f"- **Unidades segmentadas:** {n_arts} artículos",
    ]

    if conf_ocr is not None:
        lineas.append(f"- **Confianza OCR media:** {conf_ocr:.1f}%")

    lineas += [
        f"",
        f"### 2.1 Extracción de texto",
        f"",
        f"El texto fue extraído mediante **{motor_ocr}** con los siguientes parámetros:",
        f"",
        f"- Resolución de rasterización: **{dpi} DPI**",
        f"- Idioma del modelo OCR: **{lang_ocr}**",
        f"- Modo de segmentación de página (PSM): detección automática de layout",
        f"",
        f"Los PDFs de la colección BNC están digitalizados con Adobe Acrobat Paper Capture,",
        f"que embebe el reconocimiento óptico en un formato posicional (fuente HiddenHorzOCR).",
        f"Bashkar Station aplica un reconstructor de orden de lectura basado en coordenadas",
        f"X/Y para recuperar el flujo correcto de columnas múltiples.",
        f"",
        f"### 2.2 Normalización post-OCR",
        f"",
        f"La normalización preserva la ortografía histórica del español de los años 1930",
        f"(arcaísmos, formas verbales, diacríticos no estándar) y corrige únicamente errores",
        f"de digitalización: caracteres confundidos por el OCR, palabras partidas por guión",
        f"de columna, ruido tipográfico.",
        f"",
        f"- **Lematización en análisis léxico:** {'activada' if lematizar else 'desactivada (formas originales)'}",
    ]

    if not lematizar:
        lineas.append(
            "  > La lematización fue desactivada para preservar la variación ortográfica "
            "histórica como dato lingüístico.")

    lineas += [
        f"",
        f"---",
        f"",
        f"## 3. Reconocimiento de entidades nombradas (NER)",
        f"",
        f"- **Entidades únicas identificadas:** {n_ents:,}",
        f"- **Categorías:** personas, lugares, organizaciones, obras/publicaciones,",
        f"  eventos históricos, cargos/títulos",
        f"- **Pipeline:** spaCy `es_core_news_sm` (capa 1) + refinamiento con",
        f"  `mrm8488/bert-spanish-cased-finetuned-ner` (capa 2, BERT local)",
    ]

    if modelos_ia.get("ner") and "ollama" not in modelos_ia["ner"].lower():
        lineas.append(f"- **Modelo IA para NER:** {modelos_ia['ner']}")

    lineas += [
        f"",
        f"---",
        f"",
        f"## 4. Análisis léxico y estadístico",
        f"",
        f"- Frecuencias de términos calculadas sobre el corpus completo.",
        f"- Collocates extraídos con ventana de 5 tokens y métrica PMI",
        f"  (Pointwise Mutual Information).",
        f"- Topic modeling mediante LDA (Latent Dirichlet Allocation) con scikit-learn.",
        f"",
        f"---",
        f"",
        f"## 5. Reproducibilidad",
        f"",
        f"Todos los parámetros y versiones de software registrados en este documento",
        f"permiten la reproducción del análisis. Los archivos generados incluyen:",
        f"",
        f"- `corpus.xml` — transcripciones en formato TEI P5",
        f"- `corpus.bib` — referencias bibliográficas en BibTeX",
        f"- `entidades.csv` — índice completo de entidades nombradas",
        f"- `bitacora.md` — notas y reflexiones del investigador durante el proceso",
        f"- `METHODS.md` — este documento",
        f"",
        f"---",
        f"",
        f"*Documento generado automáticamente por Bashkar Station v{bashkar}.*",
        f"*Revisa y complementa antes de incluir en publicación.*",
    ]

    contenido = "\n".join(lineas)
    ruta.write_text(contenido, encoding="utf-8")
    return ruta
