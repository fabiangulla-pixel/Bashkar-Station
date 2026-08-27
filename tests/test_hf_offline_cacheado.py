"""tests/test_hf_offline_cacheado.py — _forzar_offline_si_ya_cacheado().

Regresión de un reporte real del usuario: "por qué siempre instala cosas
cada que abro Bashkar, no debería quedar guardado". Causa: ner_roberta_local
y embeddings_local llamaban from_pretrained()/SentenceTransformer() sin
HF_HUB_OFFLINE, así que transformers golpeaba el Hub para revalidar el
ETag en cada arranque aunque el modelo ya estuviera en caché — visible
como actividad de red/"instalación" cada vez. Mismo patrón que
ocr_churro.py ya tenía para CHURRO, faltaba aplicarlo aquí.
"""

import os

import pytest

import core.embeddings_local as embeddings_local
import core.ner_roberta_local as ner_roberta_local

MODULOS = [ner_roberta_local, embeddings_local]


@pytest.fixture(autouse=True)
def _limpiar_env(monkeypatch):
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)


class TestForzarOfflineSiYaCacheado:
    @pytest.mark.parametrize("modulo", MODULOS)
    def test_pone_offline_si_esta_cacheado(self, modulo, monkeypatch):
        monkeypatch.setattr(
            "huggingface_hub.try_to_load_from_cache",
            lambda *a, **k: "/ruta/falsa/config.json",
        )
        modulo._forzar_offline_si_ya_cacheado("algun/modelo")
        assert os.environ.get("HF_HUB_OFFLINE") == "1"

    @pytest.mark.parametrize("modulo", MODULOS)
    def test_no_pone_offline_si_no_esta_cacheado(self, modulo, monkeypatch):
        monkeypatch.setattr(
            "huggingface_hub.try_to_load_from_cache",
            lambda *a, **k: None,
        )
        modulo._forzar_offline_si_ya_cacheado("algun/modelo")
        assert "HF_HUB_OFFLINE" not in os.environ

    @pytest.mark.parametrize("modulo", MODULOS)
    def test_quita_offline_de_otro_modelo_si_este_no_esta_cacheado(self, modulo, monkeypatch):
        """Si un modelo A ya cacheado puso HF_HUB_OFFLINE=1, un modelo B
        NO cacheado en el mismo proceso no debe quedar bloqueado sin red
        para su primera descarga real."""
        os.environ["HF_HUB_OFFLINE"] = "1"
        monkeypatch.setattr(
            "huggingface_hub.try_to_load_from_cache",
            lambda *a, **k: None,
        )
        modulo._forzar_offline_si_ya_cacheado("modelo/no_cacheado_todavia")
        assert "HF_HUB_OFFLINE" not in os.environ

    @pytest.mark.parametrize("modulo", MODULOS)
    def test_no_revienta_si_huggingface_hub_falla(self, modulo, monkeypatch):
        def _reventar(*a, **k):
            raise RuntimeError("caché corrupta")
        monkeypatch.setattr("huggingface_hub.try_to_load_from_cache", _reventar)
        modulo._forzar_offline_si_ya_cacheado("algun/modelo")  # no debe lanzar
