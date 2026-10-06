"""core/ocr/interfaces.py — Contrato común de los motores de OCR.

Hasta la sesión 70 cada motor tenía su propia firma (``ocr_pagina`` devuelve
``(texto, confianza)``, CHURRO solo texto, PERO trabaja por lotes con un motor
precargado, Kraken corre en un venv aparte) y quien los usaba —la GUI, la CLI,
el benchmark— elegía con cadenas de ``if ruta == ...``. Agregar un motor
obligaba a tocar todos esos sitios, y ninguno registraba con qué versión se
había producido un texto.

``MotorOCR`` es el contrato: un nombre estable, por qué no está disponible (o
``None``), qué versión es, cómo reconocer una página y cómo liberar memoria.
``ResultadoOCR`` lleva siempre ``motor`` y ``version``, que es lo que la capa
de proveniencia (``datos/normalizaciones``: ``ocr_motor``, ``ocr_version``)
necesita para no escribir "desconocido".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable


# Tipos de bloque. Los de prensa (publicidad, firma…) se agregan cuando un motor
# los distinga de verdad; "desconocido" es honesto, adivinar no.
TIPOS_BLOQUE = ("titulo", "subtitulo", "texto", "pie_imagen", "lista", "tabla",
                "figura", "formula", "cabecera", "pie_pagina", "numero_pagina",
                "nota", "publicidad", "desconocido")


@dataclass
class Bloque:
    """Una región de la página con su texto, geometría y procedencia.

    ``bbox`` va en píxeles de la imagen reconocida: ``(x0, y0, x1, y1)``.
    ``orden`` es el orden de lectura (1..n) que dio el motor; 0 = sin orden.
    """
    texto: str
    bbox: tuple[int, int, int, int]
    tipo: str = "desconocido"
    orden: int = 0
    confianza: float | None = None      # 0-100, misma escala que ResultadoOCR
    poligono: list[tuple[int, int]] | None = None
    revisar: bool = False
    alternativas: list[dict] = field(default_factory=list)  # [{motor, texto, confianza}]

    def a_dict(self) -> dict:
        return {"texto": self.texto, "bbox": list(self.bbox), "tipo": self.tipo,
                "orden": self.orden, "confianza": self.confianza,
                "poligono": [list(p) for p in self.poligono] if self.poligono else None,
                "revisar": self.revisar, "alternativas": self.alternativas}

    @classmethod
    def de_dict(cls, d: dict) -> "Bloque":
        return cls(texto=d.get("texto", ""), bbox=tuple(d["bbox"]),
                   tipo=d.get("tipo", "desconocido"), orden=d.get("orden", 0),
                   confianza=d.get("confianza"),
                   poligono=[tuple(p) for p in d["poligono"]] if d.get("poligono") else None,
                   revisar=d.get("revisar", False), alternativas=d.get("alternativas", []))


@dataclass
class ResultadoOCR:
    texto: str
    motor: str
    version: str
    # 0-100 cuando el motor la da; None cuando no (CHURRO, PERO, IA de visión).
    # None no es 0: "sin medida" no es "confianza nula".
    confianza: float | None = None
    segundos: float = 0.0
    detalles: dict = field(default_factory=dict)
    # Vacío si el motor no da geometría. Nunca se inventan coordenadas.
    bloques: list[Bloque] = field(default_factory=list)


@runtime_checkable
class MotorOCR(Protocol):
    nombre: str          # clave estable: "tesseract", "zonas", "churro"…
    etiqueta: str        # texto para la interfaz

    def motivo_no_disponible(self) -> str | None:
        """None si se puede usar; si no, qué falta, en términos accionables."""

    def version(self) -> str:
        """Versión del motor o del modelo que produce el texto."""

    def reconocer(self, imagen: Path) -> ResultadoOCR:
        """Transcribe UNA página. Lanza excepción si falla: un fallo no es texto vacío."""

    def liberar(self) -> None:
        """Suelta modelos residentes en memoria (no-op si no hay)."""
