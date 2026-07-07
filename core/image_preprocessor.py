"""
core/image_preprocessor.py — Preprocesamiento de imágenes de página antes del OCR.

Replica las funciones de preprocesamiento de ABBYY FineReader:
  - deskew:     corrige la inclinación de la página (2-4° típico en la BNC)
  - despeckle:  elimina ruido de puntos de papel envejecido
  - enhance:    mejora contraste para papel amarillado/manchado
  - binarize:   binarización adaptativa (mejor que global para papel no uniforme)

Diseñado para prensa colombiana de los años 30 digitalizada por la BNC.
"""

import math


def deskew(img, max_angle: float = 10.0):
    """
    Corrige la inclinación de una imagen de página.

    Detecta el ángulo dominante del texto mediante proyección de Hough sobre
    bordes horizontales (las líneas de texto son casi horizontales).

    Args:
        img:       PIL.Image o numpy array (BGR/grayscale).
        max_angle: Máximo ángulo de corrección en grados. Imágenes con mayor
                   inclinación se devuelven sin modificar (probablemente no son texto).

    Returns:
        PIL.Image corregida, o la imagen original si no se detectó inclinación.
    """
    try:
        import cv2
        import numpy as np
        from PIL import Image
    except ImportError:
        return img

    # Convertir a numpy si es PIL
    if hasattr(img, "tobytes"):
        arr = np.array(img.convert("L"))
        es_pil = True
    else:
        arr = img
        es_pil = False

    if arr.ndim == 3:
        gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
    else:
        gray = arr

    # Binarizar con Otsu para aislar tinta
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Detectar bordes horizontales
    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 1))
    bw_h = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kernel_h)

    # Transformada de Hough probabilística
    lines = cv2.HoughLinesP(
        bw_h, 1, math.pi / 180,
        threshold=100, minLineLength=100, maxLineGap=20
    )

    if lines is None or len(lines) == 0:
        return img

    # Calcular ángulo de cada línea detectada
    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        if x2 != x1:
            angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
            # Solo ángulos cercanos a horizontal
            if abs(angle) <= max_angle:
                angles.append(angle)

    if not angles:
        return img

    # Ángulo mediano (robusto ante outliers)
    import statistics
    angulo = statistics.median(angles)

    if abs(angulo) < 0.3:  # menor a 0.3° → no vale la pena rotar
        return img

    # Rotar la imagen PIL
    if not es_pil:
        from PIL import Image
        img_pil = Image.fromarray(cv2.cvtColor(arr, cv2.COLOR_BGR2RGB) if arr.ndim == 3 else arr)
    else:
        img_pil = img if hasattr(img, "rotate") else Image.fromarray(arr)

    img_rotada = img_pil.rotate(
        -angulo,
        expand=True,
        fillcolor=(255, 255, 255) if img_pil.mode != "L" else 255,
        resample=Image.BICUBIC,
    )
    return img_rotada


def despeckle(img, kernel_size: int = 2):
    """
    Elimina ruido de puntos (speckle) de papel envejecido.
    Usa apertura morfológica: elimina puntos aislados más pequeños que kernel_size.

    Args:
        img:         PIL.Image o numpy array.
        kernel_size: Radio del elemento estructurante. 2 = puntos ≤4px eliminados.

    Returns:
        PIL.Image limpia.
    """
    try:
        import cv2
        import numpy as np
        from PIL import Image
    except ImportError:
        return img

    if hasattr(img, "tobytes"):
        arr = np.array(img.convert("L"))
        es_pil = True
    else:
        arr = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        es_pil = False

    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (kernel_size * 2 + 1, kernel_size * 2 + 1)
    )
    limpia = cv2.morphologyEx(arr, cv2.MORPH_OPEN, kernel)

    if es_pil:
        return Image.fromarray(limpia)
    return limpia


def enhance_contrast(img, clip_limit: float = 2.0, tile_size: int = 8):
    """
    Mejora el contraste para imágenes con papel amarillado o manchas de tinta.
    Usa CLAHE (Contrast Limited Adaptive Histogram Equalization) — el mismo
    algoritmo que FineReader usa internamente para normalización de iluminación.

    Args:
        img:        PIL.Image o numpy array.
        clip_limit: Límite de recorte del histograma. Mayor = más contraste.
        tile_size:  Tamaño de la ventana adaptativa (en tiles de la imagen).

    Returns:
        PIL.Image mejorada.
    """
    try:
        import cv2
        import numpy as np
        from PIL import Image
    except ImportError:
        return img

    if hasattr(img, "tobytes"):
        arr = np.array(img.convert("L"))
        es_pil = True
    else:
        arr = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        es_pil = False

    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tile_size, tile_size))
    mejorada = clahe.apply(arr)

    if es_pil:
        return Image.fromarray(mejorada)
    return mejorada


def binarize_adaptive(img, block_size: int = 31, c: int = 10):
    """
    Binarización adaptativa local — mucho mejor que Otsu global para páginas
    con iluminación no uniforme (papel doblado, manchas de humedad).

    Args:
        img:        PIL.Image o numpy array.
        block_size: Tamaño del vecindario para el umbral adaptativo (impar).
        c:          Constante sustraída de la media local. Ajusta agresividad.

    Returns:
        PIL.Image en modo "L" binarizada (blanco=fondo, negro=tinta).
    """
    try:
        import cv2
        import numpy as np
        from PIL import Image
    except ImportError:
        return img

    if hasattr(img, "tobytes"):
        arr = np.array(img.convert("L"))
        es_pil = True
    else:
        arr = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        es_pil = True  # siempre devolver PIL

    bw = cv2.adaptiveThreshold(
        arr, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        block_size, c
    )
    return Image.fromarray(bw)


def preprocesar_para_ocr(
    img,
    deskew_en: bool = True,
    despeckle_en: bool = True,
    enhance_en: bool = True,
    max_angle: float = 8.0,
):
    """
    Pipeline completo de preprocesamiento antes del OCR.
    Orden: enhance → deskew → despeckle.

    Args:
        img:          PIL.Image de la página.
        deskew_en:    Activar corrección de inclinación.
        despeckle_en: Activar eliminación de ruido.
        enhance_en:   Activar mejora de contraste.
        max_angle:    Máximo ángulo de corrección.

    Returns:
        PIL.Image preprocesada lista para OCR.
    """
    if enhance_en:
        img = enhance_contrast(img)
    if deskew_en:
        img = deskew(img, max_angle=max_angle)
    if despeckle_en:
        img = despeckle(img)
    return img


def detectar_angulo_pagina(img) -> float:
    """
    Detecta el ángulo de inclinación de una página sin corregirla.
    Útil para mostrar al usuario o para decisiones de procesamiento.

    Returns:
        Ángulo en grados (negativo = inclinada a la izquierda).
        0.0 si no se pudo detectar.
    """
    try:
        import math
        import statistics

        import cv2
        import numpy as np
    except ImportError:
        return 0.0

    if hasattr(img, "tobytes"):
        arr = np.array(img.convert("L"))
    else:
        arr = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    _, bw = cv2.threshold(arr, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 1))
    bw_h = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kernel_h)
    lines = cv2.HoughLinesP(bw_h, 1, math.pi / 180,
                             threshold=80, minLineLength=80, maxLineGap=15)
    if lines is None:
        return 0.0

    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        if x2 != x1:
            a = math.degrees(math.atan2(y2 - y1, x2 - x1))
            if abs(a) <= 10.0:
                angles.append(a)

    return round(statistics.median(angles), 2) if angles else 0.0
