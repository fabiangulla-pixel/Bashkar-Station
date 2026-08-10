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
