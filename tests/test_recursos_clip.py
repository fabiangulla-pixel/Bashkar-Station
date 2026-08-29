"""
tests/test_recursos_clip.py — Reparto de CPU y carga única de CLIP.

Estos dos módulos existen por una razón medible: en un Ryzen 5 5500U sin GPU,
PyTorch tomaba los 12 hilos lógicos y dejaba la interfaz sin repintar, y cinco
rutas distintas cargaban el mismo CLIP por separado (600 MB cada una, y
`clasificar_imagen` una vez por imagen). Lo que se verifica aquí es justo eso:
que se reservan núcleos y que el modelo se carga UNA vez.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import clip_local, recursos, visual_classifier, visual_search  # noqa: E402

# Nota para quien toque este archivo: los módulos de arriba se importan aquí y
# no dentro de los tests a propósito. Varios tests parchean `sys.modules`, y al
# deshacer el parche `patch.dict` borra lo que se hubiera importado mientras
# tanto — incluido numpy. Reimportar numpy en el mismo proceso revienta con
# "cannot load module more than once per process", porque su módulo de
# extensión en C no se puede inicializar dos veces. Importándolos antes de
# cualquier parche, ya están en sys.modules y el restaurado los respeta.
#
# Por lo mismo, para simular una dependencia ausente se pone `None` en
# sys.modules (CPython lanza ImportError al encontrarlo) en vez de parchear
# `builtins.__import__`, que rompe el import de cualquier otra cosa.


# ─────────────────────────── core/recursos.py ────────────────────────────

class TestHilosRecomendados:

    def test_reserva_nucleos_para_la_interfaz(self):
        """12 hilos lógicos → 6 físicos estimados → 5 usables. Nunca los 12."""
        with patch("os.cpu_count", return_value=12):
            assert recursos.hilos_recomendados() == 5

    def test_nunca_devuelve_cero_ni_negativo(self):
        """En una máquina de 1 o 2 hilos la resta no puede dejarlo en cero."""
        for logicos in (1, 2, 3):
            with patch("os.cpu_count", return_value=logicos):
                assert recursos.hilos_recomendados() >= 1

    def test_cpu_count_none_no_revienta(self):
        """os.cpu_count() puede devolver None en entornos exóticos."""
        with patch("os.cpu_count", return_value=None):
            assert recursos.hilos_recomendados() == 1

    def test_override_por_variable_de_entorno(self):
        with patch.dict(os.environ, {recursos.VARIABLE_OVERRIDE: "3"}):
            with patch("os.cpu_count", return_value=12):
                assert recursos.hilos_recomendados() == 3

    @pytest.mark.parametrize("valor", ["", "  ", "abc", "0", "-4", "3.5"])
    def test_override_inservible_cae_en_la_heuristica(self, valor):
        """Un valor mal escrito no puede dejar la app sin CPU ni tumbarla."""
        with patch.dict(os.environ, {recursos.VARIABLE_OVERRIDE: valor}):
            with patch("os.cpu_count", return_value=12):
                assert recursos.hilos_recomendados() == 5


class TestAplicarLimitesCPU:

    def test_fija_las_variables_de_openmp(self):
        entorno = {}
        with patch.dict(os.environ, entorno, clear=True):
            n = recursos.aplicar_limites_cpu(4)
            assert n == 4
            assert os.environ["OMP_NUM_THREADS"] == "4"
            assert os.environ["MKL_NUM_THREADS"] == "4"
            assert os.environ["OPENBLAS_NUM_THREADS"] == "4"

    def test_respeta_lo_que_el_usuario_ya_fijo(self):
        """Si alguien exportó OMP_NUM_THREADS a mano, manda su decisión."""
        with patch.dict(os.environ, {"OMP_NUM_THREADS": "2"}, clear=True):
            recursos.aplicar_limites_cpu(8)
            assert os.environ["OMP_NUM_THREADS"] == "2"

    def test_sin_argumento_usa_la_heuristica(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("os.cpu_count", return_value=8):
                assert recursos.aplicar_limites_cpu() == 3   # 8//2 - 1

    def test_fija_mitigacion_del_segfault_torch_tokenizers(self):
        """Sesión 62/63: con OMP_NUM_THREADS fijado, cargar el modelo BERT de
        core/ner_roberta_local.py segfaulteaba de forma reproducible.
        aplicar_limites_cpu() debe dejar puestas las dos mitigaciones
        conocidas para esa familia de crash nativo, ANTES de que nada
        importe torch/tokenizers."""
        with patch.dict(os.environ, {}, clear=True):
            recursos.aplicar_limites_cpu(4)
            assert os.environ["TOKENIZERS_PARALLELISM"] == "false"
            assert os.environ["KMP_DUPLICATE_LIB_OK"] == "TRUE"

    def test_respeta_mitigacion_que_el_usuario_ya_fijo(self):
        with patch.dict(os.environ, {"TOKENIZERS_PARALLELISM": "true"}, clear=True):
            recursos.aplicar_limites_cpu(4)
            assert os.environ["TOKENIZERS_PARALLELISM"] == "true"


class TestLimitarHilosTorch:

    def test_sin_torch_devuelve_none_sin_lanzar(self):
        """En el .exe compilado PyTorch se excluye a propósito."""
        with patch.dict(sys.modules, {"torch": None}):
            assert recursos.limitar_hilos_torch() is None

    def test_llama_a_set_num_threads(self):
        falso = MagicMock()
        with patch.dict(sys.modules, {"torch": falso}):
            assert recursos.limitar_hilos_torch(5) == 5
            falso.set_num_threads.assert_called_once_with(5)

    def test_interop_ya_iniciado_no_tumba_el_ocr(self):
        """set_num_interop_threads lanza si ya hubo trabajo paralelo."""
        falso = MagicMock()
        falso.set_num_interop_threads.side_effect = RuntimeError("ya iniciado")
        with patch.dict(sys.modules, {"torch": falso}):
            assert recursos.limitar_hilos_torch(5) == 5   # no propaga


# ─────────────────────── core/ocr_churro.py (recursos) ───────────────────

class TestChurroCabeEnLaMemoria:
    """Los dos ajustes que hacen a CHURRO ejecutable en un portátil.

    Medido el 2026-08-12: en `float32` el modelo pide 11,97 GB y la carga muere
    con *segmentation fault* en una máquina de 20 GB con el navegador abierto
    (~6,5 GB libres). No era lentitud: no cabía.
    """

    def test_por_defecto_carga_en_bfloat16(self):
        """float32 no cabe; float16 desborda a NaN en CPU. Queda bfloat16."""
        from core import ocr_churro
        falso = MagicMock()
        with patch.dict(os.environ, {}, clear=True):
            assert ocr_churro._dtype(falso) is falso.bfloat16

    @pytest.mark.parametrize("valor,esperado", [
        ("float32", "float32"), ("fp32", "float32"),
        ("float16", "float16"), ("fp16", "float16"),
    ])
    def test_la_variable_de_entorno_manda(self, valor, esperado):
        """Una máquina con RAM de sobra puede volver a la precisión completa."""
        from core import ocr_churro
        falso = MagicMock()
        with patch.dict(os.environ, {"BASHKAR_CHURRO_DTYPE": valor}):
            assert ocr_churro._dtype(falso) is getattr(falso, esperado)

    def test_un_dtype_inservible_no_tumba_el_ocr(self):
        from core import ocr_churro
        falso = MagicMock()
        with patch.dict(os.environ, {"BASHKAR_CHURRO_DTYPE": "cuadruple"}):
            assert ocr_churro._dtype(falso) is falso.bfloat16

    def test_el_techo_de_pixeles_es_muy_inferior_al_de_qwen(self):
        """1.280 tokens visuales frente a los 16.384 que trae por defecto."""
        from core import ocr_churro
        assert ocr_churro.MAX_PIXELS_POR_DEFECTO < 12_845_056 / 10
        assert ocr_churro.MIN_PIXELS_POR_DEFECTO < ocr_churro.MAX_PIXELS_POR_DEFECTO

    @pytest.mark.parametrize("valor", ["", "  ", "abc", "0", "-1", "1e6"])
    def test_un_limite_de_pixeles_inservible_cae_en_el_defecto(self, valor):
        from core import ocr_churro
        with patch.dict(os.environ, {"BASHKAR_CHURRO_MAX_PIXELS": valor}):
            assert ocr_churro._limite_pixeles(
                "BASHKAR_CHURRO_MAX_PIXELS",
                ocr_churro.MAX_PIXELS_POR_DEFECTO) == ocr_churro.MAX_PIXELS_POR_DEFECTO

    def test_un_limite_valido_se_respeta(self):
        from core import ocr_churro
        with patch.dict(os.environ, {"BASHKAR_CHURRO_MAX_PIXELS": "500000"}):
            assert ocr_churro._limite_pixeles(
                "BASHKAR_CHURRO_MAX_PIXELS", 1_003_520) == 500_000


class TestCacheAMediasNoCuentaComoDescargado:
    """Una descarga incompleta no puede parecer completa.

    Caso real del 2026-08-12: la caché tenía `model-00002-of-00002.safetensors`
    y le faltaban el fragmento 1 (5 GB) y el índice. `esta_descargado()` decía
    True, transformers intentaba mapear los pesos ausentes y el proceso moría
    con *segmentation fault* — no una excepción, la aplicación entera cerrándose
    y llevándose el trabajo sin guardar.
    """

    def _cache(self, tmp_path, nombres, con_indice=None):
        carpeta = tmp_path / "hub" / "models--stanford-oval--churro-3B" / "snapshots" / "abc"
        carpeta.mkdir(parents=True)
        for n in nombres:
            (carpeta / n).write_bytes(b"x" * 100)
        if con_indice is not None:
            import json
            (carpeta / "model.safetensors.index.json").write_text(
                json.dumps({"weight_map": {f"w{i}": n for i, n in enumerate(con_indice)}}),
                encoding="utf-8")
        return tmp_path

    def _mirar(self, tmp_path, monkeypatch):
        from core import ocr_churro
        monkeypatch.setattr(ocr_churro, "_dir_cache", lambda: tmp_path)
        monkeypatch.setattr(ocr_churro, "_carpeta_modelo_local", lambda: None)
        return ocr_churro.esta_descargado()

    def test_falta_un_fragmento_y_el_indice(self, tmp_path, monkeypatch):
        """El caso exacto que provocó el segfault."""
        raiz = self._cache(tmp_path, ["model-00002-of-00002.safetensors"])
        assert self._mirar(raiz, monkeypatch) is False

    def test_estan_todos_los_fragmentos_sin_indice(self, tmp_path, monkeypatch):
        """Sin índice pero completo: los nombres bastan para saberlo."""
        raiz = self._cache(tmp_path, ["model-00001-of-00002.safetensors",
                                      "model-00002-of-00002.safetensors"])
        assert self._mirar(raiz, monkeypatch) is True

    def test_modelo_de_un_solo_archivo_sigue_valiendo(self, tmp_path, monkeypatch):
        """No romper el caso legítimo: hay modelos sin fragmentar."""
        raiz = self._cache(tmp_path, ["model.safetensors"])
        assert self._mirar(raiz, monkeypatch) is True

    def test_con_indice_completo(self, tmp_path, monkeypatch):
        piezas = ["model-00001-of-00002.safetensors", "model-00002-of-00002.safetensors"]
        raiz = self._cache(tmp_path, piezas, con_indice=piezas)
        assert self._mirar(raiz, monkeypatch) is True

    def test_con_indice_y_un_fragmento_de_menos(self, tmp_path, monkeypatch):
        piezas = ["model-00001-of-00002.safetensors", "model-00002-of-00002.safetensors"]
        raiz = self._cache(tmp_path, piezas[:1], con_indice=piezas)
        assert self._mirar(raiz, monkeypatch) is False

    def test_carpeta_vacia(self, tmp_path, monkeypatch):
        raiz = self._cache(tmp_path, [])
        assert self._mirar(raiz, monkeypatch) is False


# ─────────────────────────── core/clip_local.py ──────────────────────────

class TestClipLocal:

    def setup_method(self):
        clip_local.cargar.cache_clear()

    def teardown_method(self):
        clip_local.cargar.cache_clear()

    def test_carga_una_sola_vez_aunque_se_pida_muchas(self):
        """El fallo que motivó el módulo: 600 MB releídos por cada llamada."""
        modelo, proc = MagicMock(), MagicMock()
        falso = MagicMock()
        falso.CLIPModel.from_pretrained.return_value = modelo
        falso.CLIPProcessor.from_pretrained.return_value = proc

        with patch.dict(sys.modules, {"transformers": falso}):
            primero = clip_local.cargar()
            for _ in range(10):
                clip_local.cargar()

        assert falso.CLIPModel.from_pretrained.call_count == 1
        assert primero[0] is modelo

    def test_devuelve_siempre_la_misma_instancia(self):
        """Compartir la instancia es el punto: si no, no se ahorra memoria."""
        falso = MagicMock()
        with patch.dict(sys.modules, {"transformers": falso}):
            assert clip_local.cargar() is clip_local.cargar()

    def test_el_modelo_vuelve_en_modo_evaluacion(self):
        """Sin eval() el dropout daría embeddings distintos por llamada."""
        modelo = MagicMock()
        falso = MagicMock()
        falso.CLIPModel.from_pretrained.return_value = modelo
        with patch.dict(sys.modules, {"transformers": falso}):
            clip_local.cargar()
        modelo.eval.assert_called_once()

    def test_sin_transformers_el_mensaje_dice_que_instalar(self):
        """None en sys.modules hace que CPython lance ImportError al importar."""
        with patch.dict(sys.modules, {"transformers": None}):
            with pytest.raises(ImportError, match="pip install"):
                clip_local.cargar()

    def test_liberar_permite_recargar(self):
        falso = MagicMock()
        with patch.dict(sys.modules, {"transformers": falso}):
            clip_local.cargar()
            clip_local.liberar()
            clip_local.cargar()
        assert falso.CLIPModel.from_pretrained.call_count == 2

    def test_disponible_no_carga_el_modelo(self):
        """Preguntar si se puede usar no debe costar 600 MB."""
        falso = MagicMock()
        with patch.dict(sys.modules, {"transformers": falso}):
            clip_local.disponible()
        falso.CLIPModel.from_pretrained.assert_not_called()


class TestRutasVisualesCompartenElModelo:
    """Las tres rutas visuales deben acabar en el mismo cargador cacheado."""

    def setup_method(self):
        clip_local.cargar.cache_clear()

    def teardown_method(self):
        clip_local.cargar.cache_clear()

    def test_visual_search_delega_en_clip_local(self):
        with patch.object(clip_local, "cargar",
                          return_value=("m", "p")) as cargador:
            assert visual_search._cargar_clip() == ("m", "p")
        cargador.assert_called_once()

    def test_clasificar_imagen_no_recarga_pesos_por_imagen(self):
        """visual_classifier.clasificar_imagen llamaba a from_pretrained cada vez."""
        with patch.object(clip_local, "cargar",
                          return_value=("m", "p")) as cargador:
            with patch.object(visual_classifier, "_clasificar_clip",
                              return_value={"categoria": "x"}):
                for _ in range(5):
                    visual_classifier.clasificar_imagen("falsa.png")
        assert cargador.call_count == 5          # llamadas al cargador…
        # …pero el cargador real es lru_cache, así que los pesos se leen 1 vez.
