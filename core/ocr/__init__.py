"""core/ocr — Motores de OCR detrás de un contrato común.

    from core.ocr import crear, reconocer_lote
    motor = crear("tesseract", lang="spa")
    resultado = motor.reconocer(ruta_imagen)   # ResultadoOCR(texto, motor, version, …)

Ver ``interfaces.py`` (el contrato) y ``motores.py`` (los adaptadores).
"""

from core.ocr.interfaces import TIPOS_BLOQUE, Bloque, MotorOCR, ResultadoOCR
from core.ocr.motores import RUTAS_BENCHMARK, crear, nombres, reconocer_lote

__all__ = ["TIPOS_BLOQUE", "Bloque", "MotorOCR", "ResultadoOCR", "RUTAS_BENCHMARK", "crear", "nombres",
           "reconocer_lote"]
