"""core/ocr_engine.py — OCR inteligente: extrae texto directo si ya existe, aplica OCR si no."""

import gc
import re
import sys
from pathlib import Path

# Asegurar que el directorio raíz del proyecto esté en sys.path
# para que los imports "from core.X" funcionen en cualquier contexto
_MODULE_ROOT = Path(__file__).parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

EXTS_IMAGEN = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}
PALABRAS_MIN_PAGINA = 40   # umbral para considerar que una página ya tiene texto útil


# ── Utilidades de ruta ────────────────────────────────────────────────────────

def _get_poppler_path() -> str | None:
    """
    Carpeta bin de poppler para pdf2image, o None si basta con el PATH.

    Orden de prioridad, sin cambios respecto de las versiones Windows: primero
    poppler_path.txt —la ruta que fijó el usuario o el instalador, que no debe
    revertirse porque haya otro poppler suelto en el sistema—, luego el PATH y
    solo al final la detección automática.

    Antes esta función devolvía None de entrada fuera de Windows, dando por
    hecho que en Unix poppler siempre está en el PATH. No es cierto en macOS:
    una app lanzada desde Finder hereda un PATH mínimo sin Homebrew, así que
    ahí también hay que darle a pdf2image la ruta explícita.
    """
    import shutil

    from core import plataforma
    # _MODULE_ROOT y no Path(__file__) directo: así los tests pueden apuntar la
    # búsqueda a una raíz temporal y comprobar de verdad quién manda.
    cfg = _MODULE_ROOT / "poppler_path.txt"
    if cfg.exists():
        p = cfg.read_text(encoding="utf-8").strip()
        if p and Path(p, plataforma.nombre_ejecutable("pdftoppm")).exists():
            return p
    if shutil.which("pdftoppm"):
        return None
    bin_dir = plataforma.dir_poppler()
    if bin_dir:
        # Cachear el hallazgo: la búsqueda en Windows recorre el zip
        # descomprimido en profundidad y no conviene repetirla por página.
        try:
            cfg.write_text(bin_dir, encoding="utf-8")
        except OSError:
            pass
        return bin_dir
    return None


def _get_tesseract_cmd() -> str:
    """
    Ejecutable de Tesseract para pytesseract.

    tesseract_path.txt sigue mandando. El respaldo ya no es la cadena
    "tesseract" a secas —que solo funciona si el binario está en el PATH— sino
    la ruta completa detectada según el sistema; "tesseract" queda como último
    recurso para que el mensaje de error sea el de siempre.
    """
    from core import plataforma
    # _MODULE_ROOT y no Path(__file__) directo: así los tests pueden apuntar la
    # búsqueda a una raíz temporal y comprobar de verdad quién manda.
    cfg = _MODULE_ROOT / "tesseract_path.txt"
    if cfg.exists():
        t = cfg.read_text(encoding="utf-8").strip()
        if t and Path(t).exists():
            return t
    return plataforma.buscar_tesseract() or "tesseract"


# ── Detección de texto embebido ───────────────────────────────────────────────

def analizar_pdf(pdf_path: Path) -> dict:
    """
    Analiza un PDF y determina si ya tiene texto OCR embebido de calidad.
    Retorna:
        {
          "tiene_texto": bool,
          "palabras_promedio": float,   # palabras promedio por página
          "n_paginas": int,
          "confianza_estimada": float,  # 0-100
        }
    """
    try:
        import fitz  # pymupdf
        doc = fitz.open(str(pdf_path))
        n   = doc.page_count
        totales = []
        for i in range(min(n, 5)):   # muestrear primeras 5 páginas
            texto = doc[i].get_text("text")
            palabras = len(texto.split())
            totales.append(palabras)
        doc.close()
        promedio = sum(totales) / max(len(totales), 1)
        tiene    = promedio >= PALABRAS_MIN_PAGINA
        # Estimar confianza: páginas con >100 palabras = alta calidad
        conf_est = min(100.0, promedio / 1.5)
        return {"tiene_texto": tiene, "palabras_promedio": round(promedio, 1),
                "n_paginas": n, "confianza_estimada": round(conf_est, 1)}
    except Exception:
        return {"tiene_texto": False, "palabras_promedio": 0,
                "n_paginas": 0, "confianza_estimada": 0}


def _palabras_significativas(texto: str) -> set:
    """Palabras alfabéticas de ≥4 letras, en minúscula — huella de contenido
    que ignora números de página, coordenadas OCR y ruido corto."""
    return {w.lower() for w in re.findall(r"[A-Za-zÁÉÍÓÚÑáéíóúñ]{4,}", texto)}


def detectar_posibles_duplicados(
    pdfs: "list[Path]", n_paginas_muestra: int = 3, umbral: float = 0.5
) -> "list[tuple[Path, Path, float]]":
    """
    Compara el contenido de las primeras `n_paginas_muestra` páginas de cada
    PDF seleccionado y señala pares que probablemente son el mismo material
    (ej. el mismo número exportado dos veces con nombres distintos).

    No usa nombre de archivo ni número de páginas —un export parcial puede
    llamarse distinto y tener menos páginas— sino solapamiento real de
    vocabulario: |A∩B| / min(|A|,|B|) sobre el conjunto de palabras
    significativas de cada muestra.

    Retorna [(pdf_a, pdf_b, overlap), …] ordenado de mayor a menor overlap,
    solo los pares que superan `umbral`. Un PDF ilegible/vacío (huella
    vacía) nunca se compara (evita falsos positivos por división por cero).

    Ver hallazgo de auditoría s.59 de [[project_bashkar_station]]: el
    usuario seleccionó "rev_estampa_mar_1939.pdf" y "Páginas desde
    rev_estampa_mar_1939.pdf" (export parcial mal nombrado del mismo
    número) y Bashkar los procesó como dos números distintos sin avisar.
    """
    import fitz

    huellas: list[tuple[Path, set]] = []
    for p in pdfs:
        try:
            doc = fitz.open(str(p))
            texto = "".join(doc[i].get_text("text") for i in range(min(doc.page_count, n_paginas_muestra)))
            doc.close()
        except Exception:
            continue
        palabras = _palabras_significativas(texto)
        if palabras:
            huellas.append((p, palabras))

    pares = []
    for i in range(len(huellas)):
        pa, wa = huellas[i]
        for j in range(i + 1, len(huellas)):
            pb, wb = huellas[j]
            overlap = len(wa & wb) / min(len(wa), len(wb))
            if overlap >= umbral:
                pares.append((pa, pb, round(overlap, 3)))

    pares.sort(key=lambda t: t[2], reverse=True)
    return pares


def extraer_texto_pdf(pdf_path: Path, txt_dir: Path) -> list[dict]:
    """
    Extrae texto directamente del PDF (sin OCR, sin imágenes).
    Guarda un .txt por página en txt_dir.
    Retorna lista de dicts con metadatos por página.
    """
    import fitz
    txt_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(str(pdf_path))
    resultados = []
    from core.ocr_normalizer import normalizar_texto_ocr
    for i, pag in enumerate(doc):
        nombre_pag = f"p{i+1:04d}"
        txt_path   = txt_dir / f"{nombre_pag}.txt"
        if not txt_path.exists():
            texto = pag.get_text("text")
            texto = normalizar_texto_ocr(texto)
            txt_path.write_text(texto, encoding="utf-8")
        else:
            texto = txt_path.read_text(encoding="utf-8", errors="replace")
            texto_norm = normalizar_texto_ocr(texto)
            if texto_norm != texto:
                txt_path.write_text(texto_norm, encoding="utf-8")
            texto = texto_norm
        resultados.append({
            "pagina":    nombre_pag,
            "txt_path":  str(txt_path),
            "palabras":  len(texto.split()),
            "confianza": None,   # texto nativo, no aplica confianza OCR
            "revision":  False,
            "metodo":    "texto_embebido",
        })
    doc.close()
    gc.collect()
    return resultados


# ── Conversión PDF → imágenes ─────────────────────────────────────────────────

def pdf_a_imagenes(pdf_path: Path, out_dir: Path, dpi: int) -> list[Path]:
    """
    Convierte PDF a imágenes PNG respetando la rotación embebida en cada página.
    Usa PyMuPDF directamente (más fiable que poppler para PDFs de la BNC).
    Fallback a pdf2image/poppler si PyMuPDF no está disponible.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    existentes = sorted(out_dir.glob("*.png"))
    if existentes:
        return existentes   # reusar imágenes ya extraídas correctamente

    # Intentar con PyMuPDF primero — respeta rotación y produce imágenes correctas
    try:
        import io

        import fitz  # pymupdf
        from PIL import Image as _PIL

        doc = fitz.open(str(pdf_path))
        rutas = []
        # Factor de escala basado en DPI (PDF usa 72 DPI internamente)
        zoom = dpi / 72.0
        mat  = fitz.Matrix(zoom, zoom)

        for i, page in enumerate(doc):
            # get_pixmap respeta la rotación embebida en los metadatos del PDF
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img_bytes = pix.tobytes("png")
            img = _PIL.open(io.BytesIO(img_bytes)).convert("RGB")
            dest = out_dir / f"p{i+1:04d}.png"
            img.save(str(dest), "PNG", optimize=False)
            rutas.append(dest)

        doc.close()
        gc.collect()
        return sorted(out_dir.glob("*.png"))

    except Exception:
        pass

    # Fallback: pdf2image / poppler
    from pdf2image import convert_from_path
    poppler_path = _get_poppler_path()
    kwargs = dict(dpi=dpi, fmt="png", output_folder=str(out_dir),
                  output_file="p", paths_only=True, thread_count=1)
    if poppler_path:
        kwargs["poppler_path"] = poppler_path
    convert_from_path(str(pdf_path), **kwargs)
    gc.collect()
    return sorted(out_dir.glob("*.png"))


# ── OCR de una imagen ─────────────────────────────────────────────────────────

def ocr_pagina(
    img_path: Path,
    lang: str = "spa",
    preprocesar: bool = False,  # desactivado por defecto — hacerlo antes si se desea
) -> tuple[str, float]:
    import numpy as np
    import pytesseract
    from PIL import Image, ImageEnhance

    pytesseract.pytesseract.tesseract_cmd = _get_tesseract_cmd()

    img = Image.open(img_path)
    # Conservar RGB si la imagen tiene color — Tesseract lo maneja bien
    # Solo convertir a gris si ya es paleta o RGBA
    if img.mode in ("P", "RGBA", "LA"):
        img = img.convert("RGB")
    if preprocesar:
        from core.image_preprocessor import preprocesar_para_ocr
        img = preprocesar_para_ocr(img)
    # Mejora mínima y conservadora — no distorsionar la imagen
    img_gray = img.convert("L")
    img_gray = ImageEnhance.Contrast(img_gray).enhance(1.2)
    img = img_gray
    config = f"--oem 3 --psm 3 -l {lang}"
    texto  = pytesseract.image_to_string(img, config=config)
    data   = pytesseract.image_to_data(img, config=config,
                                       output_type=pytesseract.Output.DICT)
    confs  = [c for c in data["conf"] if c != -1]
    conf   = round(float(np.mean(confs)) if confs else 0.0, 1)
    img.close()
    del img, data
    gc.collect()
    # Normalización post-OCR
    from core.ocr_normalizer import normalizar_texto_ocr
    texto = normalizar_texto_ocr(texto)
    return texto, conf


# ── Procesar carpeta de imágenes ──────────────────────────────────────────────

def imagenes_a_texto(img_dir: Path, txt_dir: Path, lang: str) -> list[dict]:
    """
    Aplica OCR a todas las imágenes de img_dir (JPG, PNG, TIFF, etc.).
    Retorna lista de dicts de metadatos por imagen.
    """
    txt_dir.mkdir(parents=True, exist_ok=True)
    imgs = sorted(p for p in img_dir.iterdir()
                  if p.suffix.lower() in EXTS_IMAGEN)
    resultados = []
    from core.ocr_normalizer import normalizar_texto_ocr
    for img_path in imgs:
        txt_path = txt_dir / (img_path.stem + ".txt")
        if txt_path.exists():
            texto = txt_path.read_text("utf-8", errors="replace")
            texto_norm = normalizar_texto_ocr(texto)
            if texto_norm != texto:
                txt_path.write_text(texto_norm, encoding="utf-8")
            texto = texto_norm
            conf  = None
        else:
            texto, conf = ocr_pagina(img_path, lang=lang)
            txt_path.write_text(texto, encoding="utf-8")
        resultados.append({
            "pagina":   img_path.stem,
            "txt_path": str(txt_path),
            "palabras": len(texto.split()),
            "confianza": conf,
            "revision":  bool(conf is not None and conf < 60),
            "metodo":    "ocr_imagen",
        })
    return resultados
