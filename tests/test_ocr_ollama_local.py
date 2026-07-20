"""tests/test_ocr_ollama_local.py — listar_modelos_vision() vía API REST de Ollama.

Bug real corregido: dependía del paquete pip "ollama" (no instalado, ni en
requirements.txt) y filtraba modelos por coincidencia de nombre ("vl",
"llava", "vision"...), que no reconoce familias nuevas (qwen3.6, gemma4,
gemma3) aunque SÍ sean modelos de visión según Ollama. Ahora consulta
GET /api/tags directo y filtra por el campo real `capabilities`.
"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.ocr_ollama_local import listar_modelos_vision  # noqa: E402


class _RespuestaFalsa:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_filtra_por_capacidad_no_por_nombre():
    """qwen3.6/gemma4 no tienen 'vl'/'vision'/'llava' en el nombre, pero SÍ
    traen 'vision' en capabilities — deben aparecer en el resultado."""
    payload = {"models": [
        {"name": "qwen3.6:latest", "capabilities": ["vision", "completion", "tools"]},
        {"name": "gemma4:latest", "capabilities": ["vision", "completion", "tools"]},
        {"name": "gemma3:4b", "capabilities": ["vision", "completion"]},
        {"name": "mistral:latest", "capabilities": ["completion", "tools"]},  # sin visión
    ]}
    with patch("core.ocr_ollama_local.requests.get", return_value=_RespuestaFalsa(payload)):
        resultado = listar_modelos_vision()
    assert resultado == ["qwen3.6:latest", "gemma4:latest", "gemma3:4b"]


def test_modelo_sin_capabilities_no_revienta():
    payload = {"models": [{"name": "modelo-viejo"}]}  # sin campo 'capabilities'
    with patch("core.ocr_ollama_local.requests.get", return_value=_RespuestaFalsa(payload)):
        assert listar_modelos_vision() == []


def test_ollama_no_disponible_devuelve_lista_vacia():
    with patch("core.ocr_ollama_local.requests.get", side_effect=ConnectionError("no server")):
        assert listar_modelos_vision() == []


def test_usa_la_url_configurada():
    payload = {"models": []}
    with patch("core.ocr_ollama_local.requests.get", return_value=_RespuestaFalsa(payload)) as mock_get:
        listar_modelos_vision("http://192.168.1.50:11434")
    url_llamada = mock_get.call_args[0][0]
    assert url_llamada == "http://192.168.1.50:11434/api/tags"


def test_sin_modelos_de_vision_devuelve_lista_vacia_no_error():
    payload = {"models": [{"name": "mistral", "capabilities": ["completion"]}]}
    with patch("core.ocr_ollama_local.requests.get", return_value=_RespuestaFalsa(payload)):
        assert listar_modelos_vision() == []
