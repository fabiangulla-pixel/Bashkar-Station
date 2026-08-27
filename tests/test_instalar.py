"""tests/test_instalar.py — instalar.py debe reportar con exit code real.

Antes, main() siempre retornaba 0 (implícito) aunque verificar() hubiera
detectado componentes requeridos faltantes. Ejecutar.bat escribía el
marcador .installed sin mirar el código de salida, así que una
instalación a medias en Python 3.14 (paquete sin wheel, red caída a
mitad de descarga...) quedaba marcada como "lista" para siempre y la
app fallaba en cada lanzamiento sin que el instalador volviera a
intentarlo — el reporte real del usuario ("las últimas veces no ha
servido").
"""

import instalar


class TestMainRetornaExitCodeReal:
    def _mockear_pasos(self, monkeypatch, todo_ok):
        monkeypatch.setattr(instalar, "instalar_python", lambda: None)
        monkeypatch.setattr(instalar, "instalar_spacy_model", lambda *a, **k: None)
        monkeypatch.setattr(instalar, "instalar_tesseract_windows", lambda: None)
        monkeypatch.setattr(instalar, "instalar_poppler_windows", lambda: None)
        monkeypatch.setattr(instalar, "instalar_unix", lambda: None)
        monkeypatch.setattr(instalar, "precargar_modelos", lambda: None)
        monkeypatch.setattr(instalar, "verificar", lambda: todo_ok)
        # Sin consola interactiva -> no debe bloquear esperando ENTER
        monkeypatch.setattr(instalar, "_es_interactivo", lambda: False)

    def test_main_retorna_1_si_verificar_falla(self, monkeypatch):
        self._mockear_pasos(monkeypatch, todo_ok=False)
        assert instalar.main() == 1

    def test_main_retorna_0_si_verificar_pasa(self, monkeypatch):
        self._mockear_pasos(monkeypatch, todo_ok=True)
        assert instalar.main() == 0

    def test_main_no_bloquea_en_enter_si_no_es_interactivo(self, monkeypatch):
        """Si se invoca sin consola interactiva (ej. desde otro proceso),
        no debe colgarse esperando ENTER."""
        self._mockear_pasos(monkeypatch, todo_ok=True)

        def _reventar_si_llama(*a, **k):
            raise AssertionError("no debería llamar input() sin consola interactiva")
        monkeypatch.setattr("builtins.input", _reventar_si_llama)

        instalar.main()  # no debe lanzar AssertionError


class TestEsInteractivo:
    def test_no_es_interactivo_bajo_pytest(self):
        """pytest reemplaza sys.stdin por un objeto que no es una consola
        real; _es_interactivo() debe reflejarlo sin reventar."""
        assert instalar._es_interactivo() is False
