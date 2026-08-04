"""Tests de las rutas nuevas: CHURRO-3B y PERO-OCR.

Ninguno descarga modelos ni toca la red: se comprueba la lógica de
disponibilidad, la estimación previa y el manejo de errores del lote, que es
donde de verdad se rompen estas integraciones. La inferencia real de un modelo
de 3B en CPU tarda minutos por página y no cabe en una suite de tests.
"""

from __future__ import annotations

import sys
import types

import pytest

from core import benchmark_ocr, ocr_churro, ocr_pero


def _sin(monkeypatch, *ausentes):
    """Simula que faltan ciertos módulos.

    Se parchea el helper `_hay_modulo` del propio módulo, NUNCA
    `importlib.util.find_spec`: parchear la maquinaria de importación de forma
    global rompe a pytest por dentro (llega a provocar un access violation al
    crear los directorios temporales de los fixtures).
    """
    monkeypatch.setattr(ocr_churro, "_hay_modulo",
                        lambda nombre: nombre not in ausentes)


class TestChurroDisponibilidad:
    def test_reporta_motivo_accionable_si_falta_torch(self, monkeypatch):
        _sin(monkeypatch, "torch")
        monkeypatch.setattr(ocr_churro, "_esta_congelado", lambda: False)
        motivo = ocr_churro.motivo_no_disponible()
        assert motivo is not None
        assert "pip install torch" in motivo      # dice QUÉ hacer, no solo que falla
        assert not ocr_churro.disponible()

    def test_en_el_exe_no_aconseja_pip_porque_seria_imposible(self, monkeypatch):
        """En un .exe congelado torch está excluido y no hay pip dentro.

        Decir «pip install torch» ahí sería un consejo que el usuario no puede
        seguir. El mensaje debe mandarlo al código fuente.
        """
        _sin(monkeypatch, "torch")
        monkeypatch.setattr(ocr_churro, "_esta_congelado", lambda: True)
        motivo = ocr_churro.motivo_no_disponible()
        assert "pip install" not in motivo
        assert "código fuente" in motivo

    def test_reporta_motivo_si_falta_transformers(self, monkeypatch):
        _sin(monkeypatch, "transformers")
        monkeypatch.setattr(ocr_churro, "_esta_congelado", lambda: False)
        assert "transformers" in ocr_churro.motivo_no_disponible()

    def test_hay_modulo_tolera_spec_none(self, monkeypatch):
        """`find_spec` lanza ValueError si __spec__ es None (pasa en un .exe)."""
        import importlib.util
        monkeypatch.setattr(
            importlib.util, "find_spec",
            lambda *a, **k: (_ for _ in ()).throw(ValueError("__spec__ is None")))
        monkeypatch.setitem(sys.modules, "modulo_de_prueba", types.ModuleType("x"))
        assert ocr_churro._hay_modulo("modulo_de_prueba") is True
        assert ocr_churro._hay_modulo("modulo_que_no_existe_jamas") is False

    def test_detecta_transformers_sin_soporte_qwen(self, monkeypatch):
        """Una versión vieja de transformers no trae la clase de Qwen2.5-VL."""
        monkeypatch.setattr(ocr_churro, "_soporta_qwen", lambda: (False, None))
        motivo = ocr_churro.motivo_no_disponible()
        assert motivo is not None
        assert "Qwen2.5-VL" in motivo

    def test_transformers_roto_se_reporta_sin_reventar(self, monkeypatch):
        monkeypatch.setattr(ocr_churro, "_soporta_qwen",
                            lambda: (False, "DLL load failed"))
        assert "DLL load failed" in ocr_churro.motivo_no_disponible()

    def test_todo_presente_devuelve_none(self, monkeypatch):
        monkeypatch.setattr(ocr_churro, "_hay_modulo", lambda n: True)
        monkeypatch.setattr(ocr_churro, "_soporta_qwen", lambda: (True, None))
        assert ocr_churro.motivo_no_disponible() is None
        assert ocr_churro.disponible() is True

    def test_esta_descargado_no_falla_sin_cache(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HF_HOME", str(tmp_path))
        assert ocr_churro.esta_descargado() is False


class TestChurroEstimacion:
    def test_estima_tiempo_y_costo_cero(self):
        est = ocr_churro.estimar_tiempo(10)
        assert est["paginas"] == 10
        assert est["costo_usd"] == 0.0           # es local: no cuesta dinero
        assert est["minutos"] > 0
        assert "min" in est["texto"]

    def test_avisa_de_la_descarga_pendiente(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HF_HOME", str(tmp_path))
        assert ocr_churro.estimar_tiempo(1)["descarga_pendiente_gb"] == 7.0

    def test_cero_paginas(self):
        assert ocr_churro.estimar_tiempo(0)["segundos"] == 0


class TestChurroLote:
    def test_una_pagina_que_falla_no_aborta_el_lote(self, monkeypatch):
        def falso_ocr(imagen, **kwargs):
            if "mala" in str(imagen):
                raise RuntimeError("modelo no cargado")
            return "texto reconocido"

        monkeypatch.setattr(ocr_churro, "ocr_pagina", falso_ocr)
        res = ocr_churro.ocr_lote(["p0001.png", "mala.png", "p0003.png"])
        assert res["p0001"] == "texto reconocido"
        assert res["mala"] == ""                 # error total, no ausencia
        assert res["p0003"] == "texto reconocido"

    def test_el_callback_recibe_el_avance(self, monkeypatch):
        monkeypatch.setattr(ocr_churro, "ocr_pagina", lambda *a, **k: "ok")
        avisos = []
        ocr_churro.ocr_lote(["a.png", "b.png"],
                            callback=lambda i, t, n, s: avisos.append((i, t, n)))
        assert avisos == [(1, 2, "a"), (2, 2, "b")]

    def test_el_callback_tambien_avisa_de_los_errores(self, monkeypatch):
        def siempre_falla(*a, **k):
            raise RuntimeError("sin memoria")

        monkeypatch.setattr(ocr_churro, "ocr_pagina", siempre_falla)
        avisos = []
        ocr_churro.ocr_lote(["a.png"], callback=lambda i, t, n, s: avisos.append(n))
        assert "ERROR" in avisos[0]

    def test_liberar_no_falla_sin_modelo_cargado(self):
        ocr_churro.liberar()


class TestPero:
    def test_motivo_si_no_esta_instalado(self):
        """pero-ocr no es dependencia del proyecto: debe degradar con gracia."""
        motivo = ocr_pero.motivo_no_disponible()
        if motivo is not None:
            assert "pip install pero-ocr" in motivo
            assert not ocr_pero.disponible()

    def test_exige_config_ini(self, monkeypatch):
        monkeypatch.setattr(ocr_pero, "motivo_no_disponible",
                            ocr_pero.motivo_no_disponible)
        import importlib.util
        if importlib.util.find_spec("pero_ocr") is None:
            pytest.skip("pero-ocr no instalado en este entorno")
        assert "config.ini" in (ocr_pero.motivo_no_disponible(None) or "")

    def test_config_inexistente_se_reporta(self, tmp_path):
        import importlib.util
        if importlib.util.find_spec("pero_ocr") is None:
            pytest.skip("pero-ocr no instalado en este entorno")
        motivo = ocr_pero.motivo_no_disponible(tmp_path / "no_existe.ini")
        assert "No existe" in motivo

    def test_rutas_probables_no_revienta(self):
        assert isinstance(ocr_pero.rutas_config_probables(), list)

    def test_estimacion_mucho_mas_rapida_que_churro(self):
        """PERO es una cadena clásica; CHURRO un VLM de 3B. Órdenes distintos."""
        assert (ocr_pero.estimar_tiempo(10)["segundos"]
                < ocr_churro.estimar_tiempo(10)["segundos"])
        assert ocr_pero.estimar_tiempo(10)["costo_usd"] == 0.0

    def test_lote_con_motor_falso(self, monkeypatch):
        monkeypatch.setattr(ocr_pero, "_cargar_motor", lambda c: object())
        monkeypatch.setattr(ocr_pero, "ocr_pagina",
                            lambda ruta, cfg, motor=None: f"texto de {ruta}")
        res = ocr_pero.ocr_lote(["p1.png", "p2.png"], "config.ini")
        assert set(res) == {"p1", "p2"}


class TestIntegracionConBenchmark:
    def test_las_salidas_de_las_rutas_alimentan_el_benchmark(self, monkeypatch):
        """El contrato entre las rutas y benchmark_ocr es {nombre: texto}."""
        monkeypatch.setattr(ocr_churro, "ocr_pagina",
                            lambda *a, **k: "la guerra civil espanola")
        salida = ocr_churro.ocr_lote(["p0001.png"])

        referencias = {"p0001": "la guerra civil española"}
        resultado = benchmark_ocr.comparar(referencias, salida, ruta="churro")
        assert resultado.paginas == 1
        assert resultado.cer == 0.0        # las tildes no penalizan por defecto
        assert resultado.calidad == "casi limpio"
