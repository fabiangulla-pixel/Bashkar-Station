"""tests/test_juez_ground_truth.py — scripts/juez_ground_truth.py sin red real.

Adaptado del patrón de test de Medallo/GullaBench (test_llm_judge.py): un
cliente Anthropic falso que nunca sale a internet, para verificar la lógica
de armado de mensajes, parseo de respuesta, estimación de costo y
resumibilidad (páginas ya juzgadas se saltan) sin gastar un centavo.
"""
import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "juez_ground_truth.py"
_spec = importlib.util.spec_from_file_location("juez_ground_truth", _SCRIPT_PATH)
juez = importlib.util.module_from_spec(_spec)
sys.modules["juez_ground_truth"] = juez
_spec.loader.exec_module(juez)


@dataclass
class _FakeTextBlock:
    text: str
    type: str = "text"


@dataclass
class _FakeUsage:
    input_tokens: int
    output_tokens: int


@dataclass
class _FakeMessage:
    content: list
    usage: _FakeUsage
    stop_reason: str = "end_turn"


@dataclass
class _FakeCountResponse:
    input_tokens: int


class _FakeMessages:
    def __init__(self, *, create_response=None, count_response=None):
        self._create_response = create_response
        self._count_response = count_response
        self.create_calls: list[dict] = []

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return self._create_response

    def count_tokens(self, **kwargs):
        return self._count_response


class _FakeClient:
    def __init__(self, messages: _FakeMessages):
        self.messages = messages


def _respuesta_json(**overrides):
    payload = {
        "accuracy_estimate": 0.85,
        "errors": [{"quote": "meuos", "issue": "debería ser 'menos'"}],
        "notes": "resto legible",
    }
    payload.update(overrides)
    return json.dumps(payload)


def test_build_messages_incluye_imagen_y_texto(tmp_path):
    imagen = tmp_path / "p0002.jpg"
    imagen.write_bytes(b"\xff\xd8\xff")
    mensajes = juez.build_messages(imagen, "texto candidato")
    contenido = mensajes[0]["content"]
    assert contenido[0]["type"] == "image"
    assert contenido[0]["source"]["media_type"] == "image/jpeg"
    assert "texto candidato" in contenido[1]["text"]


def test_judge_page_parsea_respuesta_valida(tmp_path):
    imagen = tmp_path / "p0002.jpg"
    imagen.write_bytes(b"\xff\xd8\xff")
    fake = _FakeMessages(create_response=_FakeMessage(
        content=[_FakeTextBlock(_respuesta_json())],
        usage=_FakeUsage(input_tokens=1000, output_tokens=200),
    ))
    client = _FakeClient(fake)

    resultado = juez.judge_page(client, "p0002", imagen, "meuos texto", model="claude-sonnet-5")

    assert resultado.pagina_id == "p0002"
    assert resultado.accuracy_estimate == 0.85
    assert resultado.errors[0]["quote"] == "meuos"
    assert resultado.input_tokens == 1000
    assert resultado.cost_usd == pytest.approx(1000 / 1_000_000 * 2.00 + 200 / 1_000_000 * 10.00)


def test_judge_page_json_invalido_lanza_error(tmp_path):
    imagen = tmp_path / "p0002.jpg"
    imagen.write_bytes(b"\xff\xd8\xff")
    fake = _FakeMessages(create_response=_FakeMessage(
        content=[_FakeTextBlock("esto no es json")],
        usage=_FakeUsage(input_tokens=10, output_tokens=5),
    ))
    client = _FakeClient(fake)

    with pytest.raises(juez.JudgeResponseError):
        juez.judge_page(client, "p0002", imagen, "texto", model="claude-sonnet-5")


def test_judge_page_sin_accuracy_estimate_lanza_error(tmp_path):
    imagen = tmp_path / "p0002.jpg"
    imagen.write_bytes(b"\xff\xd8\xff")
    fake = _FakeMessages(create_response=_FakeMessage(
        content=[_FakeTextBlock(json.dumps({"errors": [], "notes": ""}))],
        usage=_FakeUsage(input_tokens=10, output_tokens=5),
    ))
    client = _FakeClient(fake)

    with pytest.raises(juez.JudgeResponseError):
        juez.judge_page(client, "p0002", imagen, "texto", model="claude-sonnet-5")


def test_estimate_cost_usd_formula():
    costo = juez.estimate_cost_usd(1_000_000, 1_000_000, model="claude-sonnet-5")
    assert costo == pytest.approx(2.00 + 10.00)


def test_paginas_pendientes_salta_ya_juzgadas(tmp_path):
    piloto = tmp_path / "piloto"
    (piloto / "juicios").mkdir(parents=True)
    (piloto / "juicios" / "p0002.json").write_text("{}", encoding="utf-8")
    manifiesto = {
        "paginas": [
            {"pagina_id": "p0002", "imagen": "imagenes/p0002.jpg", "candidato": "candidatos/p0002.txt"},
            {"pagina_id": "p0003", "imagen": "imagenes/p0003.jpg", "candidato": "candidatos/p0003.txt"},
        ]
    }
    pendientes = juez._paginas_pendientes(piloto, manifiesto, forzar=False)
    assert [p["pagina_id"] for p in pendientes] == ["p0003"]


def test_paginas_pendientes_forzar_incluye_todas(tmp_path):
    piloto = tmp_path / "piloto"
    (piloto / "juicios").mkdir(parents=True)
    (piloto / "juicios" / "p0002.json").write_text("{}", encoding="utf-8")
    manifiesto = {
        "paginas": [
            {"pagina_id": "p0002", "imagen": "i", "candidato": "c"},
            {"pagina_id": "p0003", "imagen": "i", "candidato": "c"},
        ]
    }
    pendientes = juez._paginas_pendientes(piloto, manifiesto, forzar=True)
    assert len(pendientes) == 2
