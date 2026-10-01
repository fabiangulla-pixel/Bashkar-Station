"""core/ocr/procedencia.py — Fila de metadatos de OCR fiel a lo que pasó.

El worker de OCR de la app (paneles/ocr.py) anotaba la procedencia de cada
página de forma optimista (sesión 71):

- Si la IA de visión, Kraken u Ollama fallaban en una página, se usaba
  Tesseract de respaldo pero la fila seguía diciendo "vision_claude",
  "kraken" u "ollama".
- La ruta de visión anotaba confianza 95.0 en cada página, también en las
  releídas de una corrida anterior: ningún modelo la calculó, y entraba en la
  "confianza OCR media" de METHODS.md.

``fila_meta`` registra el motor que de verdad produjo el texto, su versión,
y la confianza solo si el motor la midió (None si no: "sin medida" no es 0
ni 95). ``revision`` marca para revisión las páginas con confianza medida
baja y las que salieron de un respaldo.
"""

from __future__ import annotations

UMBRAL_REVISION = 60.0


def fila_meta(numero: str, pagina: str, txt_path, texto: str, *, motor: str,
              version: str = "", confianza: float | None = None,
              respaldo_de: str | None = None, **extra) -> dict:
    """Fila de ``ocr_metadatos.csv`` para una página.

    ``motor`` es el que produjo ``texto``; si fue un respaldo porque otro
    falló, ``respaldo_de`` nombra al que falló y ``metodo`` lo dice.
    """
    metodo = f"{motor}_respaldo_de_{respaldo_de}" if respaldo_de else motor
    baja = confianza is not None and confianza < UMBRAL_REVISION
    return {
        "numero": numero,
        "pagina": pagina,
        "txt_path": str(txt_path),
        "palabras": len((texto or "").split()),
        "confianza": confianza,
        "revision": bool(baja or respaldo_de),
        "metodo": metodo,
        "motor_version": version,
        **extra,
    }


def version_de(nombre: str, **opciones) -> str:
    """Versión de un motor del registro; nunca lanza (la fila no debe caerse
    por no saber la versión)."""
    try:
        from core.ocr import crear
        return crear(nombre, **opciones).version()
    except Exception:
        return "desconocida"
