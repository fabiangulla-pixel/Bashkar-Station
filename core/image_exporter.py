"""
core/image_exporter.py — Extracción y organización de imágenes de la publicación.

Genera una carpeta con cada imagen recortada de las páginas, nombrando
los archivos de la forma:
  <publicacion>_num<numero>_pag<pagina>_<tipo>_<idx>[_<autor>].png

Ejemplo:
  Estampa_num12_pag003_fotografia_01_Ricardo_Rendon.png
  Estampa_num12_pag005_ilustracion_02.png
"""

import re, gc
from pathlib import Path
from typing import Optional, Callable


# Tipos de elementos que se consideran "imágenes" (se excluye texto puro)
TIPOS_IMAGEN = {
    "Fotografía", "Ilustración / caricatura", "Ilustración",
    "Publicidad", "Mixto", "Viñeta",
    # Alias IA
    "fotografía", "ilustración", "caricatura", "publicidad", "viñeta", "mixto",
}


def _sanitizar(texto: str, max_len: int = 30) -> str:
    """Convierte un texto en componente de nombre de archivo seguro."""
    s = re.sub(r"[^\w\sáéíóúüñÁÉÍÓÚÜÑ]", "", texto, flags=re.UNICODE)
    s = re.sub(r"\s+", "_", s.strip())
    return s[:max_len]


def _nombre_archivo(publicacion: str, nombre_num: str, pagina: str,
                     tipo: str, idx: int, autor: str = "") -> str:
    pub   = _sanitizar(publicacion, 20)
    num   = _sanitizar(nombre_num, 20)
    pag   = re.sub(r"\D", "", str(pagina)).zfill(3)
    tip   = _sanitizar(tipo, 15).lower()
    base  = f"{pub}_{num}_pag{pag}_{tip}_{idx:02d}"
    if autor:
        base += "_" + _sanitizar(autor, 25)
    return base + ".png"


def exportar_imagenes(
    datos_imagenes: dict,
    img_dir_raiz: Path,
    destino: Path,
    publicacion: str = "Publicacion",
    tipos: Optional[set] = None,
    min_ancho_px: int = 60,
    min_alto_px:  int = 60,
    callback: Optional[Callable[[int, int, str], None]] = None,
) -> dict:
    """
    Recorre datos_imagenes (estructura de visual_analyzer), recorta cada
    elemento que sea imagen y lo guarda en *destino* con nombre descriptivo.

    Parámetros
    ----------
    datos_imagenes  : dict  {nombre_numero → {paginas: [{pagina, elementos:[…]}]}}
    img_dir_raiz    : Path  carpeta raíz donde están las subcarpetas por número (imgs/)
    destino         : Path  carpeta de salida (se crea si no existe)
    publicacion     : str   nombre de la publicación para prefijo
    tipos           : set   tipos a exportar (None → todos excepto texto)
    min_ancho_px    : int   filtro de tamaño mínimo
    min_alto_px     : int   filtro de tamaño mínimo
    callback        : callable(n_actual, n_total, descripcion)

    Retorna
    -------
    dict con estadísticas: {exportadas, omitidas, errores, archivos}
    """
    import cv2

    if tipos is None:
        tipos = TIPOS_IMAGEN

    destino.mkdir(parents=True, exist_ok=True)

    stats = {"exportadas": 0, "omitidas": 0, "errores": 0, "archivos": []}

    # Construir lista plana de tareas
    tareas = []
    for nombre_num, datos in datos_imagenes.items():
        for pag_datos in datos.get("paginas", []):
            pagina = pag_datos.get("pagina", "?")
            # Localizar la imagen de la página
            # Las imágenes se guardan en img_dir_raiz / nombre_num / pagina.png
            img_path = img_dir_raiz / nombre_num / f"{pagina}.png"
            if not img_path.exists():
                # Intentar variantes
                for ext in (".jpg", ".jpeg"):
                    alt = img_path.with_suffix(ext)
                    if alt.exists():
                        img_path = alt
                        break

            for i, el in enumerate(pag_datos.get("elementos", []), 1):
                tipo = el.get("tipo_ai") or el.get("tipo", "")
                if tipo not in tipos:
                    continue
                tareas.append({
                    "img_path":   img_path,
                    "nombre_num": nombre_num,
                    "pagina":     pagina,
                    "tipo":       tipo,
                    "idx":        i,
                    "autor":      el.get("autor", ""),
                    "x":          el.get("x_px", 0),
                    "y":          el.get("y_px", 0),
                    "w":          el.get("w_px", 0),
                    "h":          el.get("h_px", 0),
                })

    total = len(tareas)
    for n, t in enumerate(tareas, 1):
        if callback:
            callback(n, total, f"{t['nombre_num']} · pág {t['pagina']}")

        w, h = t["w"], t["h"]
        if w < min_ancho_px or h < min_alto_px:
            stats["omitidas"] += 1
            continue

        img_path = t["img_path"]
        if not img_path.exists():
            stats["omitidas"] += 1
            continue

        try:
            img = cv2.imread(str(img_path))
            if img is None:
                stats["errores"] += 1
                continue

            ih, iw = img.shape[:2]
            x0 = max(0, t["x"] - 4)
            y0 = max(0, t["y"] - 4)
            x1 = min(iw, t["x"] + w + 4)
            y1 = min(ih, t["y"] + h + 4)
            recorte = img[y0:y1, x0:x1]
            if recorte.size == 0:
                stats["omitidas"] += 1
                continue

            nombre = _nombre_archivo(
                publicacion, t["nombre_num"], t["pagina"],
                t["tipo"], t["idx"], t["autor"]
            )
            ruta = destino / nombre
            cv2.imwrite(str(ruta), recorte,
                        [cv2.IMWRITE_PNG_COMPRESSION, 6])
            stats["exportadas"] += 1
            stats["archivos"].append(str(ruta))

            del img, recorte
            gc.collect()

        except Exception as e:
            stats["errores"] += 1

    return stats
