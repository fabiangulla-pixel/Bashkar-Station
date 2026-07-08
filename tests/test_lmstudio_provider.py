"""tests/test_lmstudio_provider.py — Proveedor local LM Studio
(servidor OpenAI-compatible en localhost:1234), añadido en paridad con
core/ocr_llm.py, core/ner_engine.py, core/extractor_multimodal.py,
core/costos.py. Nunca requiere un servidor LM Studio real corriendo:
_cliente_lmstudio se monkeypatchea con un stub."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import extractor_multimodal as em  # noqa: E402
from core import ner_engine  # noqa: E402
from core import ocr_llm  # noqa: E402
from core.costos import PROVEEDORES_LOCALES, estimar_lote_ocr  # noqa: E402


# ── Stub de cliente OpenAI-compatible ────────────────────────────────────────

class _RespuestaFalsa:
    def __init__(self, contenido: str, usage: dict | None = None):
        self.choices = [type("Choice", (), {
            "message": type("Msg", (), {"content": contenido})()
        })()]
        self.usage = usage


class _ClienteFalso:
    """Stub de openai.OpenAI: registra la llamada y devuelve una respuesta fija."""

    def __init__(self, respuesta: str):
        self.llamadas: list[dict] = []
        self._respuesta = respuesta

        class _Completions:
            def create(inner_self, **kwargs):
                self.llamadas.append(kwargs)
                return _RespuestaFalsa(self._respuesta)

        class _Chat:
            completions = _Completions()

        self.chat = _Chat()


def _png_real(path: Path):
    from PIL import Image
    Image.new("RGB", (2, 2), (255, 255, 255)).save(path, "PNG")


# ── costos.py: lmstudio es local ─────────────────────────────────────────────

def test_lmstudio_en_proveedores_locales():
    assert "lmstudio" in PROVEEDORES_LOCALES


def test_lmstudio_es_gratis():
    est = estimar_lote_ocr(20, "lmstudio", "gemma-3-12b-it-qat", n_vision=20)
    assert est.es_local is True
    assert est.costo_usd == 0.0
    assert "LOCAL" in est.resumen()


# ── modelos_cargados_lmstudio: health-check /v1/models ───────────────────────

def test_modelos_cargados_servidor_caido_devuelve_vacio(monkeypatch):
    def _falla(*a, **k):
        raise OSError("conexión rechazada")
    monkeypatch.setattr("urllib.request.urlopen", _falla)
    assert ocr_llm.modelos_cargados_lmstudio() == []


def test_modelos_cargados_devuelve_ids(monkeypatch):
    import json
    import io

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    payload = json.dumps({"data": [{"id": "gemma-3-12b-it-qat"}, {"id": "qwen2.5-vl"}]}).encode()
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _Resp(payload))
    assert ocr_llm.modelos_cargados_lmstudio() == ["gemma-3-12b-it-qat", "qwen2.5-vl"]


# ── ocr_llm: corregir_texto / ocr_con_vision con proveedor=lmstudio ──────────

def test_corregir_texto_lmstudio_usa_host_y_modelo(monkeypatch):
    cliente = _ClienteFalso("texto corregido")
    host_usado = {}

    def _fake_cliente(host="http://localhost:1234"):
        host_usado["host"] = host
        return cliente
    monkeypatch.setattr(ocr_llm, "_cliente_lmstudio", _fake_cliente)

    resultado = ocr_llm.corregir_texto(
        "un texto ocr largo " * 20, api_key="http://localhost:9999",
        modelo="mi-modelo-local", proveedor="lmstudio",
    )
    assert resultado.startswith("texto corregido")
    assert host_usado["host"] == "http://localhost:9999"
    assert cliente.llamadas[0]["model"] == "mi-modelo-local"


def test_corregir_texto_lmstudio_default_host_sin_url(monkeypatch):
    cliente = _ClienteFalso("ok")
    host_usado = {}

    def _fake_cliente(host="http://localhost:1234"):
        host_usado["host"] = host
        return cliente
    monkeypatch.setattr(ocr_llm, "_cliente_lmstudio", _fake_cliente)

    ocr_llm.corregir_texto("texto", api_key="no-es-url", proveedor="lmstudio")
    assert host_usado["host"] == "http://localhost:1234"


def test_ocr_con_vision_lmstudio(tmp_path, monkeypatch):
    cliente = _ClienteFalso("transcripción de la página")
    monkeypatch.setattr(ocr_llm, "_cliente_lmstudio", lambda host="http://localhost:1234": cliente)

    img = tmp_path / "p0001.png"
    _png_real(img)
    # modelo=None: igual que hace mejorar_pagina() para proveedores locales sin
    # modelo específico — cae al default "local-model" (no al default de Claude).
    texto = ocr_llm.ocr_con_vision(img, api_key="http://localhost:1234",
                                    modelo=None, proveedor="lmstudio")
    assert texto == "transcripción de la página"
    assert cliente.llamadas[0]["model"] == "local-model"


# ── mejorar_pagina: propaga el modelo local también para lmstudio ───────────
# (bug de regresión: la rama original solo comprobaba proveedor=="ollama" y
# descartaba en silencio el modelo elegido por el usuario para lmstudio).

def test_mejorar_pagina_correccion_propaga_modelo_lmstudio(tmp_path, monkeypatch):
    cliente = _ClienteFalso("texto corregido de sobra para pasar el filtro")
    monkeypatch.setattr(ocr_llm, "_cliente_lmstudio", lambda host="http://localhost:1234": cliente)

    txt = tmp_path / "p0001.txt"
    txt.write_text("texto ocr original " * 10, encoding="utf-8")
    ocr_llm.mejorar_pagina(
        txt_path=txt, img_path=None, api_key="http://localhost:1234",
        confianza_tesseract=10, proveedor="lmstudio", modelo_ollama="mi-modelo-elegido",
    )
    assert cliente.llamadas[0]["model"] == "mi-modelo-elegido"


# ── ner_engine: validar_con_llm con proveedor=lmstudio ───────────────────────

def test_validar_con_llm_lmstudio(monkeypatch):
    raw = '{"personas": ["Alfonso López"], "notas_ocr": ""}'
    cliente = _ClienteFalso(raw)
    monkeypatch.setattr(ocr_llm, "_cliente_lmstudio", lambda host="http://localhost:1234": cliente)

    resultado = ner_engine.validar_con_llm(
        "texto de prueba con Alfonso López", api_key="http://localhost:1234",
        modelo="mi-modelo", proveedor="lmstudio",
    )
    assert "Alfonso López" in resultado.get("personas", [])
    assert cliente.llamadas[0]["model"] == "mi-modelo"


def test_pipeline_ner_lmstudio_no_revienta_sin_spacy(monkeypatch):
    raw = '{"personas": [], "notas_ocr": ""}'
    cliente = _ClienteFalso(raw)
    monkeypatch.setattr(ocr_llm, "_cliente_lmstudio", lambda host="http://localhost:1234": cliente)

    resultado = ner_engine.pipeline_ner(
        "un texto cualquiera de prueba", nlp=None, api_key="http://localhost:1234",
        usar_roberta=False, proveedor_llm="lmstudio", modelo_ollama="mi-modelo",
    )
    assert isinstance(resultado, dict)


# ── extractor_multimodal: extraer_pagina con proveedor=lmstudio ──────────────

def test_extraer_pagina_lmstudio_mock(tmp_path, monkeypatch):
    raw = (
        '{"articulo_principal": {"titulo": "T", "autor": "A", "seccion": "s", '
        '"cuerpo": "c"}, "fotos": [], "publicidad": []}'
    )
    cliente = _ClienteFalso(raw)
    monkeypatch.setattr(ocr_llm, "_cliente_lmstudio", lambda host="http://localhost:1234": cliente)

    img = tmp_path / "p0020.png"
    _png_real(img)
    datos = em.extraer_pagina(img, api_key="http://localhost:1234", proveedor="lmstudio")
    assert datos["articulo_principal"]["autor"] == "A"
    assert cliente.llamadas[0]["model"] == "local-model"
