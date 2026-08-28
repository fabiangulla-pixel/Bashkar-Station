"""tests/test_inference_provider.py — core/inference_provider.py.

Regresión de un bug real encontrado en la primera corrida a escala completa
del pase de OCR Vision (792 páginas, 27-ago-2026): con thinking adaptativo
activado por defecto en Claude Sonnet 5, `content[0]` de la respuesta puede
ser un ThinkingBlock en vez de un TextBlock — `msg.content[0].text` revienta
con AttributeError. Efecto real: 194/214 páginas de un número fallaron con
"'ThinkingBlock' object has no attribute 'text'" en vez de transcribirse.
"""
from dataclasses import dataclass

import pytest

from core.inference_provider import ProviderResponse, _texto_de_respuesta_claude


@dataclass
class _BloqueThinking:
    thinking: str = "razonando en voz baja..."
    type: str = "thinking"


@dataclass
class _BloqueTexto:
    text: str
    type: str = "text"


@dataclass
class _RespuestaFalsa:
    content: list
    stop_reason: str = "end_turn"


class TestTextoDeRespuestaClaude:
    def test_extrae_texto_cuando_es_el_unico_bloque(self):
        msg = _RespuestaFalsa(content=[_BloqueTexto("hola mundo")])
        assert _texto_de_respuesta_claude(msg) == "hola mundo"

    def test_extrae_texto_cuando_thinking_va_primero(self):
        """El caso real que rompía: content[0] es ThinkingBlock."""
        msg = _RespuestaFalsa(content=[_BloqueThinking(), _BloqueTexto("  transcripción real  ")])
        assert _texto_de_respuesta_claude(msg) == "transcripción real"

    def test_lanza_error_claro_sin_bloque_de_texto(self):
        msg = _RespuestaFalsa(content=[_BloqueThinking()], stop_reason="max_tokens")
        with pytest.raises(ValueError, match="max_tokens"):
            _texto_de_respuesta_claude(msg)

    def test_toma_el_primer_bloque_de_texto_si_hay_varios(self):
        msg = _RespuestaFalsa(content=[
            _BloqueThinking(),
            _BloqueTexto("primero"),
            _BloqueTexto("segundo"),
        ])
        assert _texto_de_respuesta_claude(msg) == "primero"


class TestGenerateTextClaudeConThinking:
    def test_generate_text_no_revienta_con_thinking_primero(self):
        from core.inference_provider import generate_text

        class _MensajesFalsos:
            def create(self, **kwargs):
                return _RespuestaFalsa(content=[_BloqueThinking(), _BloqueTexto("respuesta")])

        class _ClienteFalso:
            messages = _MensajesFalsos()

        resp = generate_text(
            "claude", "un prompt", api_key="sk-fake",
            cliente_claude=lambda key: _ClienteFalso(),
        )
        assert isinstance(resp, ProviderResponse)
        assert resp.texto == "respuesta"


class TestGenerateVisionClaudeConThinking:
    def test_generate_vision_no_revienta_con_thinking_primero(self):
        from core.inference_provider import generate_vision

        class _MensajesFalsos:
            def create(self, **kwargs):
                return _RespuestaFalsa(content=[_BloqueThinking(), _BloqueTexto("texto de la pagina")])

        class _ClienteFalso:
            messages = _MensajesFalsos()

        resp = generate_vision(
            "claude", "transcribe esta pagina", "base64falso", "image/jpeg",
            api_key="sk-fake", cliente_claude=lambda key: _ClienteFalso(),
        )
        assert resp.texto == "texto de la pagina"
