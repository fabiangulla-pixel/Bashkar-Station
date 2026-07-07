"""
core/layout_tesseract.py — Análisis de layout local estilo FineReader.

Motor de detección de zonas 100% offline diseñado para los escaneos
degradados de la BNC (grano de microfilm, inclinación de 2-20°):

  1. Deskew automático — ángulo por líneas de texto (Hough) con respaldo
     por minAreaRect del contenido; la imagen corregida se guarda en disco.
  2. Máscara de tinta limpia — mediana + umbral adaptativo + filtrado de
     grano y de líneas largas (marcos, filetes).
  3. Segmentación RLSA (run-length smoothing) — forma bloques aunque el
     layout sea de tipo "marco" (fotos rodeando al texto), donde el XY-cut
     clásico y el PSM 3 de Tesseract fallan.
  4. Clasificación texto/foto por periodicidad del interlineado
     (autocorrelación de la proyección de filas).
  5. Refinamiento con Tesseract cuando el escaneo lo permite: títulos por
     altura tipográfica, cabeceras y números de página por posición.

También implementa el OCR por zonas (la pieza central de FineReader):
cada zona se recorta, se le aplica denoise + upscale y se reconoce por
separado en orden de lectura — preserva las columnas, a diferencia del
filtrado lineal del stream OCR.

Uso:
    from core.layout_tesseract import analizar_pagina_local, ocr_por_zonas
    zonas = analizar_pagina_local(img_path)                # list[Zona]
    res   = ocr_por_zonas(img_path, zonas, idioma="spa")   # {"texto", "zonas", "confianza"}
"""

from __future__ import annotations

import statistics
from pathlib import Path
from typing import Optional

from core.zone_labeler import Zona, TIPOS_ZONA, calcular_orden_lectura


# ── Configuración Tesseract ───────────────────────────────────────────────────

def _tesseract_cmd() -> str:
    from core.ocr_engine import _get_tesseract_cmd
    _asegurar_tessdata()
    return _get_tesseract_cmd()


def _asegurar_tessdata() -> None:
    """
    Fija TESSDATA_PREFIX si no está definido y spa.traineddata no está junto
    al ejecutable — necesario al usar el módulo fuera de app.py (CLI, tests).
    Mismo orden de búsqueda que app.py.
    """
    import os
    if os.environ.get("TESSDATA_PREFIX"):
        return
    candidatos = [
        Path.home() / "tessdata",
        Path(r"C:\Users\Lenovo\tessdata"),
        Path(r"C:\Program Files\Tesseract-OCR\tessdata"),
        Path(r"C:\Program Files (x86)\Tesseract-OCR\tessdata"),
    ]
    for td in candidatos:
        if (td / "spa.traineddata").exists():
            os.environ["TESSDATA_PREFIX"] = str(td)
            return


# ── Deskew ────────────────────────────────────────────────────────────────────

def detectar_angulo(img, max_ang: float = 20.0) -> float:
    """
    Detecta la inclinación de la página combinando dos métodos:
    1. Hough sobre líneas de texto (preciso hasta ±10°).
    2. minAreaRect del contenido entintado (respaldo, hasta ±max_ang;
       necesario en los escaneos BNC con 12-17° donde Hough no ve líneas).

    Devuelve grados; 0.0 si la página ya está derecha o no se pudo medir.
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        return 0.0

    from core.image_preprocessor import detectar_angulo_pagina
    ang = detectar_angulo_pagina(img)
    if abs(ang) >= 1.0:
        return float(ang)

    # Respaldo: rectángulo mínimo del contenido (tinta sobre fondo claro)
    arr = np.array(img.convert("L")) if hasattr(img, "convert") else img
    _, bw = cv2.threshold(arr, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE,
                          np.ones((35, 35), np.uint8), iterations=2)
    pts = cv2.findNonZero(bw)
    if pts is None:
        return 0.0
    _, _, ang_r = cv2.minAreaRect(pts)
    if ang_r < -45:
        ang_r += 90
    elif ang_r > 45:
        ang_r -= 90
    if 1.0 <= abs(ang_r) <= max_ang:
        return float(ang_r)
    return 0.0


def _deskew_y_guardar(img, img_path: Path, log) -> "tuple":
    """
    Corrige la inclinación (hasta 2 pasadas) y guarda la imagen corregida
    sobre el archivo original, para que zonas, canvas y OCR compartan el
    mismo marco de coordenadas (02_imagenes/ se regenera desde el PDF).
    Devuelve (imagen, angulo_total_aplicado).
    """
    from PIL import Image
    total = 0.0
    for _ in range(2):
        ang = detectar_angulo(img)
        if abs(ang) < 1.0:
            break
        img = img.rotate(ang, expand=True, fillcolor=255,
                         resample=Image.BICUBIC)
        total += ang
    if abs(total) >= 1.0:
        try:
            img.save(img_path)
            log(f"⟳ Inclinación corregida {total:+.1f}° y guardada")
        except Exception as e:
            log(f"⚠ No se pudo guardar el deskew: {e}")
    return img, total


# ── Máscara de tinta y RLSA ───────────────────────────────────────────────────

def _mascara_tinta(gray):
    """
    Binariza separando tinta de fondo en escaneos con grano de microfilm:
    mediana + umbral adaptativo agresivo + eliminación de motas y de
    líneas largas (marcos de foto, filetes — se detectan aparte).
    Devuelve (mascara, imagen_denoised).
    """
    import cv2
    import numpy as np

    H, W = gray.shape
    den = cv2.medianBlur(gray, 5)
    bw = cv2.adaptiveThreshold(den, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                               cv2.THRESH_BINARY_INV, 41, 25)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(bw, 8)
    malos = (stats[:, cv2.CC_STAT_AREA] < 25)
    malos |= ((stats[:, cv2.CC_STAT_HEIGHT] > H * 0.06) &
              (stats[:, cv2.CC_STAT_WIDTH] < W * 0.01))
    malos |= ((stats[:, cv2.CC_STAT_WIDTH] > W * 0.06) &
              (stats[:, cv2.CC_STAT_HEIGHT] < H * 0.008))
    malos[0] = False
    bw[np.isin(lab, np.where(malos)[0])] = 0
    return bw, den


def _altura_caracter(bw) -> float:
    """Altura mediana de los componentes de tamaño letra (px)."""
    import cv2
    import numpy as np
    n, lab, stats, _ = cv2.connectedComponentsWithStats(bw, 8)
    if n <= 1:
        return 15.0
    hs = stats[1:, cv2.CC_STAT_HEIGHT]
    areas = stats[1:, cv2.CC_STAT_AREA]
    sel = (areas >= 25) & (hs >= 5) & (hs <= 80)
    return float(np.median(hs[sel])) if sel.any() else 15.0


def _bloques_rlsa(bw, h_char: float):
    """
    Run-Length Smoothing: une letras en líneas (cierre horizontal) y líneas
    en bloques (cierre vertical). Devuelve lista de (x0, y0, x1, y1) en px.
    """
    import cv2

    H, W = bw.shape
    hsv = max(7, int(h_char * 2.2)) | 1
    vsv = max(7, int(h_char * 2.0)) | 1
    kh = cv2.getStructuringElement(cv2.MORPH_RECT, (hsv, 1))
    kv = cv2.getStructuringElement(cv2.MORPH_RECT, (1, vsv))
    blq = cv2.bitwise_and(cv2.morphologyEx(bw, cv2.MORPH_CLOSE, kh),
                          cv2.morphologyEx(bw, cv2.MORPH_CLOSE, kv))
    blq = cv2.morphologyEx(blq, cv2.MORPH_CLOSE,
                           cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)))
    cnts, _ = cv2.findContours(blq, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cajas = []
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        if w * h < W * H * 0.0025 or w < W * 0.025 or h < H * 0.015:
            continue
        cajas.append((x, y, x + w, y + h))
    return cajas


def periodicidad_lineas(sub_mask, h_char: float) -> float:
    """
    Fuerza del patrón periódico de interlineado en un bloque (0–1).
    El texto impreso tiene líneas a intervalos regulares → pico de
    autocorrelación en el rango [1.1, 3.2]×h_char. Las fotos no.
    """
    import numpy as np
    py = (sub_mask > 0).mean(axis=1).astype(np.float64)
    if len(py) < h_char * 4:
        return 0.0
    py = py - py.mean()
    if py.std() < 1e-6:
        return 0.0
    ac = np.correlate(py, py, mode="full")[len(py) - 1:]
    if ac[0] <= 0:
        return 0.0
    ac = ac / ac[0]
    lo = max(2, int(h_char * 1.1))
    hi = min(len(ac) - 1, int(h_char * 3.2))
    if hi <= lo:
        return 0.0
    return float(ac[lo:hi].max())


# ── Clasificación de bloques de texto (pura, testeable) ──────────────────────

def clasificar_bloque(
    n_palabras: int,
    altura_palabra_med: float,
    altura_mediana_pagina: float,
    texto: str,
    y_centro_norm: float,
    ancho_norm: float,
) -> str:
    """
    Clasifica un bloque de TEXTO en un tipo de zona Bashkar usando los
    metadatos de palabras de Tesseract (refinamiento del tipo "articulo").
    """
    alnum = [c for c in texto if c.isalnum()]
    digitos = sum(1 for c in alnum if c.isdigit())
    ratio_digitos = digitos / len(alnum) if alnum else 0.0

    # N.º de página: bloque mínimo, mayormente numérico, banda superior/inferior
    if n_palabras <= 4 and ratio_digitos > 0.5 and (
            y_centro_norm < 0.08 or y_centro_norm > 0.92):
        return "numero_pag"

    # Cabecera: banda superior estrecha (folio, fecha, nombre de la revista)
    if y_centro_norm < 0.055 and n_palabras <= 14:
        return "cabecera"

    # Título: tipografía notablemente mayor que el cuerpo, pocas palabras
    if (altura_mediana_pagina > 0 and
            altura_palabra_med >= 1.6 * altura_mediana_pagina and
            n_palabras <= 20):
        return "titulo"

    return "articulo"


# ── Análisis de página ────────────────────────────────────────────────────────

def analizar_pagina_local(
    img_path: Path,
    idioma: str = "spa",
    incluir_filetes: bool = True,
    auto_deskew: bool = True,
    umbral_texto: float = 0.22,
    refinar_con_tesseract: bool = True,
    callback=None,
) -> list[Zona]:
    """
    Detecta zonas en una página de prensa histórica. 100% local.
    Devuelve list[Zona] clasificadas y con orden de lectura asignado.
    """
    def log(m):
        if callback:
            callback(m)

    try:
        import cv2
        import numpy as np
        from PIL import Image
    except ImportError:
        log("⚠ OpenCV/Pillow no disponibles")
        return []

    img_path = Path(img_path)
    if not img_path.exists():
        log(f"⚠ Imagen no encontrada: {img_path}")
        return []

    img = Image.open(img_path)
    if img.mode != "L":
        img = img.convert("L")

    # 1. Deskew — sin esto, nada funciona en los escaneos BNC inclinados
    if auto_deskew:
        try:
            img, _ = _deskew_y_guardar(img, img_path, log)
        except Exception as e:
            log(f"⚠ Deskew omitido: {e}")

    gray = np.array(img)
    H, W = gray.shape

    # 2-3. Máscara limpia + bloques RLSA
    log("Segmentando bloques (RLSA)…")
    bw, den = _mascara_tinta(gray)
    h_char = _altura_caracter(bw)
    cajas = _bloques_rlsa(bw, h_char)

    # 4. Clasificación texto/foto por periodicidad de interlineado
    zonas: list[Zona] = []
    for (x0, y0, x1, y1) in cajas:
        per = periodicidad_lineas(bw[y0:y1, x0:x1], h_char)
        tipo = "articulo" if per >= umbral_texto else "foto"
        conf = 0.5 + min(0.4, abs(per - umbral_texto))
        zonas.append(Zona(
            tipo=tipo,
            x0=round(x0 / W, 4), y0=round(y0 / H, 4),
            x1=round(x1 / W, 4), y1=round(y1 / H, 4),
            confianza=round(conf, 2),
        ))

    # 5. Refinamiento con Tesseract: titulo / cabecera / numero_pag
    if refinar_con_tesseract and zonas:
        try:
            _refinar_tipos_tesseract(den, zonas, W, H, idioma, log)
        except Exception as e:
            log(f"⚠ Refinamiento Tesseract omitido: {e}")

    # Pies de foto: bloques de texto bajos pegados debajo de una foto
    fotos = [z for z in zonas if z.tipo == "foto"]
    for z in zonas:
        if z.tipo != "articulo" or (z.y1 - z.y0) > 0.05:
            continue
        for f in fotos:
            solape_x = min(z.x1, f.x1) - max(z.x0, f.x0)
            ancho_min = min(z.x1 - z.x0, f.x1 - f.x0)
            if ancho_min > 0 and solape_x / ancho_min >= 0.5 \
                    and 0 <= z.y0 - f.y1 <= 0.03:
                z.tipo = "pie_foto"
                break

    # 6. Filetes y separadores de columna
    if incluir_filetes:
        zonas.extend(_detectar_filetes(den, W, H))

    zonas = _descartar_contenidas(zonas)
    calcular_orden_lectura(zonas)

    n_txt = sum(1 for z in zonas if z.tipo in
                ("articulo", "titulo", "pie_foto", "cabecera", "numero_pag"))
    log(f"  Layout local: {len(zonas)} zonas ({n_txt} de texto)")
    return zonas


def _refinar_tipos_tesseract(den, zonas: list[Zona], W: int, H: int,
                             idioma: str, log) -> None:
    """
    Pasa Tesseract sobre la imagen denoised y usa las cajas de palabra para
    reclasificar bloques de texto: titulo (tipografía grande), cabecera y
    numero_pag (posición). En escaneos muy degradados Tesseract devuelve
    pocas palabras y este refinamiento simplemente no cambia nada.
    """
    import pytesseract
    from PIL import Image

    pytesseract.pytesseract.tesseract_cmd = _tesseract_cmd()
    data = pytesseract.image_to_data(
        Image.fromarray(den),
        config=f"--oem 3 --psm 3 -l {idioma}",
        output_type=pytesseract.Output.DICT,
    )
    palabras = []
    for i in range(len(data["text"])):
        txt = (data["text"][i] or "").strip()
        if not txt:
            continue
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            continue
        if conf < 20:
            continue
        palabras.append({
            "x": int(data["left"][i]), "y": int(data["top"][i]),
            "w": int(data["width"][i]), "h": int(data["height"][i]),
            "txt": txt,
        })
    if len(palabras) < 15:
        return   # escaneo demasiado degradado para refinar

    alturas = [p["h"] for p in palabras]
    h_med_pag = statistics.median(alturas)

    for z in zonas:
        if z.tipo not in ("articulo",):
            continue
        x0, y0 = z.x0 * W, z.y0 * H
        x1, y1 = z.x1 * W, z.y1 * H
        dentro = [p for p in palabras
                  if x0 <= p["x"] + p["w"] / 2 <= x1
                  and y0 <= p["y"] + p["h"] / 2 <= y1]
        if not dentro:
            continue
        tipo = clasificar_bloque(
            n_palabras=len(dentro),
            altura_palabra_med=statistics.median(p["h"] for p in dentro),
            altura_mediana_pagina=h_med_pag,
            texto=" ".join(p["txt"] for p in dentro),
            y_centro_norm=(z.y0 + z.y1) / 2,
            ancho_norm=z.x1 - z.x0,
        )
        if tipo != "articulo":
            z.tipo = tipo
    log(f"  Refinado con {len(palabras)} palabras Tesseract")


def _detectar_filetes(gray, W, H) -> list[Zona]:
    """Detecta filetes horizontales y separadores verticales de columna."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return []

    arr = np.asarray(gray)
    _, bw = cv2.threshold(arr, 180, 255, cv2.THRESH_BINARY_INV)
    zonas = []

    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (int(W * 0.30), 1))
    horiz = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kernel_h)
    cnts_h, _ = cv2.findContours(horiz, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in cnts_h:
        x, y, w, h = cv2.boundingRect(c)
        if h <= 6 and w >= W * 0.30:
            zonas.append(Zona(
                tipo="filete",
                x0=round(x / W, 4), y0=round(y / H, 4),
                x1=round((x + w) / W, 4), y1=round((y + h) / H, 4),
                confianza=0.80,
            ))

    kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, int(H * 0.20)))
    vert = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kernel_v)
    cnts_v, _ = cv2.findContours(vert, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in cnts_v:
        x, y, w, h = cv2.boundingRect(c)
        if w <= 6 and h >= H * 0.20:
            zonas.append(Zona(
                tipo="separador_columna",
                x0=round(x / W, 4), y0=round(y / H, 4),
                x1=round((x + w) / W, 4), y1=round((y + h) / H, 4),
                confianza=0.80,
            ))
    return zonas


def _descartar_contenidas(zonas: list[Zona], umbral: float = 0.88) -> list[Zona]:
    """
    Elimina zonas de texto cuya área está contenida ≥ umbral dentro de otra
    zona de texto mayor (fragmentos duplicados del mismo bloque).
    Las zonas de tipo distinto (foto vs texto) no se descartan entre sí.
    """
    TIPOS_TEXTO = {"articulo", "titulo", "pie_foto", "cabecera",
                   "numero_pag", "indice", "colofon"}
    resultado = []
    for i, z in enumerate(zonas):
        contenida = False
        if z.tipo in TIPOS_TEXTO:
            area_z = z.area()
            if area_z > 0:
                for j, otra in enumerate(zonas):
                    if i == j or otra.tipo not in TIPOS_TEXTO:
                        continue
                    if otra.area() <= area_z:
                        continue
                    ix0 = max(z.x0, otra.x0); iy0 = max(z.y0, otra.y0)
                    ix1 = min(z.x1, otra.x1); iy1 = min(z.y1, otra.y1)
                    if ix1 > ix0 and iy1 > iy0:
                        inter = (ix1 - ix0) * (iy1 - iy0)
                        if inter / area_z >= umbral:
                            contenida = True
                            break
        if not contenida:
            resultado.append(z)
    return resultado


# ── OCR por zonas (estilo FineReader) ─────────────────────────────────────────

def _mejorar_recorte(crop, escala: int = 2):
    """
    Preprocesa un recorte para OCR en escaneos con grano: mediana +
    denoise non-local means + upscale. Validado: pasa de 0 a ~80 palabras
    legibles por columna en los escaneos BNC de Estampa.
    """
    try:
        import cv2
        import numpy as np
        arr = np.array(crop)
        arr = cv2.medianBlur(arr, 3)
        # NLMeans es costoso — solo en recortes de tamaño razonable
        if arr.size <= 4_000_000:
            arr = cv2.fastNlMeansDenoising(arr, None, h=15,
                                           templateWindowSize=7,
                                           searchWindowSize=21)
        arr = cv2.resize(arr, None, fx=escala, fy=escala,
                         interpolation=cv2.INTER_CUBIC)
        from PIL import Image
        return Image.fromarray(arr)
    except Exception:
        return crop


def ocr_por_zonas(
    img_path: Path,
    zonas: list[Zona],
    idioma: str = "spa",
    normalizar: bool = True,
    mejorar: bool = True,
    margen_px: int = 4,
    callback=None,
) -> dict:
    """
    OCR-ea cada zona procesable por separado, en orden de lectura.
    A diferencia del filtrado lineal, esto preserva las columnas: cada
    recorte se mejora (denoise+upscale) y se reconoce de forma
    independiente con el PSM adecuado.

    Returns:
        {
          "texto":     str — texto completo en orden de lectura,
          "zonas":     list[dict] — {orden, tipo, texto, confianza} por zona,
          "confianza": float — confianza media (0–100),
        }
    """
    def log(m):
        if callback:
            callback(m)

    import pytesseract
    from PIL import Image

    pytesseract.pytesseract.tesseract_cmd = _tesseract_cmd()

    img = Image.open(img_path)
    if img.mode != "L":
        img = img.convert("L")
    W, H = img.size

    procesables = [z for z in zonas
                   if TIPOS_ZONA.get(z.tipo, {}).get("ocr", True)]
    if not procesables:
        return {"texto": "", "zonas": [], "confianza": 0.0}

    # Garantizar orden de lectura
    if all(getattr(z, "orden", 0) == 0 for z in procesables):
        calcular_orden_lectura(zonas)
    procesables.sort(key=lambda z: (z.orden if z.orden > 0 else 9999, z.y0, z.x0))

    resultados = []
    confs = []
    for i, z in enumerate(procesables):
        x0, y0, x1, y1 = z.a_pixeles(W, H)
        x0 = max(0, x0 - margen_px); y0 = max(0, y0 - margen_px)
        x1 = min(W, x1 + margen_px); y1 = min(H, y1 + margen_px)
        if x1 - x0 < 8 or y1 - y0 < 8:
            continue
        crop = img.crop((x0, y0, x1, y1))
        if mejorar:
            crop = _mejorar_recorte(crop)

        # PSM 7 (una línea) para zonas de una sola línea; PSM 6 (bloque) si no
        psm = 7 if (y1 - y0) < H * 0.035 else 6
        config = f"--oem 3 --psm {psm} -l {idioma}"
        try:
            texto = pytesseract.image_to_string(crop, config=config).strip()
            data = pytesseract.image_to_data(
                crop, config=config, output_type=pytesseract.Output.DICT)
            zconfs = [float(c) for c in data["conf"]
                      if c not in (-1, "-1")]
            conf = round(statistics.mean(zconfs), 1) if zconfs else 0.0
        except Exception as e:
            log(f"⚠ OCR falló en zona {i+1}: {e}")
            texto, conf = "", 0.0

        if conf:
            confs.append(conf)
        resultados.append({
            "orden": z.orden or (i + 1),
            "tipo": z.tipo,
            "texto": texto,
            "confianza": conf,
        })
        log(f"  Zona {i+1}/{len(procesables)} ({z.tipo}): "
            f"{len(texto.split())} palabras, conf {conf:.0f}")

    texto_total = "\n\n".join(r["texto"] for r in resultados if r["texto"])
    if normalizar and texto_total:
        from core.ocr_normalizer import normalizar_texto_ocr
        texto_total = normalizar_texto_ocr(texto_total)

    return {
        "texto": texto_total,
        "zonas": resultados,
        "confianza": round(statistics.mean(confs), 1) if confs else 0.0,
    }


def ocr_pagina_con_zonas(
    img_path: Path,
    out_dir: Path,
    numero: str,
    pagina: str,
    lang: str = "spa",
) -> tuple[str, float, bool]:
    """
    Punto de integración con el pipeline OCR (Ruta 1):
    si la página tiene zonas guardadas en 05_etiquetas/, OCR-ea por zonas;
    si no, cae al OCR de página completa.

    Returns: (texto, confianza, uso_zonas)
    """
    from core.zone_labeler import cargar_pagina

    pag = cargar_pagina(out_dir, numero, pagina)
    if pag is not None and pag.zonas_ocr():
        try:
            res = ocr_por_zonas(img_path, pag.zonas, idioma=lang)
            if res["texto"].strip():
                return res["texto"], res["confianza"], True
        except Exception:
            pass  # cualquier fallo → página completa

    from core.ocr_engine import ocr_pagina
    texto, conf = ocr_pagina(img_path, lang=lang)
    return texto, conf if conf is not None else 0.0, False
