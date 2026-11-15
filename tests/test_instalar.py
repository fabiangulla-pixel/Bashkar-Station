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


# ── Hito C2 de PLAN_MVP.md ────────────────────────────────────────────────────
# instalar.py tenía su propia lista de paquetes, sin versiones fijas, distinta
# de requirements.txt: en una instalación limpia faltaban 8 paquetes (anthropic,
# google-generativeai, accelerate, wordcloud, python-louvain, spylls, fastapi,
# uvicorn) y las versiones no coincidían con las que pasan la suite.

class TestInstalaDesdeElLock:
    def _capturar_pip(self, monkeypatch):
        llamadas = []
        monkeypatch.setattr(instalar.subprocess, "check_call",
                            lambda cmd, *a, **k: llamadas.append(list(map(str, cmd))) or 0)
        return llamadas

    def test_instala_las_versiones_exactas_del_lock(self, monkeypatch):
        llamadas = self._capturar_pip(monkeypatch)
        monkeypatch.setattr(instalar.platform, "system", lambda: "Windows")
        instalar.instalar_python()
        lock = str(instalar.APP_DIR / "requirements.lock.txt")
        assert any("-r" in c and lock in c for c in llamadas), llamadas

    def test_el_lock_trae_los_ocho_paquetes_que_faltaban(self):
        texto = (instalar.APP_DIR / "requirements.lock.txt").read_text(encoding="utf-8").lower()
        for p in ("anthropic==", "google-generativeai==", "accelerate==", "wordcloud==",
                  "python-louvain==", "spylls==", "fastapi==", "uvicorn=="):
            assert p in texto, p

    def test_en_linux_torch_viene_del_indice_solo_cpu(self, monkeypatch):
        llamadas = self._capturar_pip(monkeypatch)
        monkeypatch.setattr(instalar.platform, "system", lambda: "Linux")
        instalar.instalar_python()
        torch_cmd = [c for c in llamadas if any(x.startswith("torch==") for x in c)]
        assert torch_cmd and "https://download.pytorch.org/whl/cpu" in torch_cmd[0]

    def test_kraken_no_se_instala_por_defecto(self, monkeypatch):
        # pip install kraken puede cambiar torch y romper el lock.
        llamadas = self._capturar_pip(monkeypatch)
        monkeypatch.setattr(instalar.platform, "system", lambda: "Windows")
        instalar.instalar_python()
        assert not any("kraken" in " ".join(c) for c in llamadas)


class TestVersionDePython:
    def test_python_no_soportado_se_detiene_sin_instalar(self, monkeypatch):
        llamados = []
        monkeypatch.setattr(instalar, "PYV", (3, 14, 7))
        monkeypatch.setattr(instalar, "instalar_python", lambda: llamados.append(1))
        monkeypatch.setattr(instalar, "_es_interactivo", lambda: False)
        assert instalar.main() == 2
        assert not llamados

    def test_python_312_es_el_soportado(self):
        assert instalar.version_soportada((3, 12, 10))
        assert not instalar.version_soportada((3, 14, 0))
        assert not instalar.version_soportada((3, 10, 0))


def test_enter_final_sin_consola_real_no_revienta(monkeypatch):
    # En la instalación limpia del 14-nov, input() lanzó EOFError y el
    # instalador terminó con código 1 tras decir «Todo listo».
    TestMainRetornaExitCodeReal()._mockear_pasos(monkeypatch, todo_ok=True)
    monkeypatch.setattr(instalar, "_es_interactivo", lambda: True)

    def _eof(*a, **k):
        raise EOFError
    monkeypatch.setattr("builtins.input", _eof)
    assert instalar.main() == 0
