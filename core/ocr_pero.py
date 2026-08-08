"""core/ocr_pero.py — Ruta 7: PERO-OCR, motor especializado en microfilm de prensa.

PERO-OCR (Grupo DCGM, Universidad Tecnológica de Brno) es un motor de OCR de
código abierto cuya documentación declara estar **especializado en periódicos
checos de baja calidad digitalizados desde microfilm**, con buenos resultados
en documentos impresos europeos en general.

Por qué está aquí: es el caso exacto del corpus *Estampa*. La auditoría de la
sesión 36 documentó que los escaneos de la BNC vienen de microfilm, con 12-17°
de inclinación y grano, y que Tesseract con PSM 3 devolvía **0 palabras** sin
deskew ni denoise. PERO-OCR no es un motor genérico al que haya que domar: está
entrenado para esa degradación concreta, e incluye pipeline completo (detección
de párrafos, detección de líneas, transcripción y refinamiento con un modelo de
lenguaje).

A diferencia de [`core.ocr_churro`], no es un modelo de visión-lenguaje: es una
cadena clásica de detección + reconocimiento, mucho más rápida en CPU. Eso lo
hace candidato para procesar el corpus completo, no solo una muestra.

**Instalación** (no viene con la aplicación; el motor y sus modelos pesan):

    pip install pero-ocr

Los modelos entrenados se descargan aparte desde https://pero-ocr.fit.vutbr.cz
y se le indica a la aplicación la carpeta de configuración (`config.ini` del
motor). Mientras no estén, esta ruta se ofrece deshabilitada con el motivo a la
vista, en vez de fallar a mitad de un lote.

Referencias:
  · https://github.com/DCGM/pero-ocr
  · https://pypi.org/project/pero-ocr/
"""

from __future__ import annotations

import configparser
import time
from pathlib import Path

__all__ = [
    "disponible",
    "motivo_no_disponible",
    "rutas_config_probables",
    "estimar_tiempo",
    "ocr_pagina",
    "ocr_lote",
]

# Estimación en CPU de 6 núcleos. Es una cadena clásica, órdenes de magnitud
# más rápida que un VLM de 3B.
SEGUNDOS_POR_PAGINA_CPU = 12.0


def motivo_no_disponible(config_ini: str | Path | None = None) -> str | None:
    """Motivo por el que no se puede usar PERO-OCR, o None si está listo."""
    import importlib.util
    if importlib.util.find_spec("pero_ocr") is None:
        return ("PERO-OCR no está instalado. Instálalo con:\n\n"
                "    pip install pero-ocr\n\n"
                "y descarga un motor entrenado desde https://pero-ocr.fit.vutbr.cz")
    if config_ini is None:
        return ("Falta indicar el config.ini del motor de PERO-OCR "
                "(la carpeta que descargaste de pero-ocr.fit.vutbr.cz).")
    ruta = Path(config_ini)
    if not ruta.exists():
        return f"No existe el archivo de configuración: {ruta}"
    return None


def disponible(config_ini: str | Path | None = None) -> bool:
    return motivo_no_disponible(config_ini) is None


def rutas_config_probables() -> list[Path]:
    """Sitios donde suele quedar el motor descargado, para autodetectarlo."""
    from core import plataforma
    candidatas = [
        Path.home() / "pero_ocr" / "config.ini",
        Path.home() / ".pero_ocr" / "config.ini",
        Path.home() / "Documents" / "pero_ocr" / "config.ini",
    ]
    if plataforma.es_windows():
        # PERO-OCR se descarga como carpeta suelta y el usuario suele dejarla en
        # la raíz de un disco; las letras de unidad solo tienen sentido aquí.
        candidatas += [Path("C:/pero_ocr/config.ini"), Path("D:/pero_ocr/config.ini")]
    else:
        candidatas += [Path("/opt/pero_ocr/config.ini"),
                       Path("/usr/local/share/pero_ocr/config.ini")]
    salida = []
    for c in candidatas:
        try:
            if c.exists():
                salida.append(c)
        except OSError:      # unidad ausente o sin permisos
            continue
    return salida


def estimar_tiempo(n_paginas: int) -> dict:
    """Estimación previa de tiempo. En dinero cuesta 0: corre en local."""
    segundos = n_paginas * SEGUNDOS_POR_PAGINA_CPU
    return {
        "paginas": n_paginas,
        "segundos": segundos,
        "minutos": round(segundos / 60, 1),
        "texto": (f"{n_paginas} página(s) · ~{round(segundos / 60, 1)} min "
                  f"en CPU (~{int(SEGUNDOS_POR_PAGINA_CPU)} s por página)"),
        "costo_usd": 0.0,
    }


def _cargar_motor(config_ini: str | Path):
    """Construye el PageParser de PERO-OCR a partir de su config.ini."""
    motivo = motivo_no_disponible(config_ini)
    if motivo:
        raise RuntimeError(motivo)

    from pero_ocr.document_ocr.page_parser import PageParser

    ruta = Path(config_ini)
    config = configparser.ConfigParser()
    config.read(str(ruta), encoding="utf-8")
    # El motor resuelve rutas relativas respecto de su propia carpeta
    return PageParser(config, config_path=str(ruta.parent))


def _texto_de_pagina(page_layout) -> str:
    """Extrae el texto en orden de lectura del PageLayout de PERO-OCR."""
    lineas = []
    for region in getattr(page_layout, "regions", []) or []:
        for linea in getattr(region, "lines", []) or []:
            transcripcion = getattr(linea, "transcription", None)
            if transcripcion:
                lineas.append(transcripcion)
        lineas.append("")          # línea en blanco entre regiones
    return "\n".join(lineas).strip()


def ocr_pagina(ruta_imagen: str | Path, config_ini: str | Path,
               motor=None) -> str:
    """Transcribe UNA imagen con PERO-OCR.

    `motor` permite reutilizar un PageParser ya construido: cargarlo cuesta
    varios segundos y en un lote no tiene sentido repetirlo por página.
    """
    import cv2
    from pero_ocr.core.layout import PageLayout

    motor = motor or _cargar_motor(config_ini)
    ruta = Path(ruta_imagen)
    imagen = cv2.imread(str(ruta))
    if imagen is None:
        raise RuntimeError(f"No se pudo leer la imagen: {ruta}")

    layout = PageLayout(id=ruta.stem,
                        page_size=(imagen.shape[0], imagen.shape[1]))
    layout = motor.process_page(imagen, layout)
    return _texto_de_pagina(layout)


def ocr_lote(rutas_imagenes, config_ini: str | Path, callback=None) -> dict:
    """Transcribe varias imágenes reutilizando un solo motor. {nombre: texto}.

    Igual que en las demás rutas, un fallo en una página no aborta el lote:
    queda como texto vacío y el resto continúa.
    """
    motor = _cargar_motor(config_ini)
    resultados: dict[str, str] = {}
    rutas = list(rutas_imagenes)
    for i, ruta in enumerate(rutas):
        nombre = Path(ruta).stem
        t0 = time.perf_counter()
        try:
            resultados[nombre] = ocr_pagina(ruta, config_ini, motor=motor)
        except Exception as e:                  # noqa: BLE001
            resultados[nombre] = ""
            if callback:
                callback(i + 1, len(rutas), f"{nombre} — ERROR: {e}",
                         time.perf_counter() - t0)
            continue
        if callback:
            callback(i + 1, len(rutas), nombre, time.perf_counter() - t0)
    return resultados
