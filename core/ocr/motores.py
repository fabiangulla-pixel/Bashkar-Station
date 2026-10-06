"""core/ocr/motores.py — Adaptadores de los motores existentes al contrato.

Los módulos de cada motor (``core/ocr_engine.py``, ``ocr_churro.py``…) no se
tocan: aquí solo se envuelven. Así la extracción no cambia el comportamiento
de nada que ya funcione, y cada adaptador se prueba contra el mismo contrato
(``tests/test_motores_ocr.py``).
"""

from __future__ import annotations

import functools
import time
from pathlib import Path

from core.ocr.interfaces import Bloque, ResultadoOCR

# Tipos de zona de Bashkar (``zone_labeler.TIPOS_ZONA``) → tipos de bloque.
_TIPO_ZONA_A_BLOQUE = {
    "articulo": "texto", "titulo": "titulo", "publicidad": "publicidad",
    "foto": "figura", "pie_foto": "pie_imagen", "numero_pag": "numero_pagina",
    "cabecera": "cabecera", "indice": "lista", "colofon": "nota",
}


def bloques_de_zonas(zonas: list[dict]) -> list[Bloque]:
    """Zonas de ``ocr_por_zonas`` (con ``bbox``) → bloques del contrato."""
    return [Bloque(texto=z.get("texto", ""), bbox=tuple(z["bbox"]),
                   tipo=_TIPO_ZONA_A_BLOQUE.get(z.get("tipo"), "desconocido"),
                   orden=z.get("orden", 0), confianza=z.get("confianza"))
            for z in zonas if z.get("bbox")]


def _medir(fn):
    """Rellena ``segundos`` del resultado."""
    @functools.wraps(fn)
    def envoltura(self, imagen):
        t0 = time.perf_counter()
        r = fn(self, Path(imagen))
        r.segundos = round(time.perf_counter() - t0, 3)
        return r
    return envoltura


@functools.lru_cache(maxsize=1)
def _version_tesseract() -> str:
    try:
        import pytesseract

        from core.ocr_engine import _get_tesseract_cmd
        pytesseract.pytesseract.tesseract_cmd = _get_tesseract_cmd()
        return f"tesseract {pytesseract.get_tesseract_version()}"
    except Exception:
        return "tesseract desconocida"


class Tesseract:
    """Página completa, la ruta de producción (``ocr_engine.ocr_pagina``)."""

    nombre = "tesseract"
    etiqueta = "Tesseract (local, rápido)"

    def __init__(self, lang: str = "spa"):
        self.lang = lang

    def motivo_no_disponible(self) -> str | None:
        from core import plataforma
        return None if plataforma.buscar_tesseract() else (
            "Tesseract no está instalado: ver INSTALACION.md, paso 3")

    def version(self) -> str:
        return f"{_version_tesseract()} lang={self.lang}"

    @_medir
    def reconocer(self, imagen: Path) -> ResultadoOCR:
        from core.ocr_engine import ocr_pagina
        texto, conf = ocr_pagina(imagen, lang=self.lang)
        return ResultadoOCR(texto or "", self.nombre, self.version(), confianza=conf)

    def liberar(self) -> None:
        pass


class TesseractZonas(Tesseract):
    """Deskew + bloques RLSA + OCR por zona, sin etiquetas manuales.

    Trabaja sobre una COPIA: el deskew de ``analizar_pagina_local`` guarda la
    imagen enderezada encima del archivo (sesión 70).
    """

    nombre = "zonas"
    etiqueta = "Tesseract por zonas (deskew + RLSA)"

    def version(self) -> str:
        return f"{_version_tesseract()} lang={self.lang} +zonas-rlsa"

    @_medir
    def reconocer(self, imagen: Path) -> ResultadoOCR:
        import shutil
        import tempfile

        from core.layout_tesseract import analizar_pagina_local, ocr_por_zonas
        with tempfile.TemporaryDirectory(prefix="bashkar_zonas_") as tmp:
            copia = Path(tmp) / imagen.name
            shutil.copy2(imagen, copia)
            zonas = analizar_pagina_local(copia)
            if zonas:
                r = ocr_por_zonas(copia, zonas, idioma=self.lang)
                if r["texto"].strip():
                    return ResultadoOCR(r["texto"], self.nombre, self.version(),
                                        confianza=r.get("confianza"),
                                        detalles={"zonas": len(r.get("zonas", []))},
                                        bloques=bloques_de_zonas(r.get("zonas", [])))
            from core.ocr_engine import ocr_pagina
            texto, conf = ocr_pagina(copia, lang=self.lang)
            return ResultadoOCR(texto or "", self.nombre, self.version(), confianza=conf,
                                detalles={"zonas": 0, "respaldo": "pagina_completa"})


class Churro:
    """CHURRO-3B (visión, local). ~12 GB residentes: liberar al terminar."""

    nombre = "churro"
    etiqueta = "CHURRO-3B (visión, local)"

    def __init__(self, out_dir=None, numero: str = "", log=None):
        # Con out_dir + numero usa las zonas que etiquetó el investigador.
        self.out_dir, self.numero, self.log = out_dir, numero, log or (lambda m: None)

    def motivo_no_disponible(self) -> str | None:
        from core import ocr_churro
        motivo = ocr_churro.motivo_no_disponible()
        if motivo:
            return motivo
        if not ocr_churro.esta_descargado():
            return "requiere descargar ~7 GB la primera vez"
        return None

    def version(self) -> str:
        from core import ocr_churro
        return ocr_churro.MODELO_ID

    @_medir
    def reconocer(self, imagen: Path) -> ResultadoOCR:
        from core import ocr_churro
        from core.zone_labeler import cargar_pagina
        pag = (cargar_pagina(self.out_dir, self.numero, imagen.stem)
               if self.out_dir and self.numero else None)
        if pag and pag.zonas:
            self.log(f"    {imagen.stem}: usando {len(pag.zonas)} zona(s) etiquetada(s)")
            texto = ocr_churro.ocr_pagina_con_zonas(imagen, pag.zonas, callback=self.log)["texto"]
            detalles = {"zonas_etiquetadas": len(pag.zonas)}
        else:
            self.log(f"    {imagen.stem}: sin etiquetar — página completa (más lento)")
            texto, detalles = ocr_churro.ocr_pagina(imagen), {}
        return ResultadoOCR(texto or "", self.nombre, self.version(), detalles=detalles)

    def liberar(self) -> None:
        from core import ocr_churro
        ocr_churro.liberar()


class Pero:
    """PERO-OCR. Cargar el motor cuesta segundos: se hace una vez por instancia."""

    nombre = "pero"
    etiqueta = "PERO-OCR (microfilm de prensa)"

    def __init__(self, config_ini=None):
        self._config = config_ini
        self._motor = None

    def _config_ini(self):
        if self._config:
            return self._config
        from core import ocr_pero
        candidatas = ocr_pero.rutas_config_probables()
        if not candidatas:
            raise RuntimeError("No se encontró el config.ini de PERO-OCR. Descarga un motor "
                               "de https://pero-ocr.fit.vutbr.cz")
        self._config = candidatas[0]
        return self._config

    def motivo_no_disponible(self) -> str | None:
        from core import ocr_pero
        motivo = ocr_pero.motivo_no_disponible()
        if motivo:
            return "no instalado: pip install pero-ocr"
        if not self._config and not ocr_pero.rutas_config_probables():
            return "falta el motor entrenado (config.ini)"
        return None

    def version(self) -> str:
        try:
            import importlib.metadata as md
            v = md.version("pero-ocr")
        except Exception:
            v = "?"
        cfg = Path(self._config).parent.name if self._config else "?"
        return f"pero-ocr {v} motor={cfg}"

    @_medir
    def reconocer(self, imagen: Path) -> ResultadoOCR:
        from core import ocr_pero
        cfg = self._config_ini()
        if self._motor is None:
            self._motor = ocr_pero._cargar_motor(cfg)
        texto = ocr_pero.ocr_pagina(imagen, cfg, motor=self._motor)
        return ResultadoOCR(texto or "", self.nombre, self.version())

    def liberar(self) -> None:
        self._motor = None


class Kraken:
    """Kraken/CATMuS en su venv dedicado (subproceso)."""

    nombre = "kraken"
    etiqueta = "Kraken / CATMuS (HTR)"

    def motivo_no_disponible(self) -> str | None:
        from core import ocr_kraken
        return None if ocr_kraken.kraken_disponible() else (
            "Kraken o su modelo no están instalados")

    def version(self) -> str:
        try:
            from core import ocr_kraken
            modelo = ocr_kraken._buscar_modelo()
            return f"kraken modelo={Path(modelo).name if modelo else '?'}"
        except Exception:
            return "kraken desconocida"

    @_medir
    def reconocer(self, imagen: Path) -> ResultadoOCR:
        from core.ocr_kraken import ocr_kraken
        texto, conf = ocr_kraken(str(imagen))
        # Kraken da 0-1; el contrato usa 0-100 como Tesseract.
        return ResultadoOCR(texto or "", self.nombre, self.version(),
                            confianza=None if conf is None else round(conf * 100, 1))

    def liberar(self) -> None:
        pass


class VisionIA:
    """IA de visión multiproveedor (``ocr_llm.ocr_con_vision``). Cuesta dinero:
    quien la use debe haber estimado y confirmado el costo antes."""

    nombre = "vision_llm"
    etiqueta = "IA de visión (nube o local)"

    def __init__(self, api_key: str = "", proveedor: str = "claude", modelo: str | None = None):
        from core import ocr_llm
        self.api_key, self.proveedor = api_key, proveedor
        self.modelo = modelo or ocr_llm._MODELO_VISION

    def motivo_no_disponible(self) -> str | None:
        if self.proveedor in ("ollama", "lmstudio"):
            return None
        return None if self.api_key else f"falta la clave de API de {self.proveedor}"

    def version(self) -> str:
        return f"{self.proveedor}:{self.modelo}"

    @_medir
    def reconocer(self, imagen: Path) -> ResultadoOCR:
        from core.ocr_llm import ocr_con_vision
        texto = ocr_con_vision(imagen, self.api_key, modelo=self.modelo,
                               proveedor=self.proveedor)
        return ResultadoOCR(texto or "", self.nombre, self.version())

    def liberar(self) -> None:
        pass


from core.ocr.externo import MotorExterno  # noqa: E402


class Surya(MotorExterno):
    """Surya-OCR 2 (VLM de datalab) en su venv, servido por llama.cpp con CUDA.

    Devuelve bloques con polígono, tipo y orden de lectura. Sin confianza por
    página: el modelo no la da (None, no 0).
    """

    nombre = "surya"
    etiqueta = "Surya OCR 2 (GPU, bloques y orden de lectura)"
    variable_venv = "BASHKAR_VENV_SURYA"
    venv_por_defecto = Path(r"C:\dev\venv-surya")
    script = "surya_trabajador.py"
    paquete = "surya"


class PaddleOCR(MotorExterno):
    """PaddleOCR (PP-OCRv5, reconocedor latino) en su venv, GPU. Bloques = líneas."""

    nombre = "paddle"
    etiqueta = "PaddleOCR (GPU, rápido, por líneas)"
    variable_venv = "BASHKAR_VENV_PADDLE"
    venv_por_defecto = Path(r"C:\dev\venv-paddle")
    script = "paddle_trabajador.py"
    paquete = "paddleocr"

    def _args(self) -> list[str]:
        return ["ocr"]


class PPStructure(PaddleOCR):
    """PP-StructureV3: layout, tablas, fórmulas y orden de lectura, en GPU."""

    nombre = "ppstructure"
    etiqueta = "PP-StructureV3 (GPU, layout y tablas)"

    def _args(self) -> list[str]:
        return ["estructura"]


# Rutas que se ofrecen en el benchmark, en orden de presentación. Kraken y la
# IA de visión existen como motores pero no se listan aquí: la primera exige
# un venv aparte y la segunda cuesta dinero por página.
RUTAS_BENCHMARK = ("tesseract", "zonas", "churro", "pero", "surya", "paddle", "ppstructure")

_CLASES = {c.nombre: c for c in (Tesseract, TesseractZonas, Churro, Pero, Kraken, VisionIA,
                                  Surya, PaddleOCR, PPStructure)}


def nombres() -> list[str]:
    return list(_CLASES)


def crear(nombre: str, **opciones):
    """Instancia el motor ``nombre`` con sus opciones (lang, out_dir, api_key…)."""
    try:
        clase = _CLASES[nombre]
    except KeyError:
        raise ValueError(f"motor de OCR desconocido: {nombre!r} "
                         f"(disponibles: {', '.join(_CLASES)})") from None
    import inspect
    aceptadas = inspect.signature(clase.__init__).parameters
    return clase(**{k: v for k, v in opciones.items() if k in aceptadas})


def reconocer_lote(motor, imagenes, log=print) -> dict[str, ResultadoOCR]:
    """Corre un motor sobre varias páginas y SIEMPRE libera la memoria al final,
    también si una página falla a la mitad (CHURRO deja ~12 GB colgados)."""
    salida: dict[str, ResultadoOCR] = {}
    try:
        for i, img in enumerate(imagenes):
            r = motor.reconocer(Path(img))
            salida[Path(img).stem] = r
            log(f"    {i + 1}/{len(imagenes)}  {Path(img).stem}  ({r.segundos:.1f} s)")
    finally:
        motor.liberar()
    return salida
