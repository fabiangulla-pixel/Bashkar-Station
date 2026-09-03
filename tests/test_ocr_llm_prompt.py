"""tests/test_ocr_llm_prompt.py — Regresión del prompt de Vision OCR.

Frente 3 de la auditoría de sesión (2026-09-02): el juez de IA evaluó 46
páginas reales de rev_estampa_mar_1939 (ground_truth_piloto/rev_estampa_mar_1939/
juicios/*.json) con accuracy promedio 0.686. El error más citado (58 de 573
observaciones) fue texto "corrupto"/"sin sentido"/"que no corresponde a
contenido legible de la imagen" — el modelo completaba pasajes ilegibles
con texto plausible en vez de marcarlos [ilegible]. Estos tests protegen
las instrucciones agregadas a _PROMPT_VISION para atacar ese patrón,
para que un futuro refactor del prompt no las borre por accidente.
"""
from core.ocr_llm import _PROMPT_VISION


def test_prompt_advierte_contra_inventar_texto_ilegible():
    p = _PROMPT_VISION.lower()
    assert "[ilegible]" in p
    assert "no inventes" in p or "no la completes" in p or "no completes" in p


def test_prompt_pide_precision_en_tildes():
    assert "tilde" in _PROMPT_VISION.lower()


def test_prompt_pide_preservar_ordinales_abreviados_tal_cual():
    p = _PROMPT_VISION.lower()
    assert "ordinal" in p or "1er." in _PROMPT_VISION
