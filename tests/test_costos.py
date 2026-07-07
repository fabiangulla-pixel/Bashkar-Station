"""tests/test_costos.py — Estimador de tokens/costo multiproveedor (visión + texto)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.costos import (  # noqa: E402
    PRECIOS,
    TOKENS_IMAGEN_COTA,
    costo_real_desde_usages,
    estimar_lote_ocr,
)


def test_precios_claude_y_openai():
    assert PRECIOS["claude-sonnet-4-6"].input_por_millon == 3.00  # visión por defecto
    assert PRECIOS["claude-haiku-4-5"].output_por_millon == 5.00  # texto por defecto
    assert PRECIOS["gpt-4o-mini"].input_por_millon == 0.15


def test_familia_mas_larga_gana():
    # "gpt-4o-mini" no debe ser capturado por el prefijo "gpt-4o".
    est = estimar_lote_ocr(1, "openai", "gpt-4o-mini")
    assert est.modelo_catalogado is True
    # gpt-4o-mini ($0.15/$0.60) es mucho más barato que gpt-4o; lo comprobamos
    # contra una página equivalente con gpt-4o.
    est_4o = estimar_lote_ocr(1, "openai", "gpt-4o")
    assert est.costo_usd < est_4o.costo_usd


def test_vision_cuesta_mas_que_texto_por_pagina():
    solo_texto = estimar_lote_ocr(10, "claude", "claude-haiku-4-5", n_vision=0)
    con_vision = estimar_lote_ocr(10, "claude", "claude-haiku-4-5", n_vision=10)
    assert con_vision.tokens_input > solo_texto.tokens_input
    assert con_vision.n_imagenes == 10


def test_tokens_imagen_usan_la_cota():
    est = estimar_lote_ocr(1, "claude", "claude-sonnet-4-6", n_vision=1, prompt_overhead_chars=0)
    # 1 imagen sin overhead → exactamente la cota de tokens de imagen.
    assert est.tokens_input == TOKENS_IMAGEN_COTA


def test_ollama_es_gratis():
    est = estimar_lote_ocr(50, "ollama", "llava", n_vision=50)
    assert est.es_local is True
    assert est.costo_usd == 0.0
    assert "LOCAL" in est.resumen()


def test_modelo_no_catalogado_cota_superior():
    est = estimar_lote_ocr(1, "claude", "modelo-fantasma")
    assert est.modelo_catalogado is False
    mas_caro = max(p.output_por_millon for p in PRECIOS.values())
    # El precio usado debe ser el más caro (fable-5 $50 out).
    assert mas_caro == 50.00


def test_lote_vacio():
    est = estimar_lote_ocr(0, "claude", "claude-haiku-4-5")
    assert est.n_items == 0
    assert est.costo_usd == 0


def test_costo_real_anthropic_y_openai():
    usages = [
        {"input_tokens": 1_000_000, "output_tokens": 0},  # Anthropic
        {"prompt_tokens": 0, "completion_tokens": 1_000_000},  # OpenAI
    ]
    # Con haiku ($1 in / $5 out): 1M in + 1M out = $1 + $5 = $6.
    real = costo_real_desde_usages("claude", "claude-haiku-4-5", usages)
    assert real.tokens_input == 1_000_000
    assert real.tokens_output == 1_000_000
    assert round(real.costo_usd, 2) == 6.00


def test_costo_real_ollama_cero():
    real = costo_real_desde_usages("ollama", "llava", [{"input_tokens": 999}])
    assert real.costo_usd == 0.0


def test_costo_real_cuenta_cache_creation():
    usages = [{"input_tokens": 500_000, "cache_creation_input_tokens": 500_000}]
    real = costo_real_desde_usages("claude", "claude-haiku-4-5", usages)
    assert real.tokens_input == 1_000_000
