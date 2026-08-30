"""tests/test_hf_offline_cacheado.py — _forzar_offline_si_ya_cacheado().

Regresión de un reporte real del usuario: "por qué siempre instala cosas
cada que abro Bashkar, no debería quedar guardado". Causa: ner_roberta_local
y embeddings_local llamaban from_pretrained()/SentenceTransformer() sin
HF_HUB_OFFLINE, así que transformers golpeaba el Hub para revalidar el
ETag en cada arranque aunque el modelo ya estuviera en caché — visible
como actividad de red/"instalación" cada vez. Mismo patrón que
ocr_churro.py ya tenía para CHURRO, faltaba aplicarlo aquí.

Sesión 63: el chequeo de caché se reescribió con pathlib puro (sin importar
huggingface_hub) porque importar esa librería solo para preguntar "¿está
cacheado?" congelaba su propia constante interna HF_HUB_OFFLINE=False antes
de que este código alcanzara a fijar la variable de entorno — el bug real
detrás de un segfault reproducible en ner_roberta_local.py (ver
tests/test_ner_engine.py::TestOfflineForzadoAntesDeImportarTransformers).
embeddings_local.py tiene el mismo patrón y se arregló igual.
"""

import os
from pathlib import Path

import pytest

import core.embeddings_local as embeddings_local
import core.ner_roberta_local as ner_roberta_local

MODULOS = [ner_roberta_local, embeddings_local]


@pytest.fixture(autouse=True)
def _limpiar_env(monkeypatch):
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    monkeypatch.delenv("HUGGINGFACE_HUB_CACHE", raising=False)
    monkeypatch.delenv("HF_HOME", raising=False)


def _crear_cache_falsa(tmp_path: Path, modelo_id: str) -> None:
    carpeta = "models--" + modelo_id.replace("/", "--")
    snapshot = tmp_path / carpeta / "snapshots" / "abc123"
    snapshot.mkdir(parents=True)
    (snapshot / "config.json").write_text("{}", encoding="utf-8")


class TestForzarOfflineSiYaCacheado:
    @pytest.mark.parametrize("modulo", MODULOS)
    def test_pone_offline_si_esta_cacheado(self, modulo, tmp_path, monkeypatch):
        monkeypatch.setenv("HUGGINGFACE_HUB_CACHE", str(tmp_path))
        _crear_cache_falsa(tmp_path, "algun/modelo")
        modulo._forzar_offline_si_ya_cacheado("algun/modelo")
        assert os.environ.get("HF_HUB_OFFLINE") == "1"

    @pytest.mark.parametrize("modulo", MODULOS)
    def test_no_pone_offline_si_no_esta_cacheado(self, modulo, tmp_path, monkeypatch):
        monkeypatch.setenv("HUGGINGFACE_HUB_CACHE", str(tmp_path))
        modulo._forzar_offline_si_ya_cacheado("algun/modelo")
        assert "HF_HUB_OFFLINE" not in os.environ

    @pytest.mark.parametrize("modulo", MODULOS)
    def test_quita_offline_de_otro_modelo_si_este_no_esta_cacheado(self, modulo, tmp_path, monkeypatch):
        """Si un modelo A ya cacheado puso HF_HUB_OFFLINE=1, un modelo B
        NO cacheado en el mismo proceso no debe quedar bloqueado sin red
        para su primera descarga real."""
        monkeypatch.setenv("HUGGINGFACE_HUB_CACHE", str(tmp_path))
        os.environ["HF_HUB_OFFLINE"] = "1"
        modulo._forzar_offline_si_ya_cacheado("modelo/no_cacheado_todavia")
        assert "HF_HUB_OFFLINE" not in os.environ

    @pytest.mark.parametrize("modulo", MODULOS)
    def test_no_revienta_si_la_cache_es_illegible(self, modulo, monkeypatch):
        """Una ruta de caché inaccesible (permisos, disco de red caído) no
        puede tumbar la carga del modelo."""
        def _reventar(self, *a, **k):
            raise OSError("disco de red caído")
        monkeypatch.setattr(Path, "glob", _reventar)
        modulo._forzar_offline_si_ya_cacheado("algun/modelo")  # no debe lanzar

    @pytest.mark.parametrize("modulo", MODULOS)
    def test_ruta_de_cache_respeta_huggingface_hub_cache_sobre_hf_home(self, modulo, tmp_path, monkeypatch):
        monkeypatch.setenv("HF_HOME", str(tmp_path / "no-deberia-usarse"))
        monkeypatch.setenv("HUGGINGFACE_HUB_CACHE", str(tmp_path / "cache-explicita"))
        ruta = modulo._ruta_cache_hf("org/modelo")
        assert ruta == tmp_path / "cache-explicita" / "models--org--modelo"

    @pytest.mark.parametrize("modulo", MODULOS)
    def test_offline_forzado_al_importar_el_modulo(self, modulo):
        """El fix real: la llamada debe ocurrir a nivel de módulo (al
        importar), no dentro de la función que carga el modelo — de lo
        contrario `from transformers/sentence_transformers import ...` ya
        arrastró huggingface_hub y congeló su constante interna antes de que
        el offline se alcance a fijar. Verificado leyendo el código fuente:
        la llamada a _forzar_offline_si_ya_cacheado debe estar fuera de
        cualquier `def`."""
        import ast
        import inspect

        codigo = inspect.getsource(modulo)
        arbol = ast.parse(codigo)
        llamadas_a_nivel_modulo = [
            n for n in arbol.body
            if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
            and getattr(n.value.func, "id", "") == "_forzar_offline_si_ya_cacheado"
        ]
        assert llamadas_a_nivel_modulo, (
            f"{modulo.__name__} no llama a _forzar_offline_si_ya_cacheado() a "
            "nivel de módulo — con eso dentro de una función que primero "
            "importa transformers/sentence_transformers, fijar HF_HUB_OFFLINE "
            "llega tarde y no tiene efecto"
        )
