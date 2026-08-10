"""tests/test_requisitos.py — Diagnóstico de requisitos y asistente de instalación.

La prueba que más importa de este archivo es la de la bomba de fork: dentro de
un .exe de PyInstaller, `sys.executable` apunta al propio .exe, así que llamar a
`pip` con él relanza la aplicación entera. En este proyecto eso generó ~90
procesos en 12 segundos y obligó a reiniciar la máquina. Que `instalar_requisito`
no llame a subprocess estando congelado no es un detalle de estilo.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import plataforma, requisitos  # noqa: E402


def _simular(monkeypatch, sistema: str):
    """Hace creer al módulo de plataforma que corre en otro sistema."""
    monkeypatch.setattr(plataforma.platform, "system", lambda: sistema)
    equivalente = {"Windows": "win32", "Darwin": "darwin", "Linux": "linux"}[sistema]
    monkeypatch.setattr(plataforma.sys, "platform", equivalente)


# ── La barrera contra la bomba de fork ────────────────────────────────────────

class TestNoSeInstalaNadaCongelado:
    def test_instalar_requisito_no_llama_subprocess_si_esta_congelado(self, monkeypatch):
        monkeypatch.setattr(requisitos, "esta_congelado", lambda: True)

        def _prohibido(*_a, **_k):
            raise AssertionError(
                "subprocess llamado estando congelado: esto es la bomba de fork"
            )

        monkeypatch.setattr(requisitos.subprocess, "run", _prohibido)

        req = requisitos.Requisito(
            clave="pip:folium", nombre="folium", para_que="Mapas",
            instalado=False, puede_instalarse=True,
            instruccion_manual="pip install folium>=0.15",
        )
        mensajes = []
        assert requisitos.instalar_requisito(req, mensajes.append) is False
        # Y le dice a la persona qué hacer, en vez de fallar en silencio.
        assert any("terminal" in m for m in mensajes)

    def test_diagnostico_congelado_marca_todo_como_no_instalable(self, monkeypatch):
        monkeypatch.setattr(requisitos, "esta_congelado", lambda: True)
        diag = requisitos.diagnosticar()
        assert diag.congelado is True
        assert all(not r.puede_instalarse for r in diag.requisitos)

    def test_congelado_no_confia_en_la_marca_del_requisito(self, monkeypatch):
        """Aunque alguien construya un requisito con puede_instalarse=True."""
        monkeypatch.setattr(requisitos, "esta_congelado", lambda: True)
        monkeypatch.setattr(requisitos.subprocess, "run",
                            lambda *_a, **_k: pytest.fail("no debe llamarse"))
        req = requisitos.Requisito(
            clave="pip:x", nombre="x", para_que="", instalado=False,
            puede_instalarse=True, instruccion_manual="pip install x",
        )
        assert requisitos.instalar_requisito(req, lambda _m: None) is False


# ── Instrucciones por plataforma ──────────────────────────────────────────────

class TestInstruccionesPorSistema:
    def test_macos_usa_homebrew(self, monkeypatch):
        _simular(monkeypatch, "Darwin")
        assert requisitos._instruccion_binario("tesseract") == "brew install tesseract"
        assert requisitos._instruccion_binario("poppler") == "brew install poppler"

    def test_linux_usa_apt_con_el_idioma(self, monkeypatch):
        _simular(monkeypatch, "Linux")
        instruccion = requisitos._instruccion_binario("tesseract")
        assert instruccion.startswith("sudo apt install")
        # El paquete del idioma va aparte en Debian/Ubuntu; sin él, OCR en inglés.
        assert "tesseract-ocr-spa" in instruccion

    def test_windows_manda_al_instalador(self, monkeypatch):
        _simular(monkeypatch, "Windows")
        assert "UB-Mannheim" in requisitos._instruccion_binario("tesseract")
        assert "poppler-windows" in requisitos._instruccion_binario("poppler")


class TestTesseract:
    def test_sin_tesseract_da_la_instruccion_del_sistema(self, monkeypatch):
        _simular(monkeypatch, "Darwin")
        monkeypatch.setattr(plataforma, "buscar_tesseract", lambda: "")
        req = requisitos._requisito_tesseract()
        assert req.instalado is False
        assert req.instruccion_manual == "brew install tesseract"

    def test_tesseract_sin_espanol_cuenta_como_faltante(self, monkeypatch):
        """Tener el binario no basta: sin spa.traineddata el OCR lee inglés."""
        _simular(monkeypatch, "Darwin")
        monkeypatch.setattr(plataforma, "buscar_tesseract", lambda: "/opt/homebrew/bin/tesseract")
        monkeypatch.setattr(requisitos, "_tesseract_tiene_espanol", lambda _r: False)
        req = requisitos._requisito_tesseract()
        assert req.instalado is False
        assert "español" in req.nombre
        assert req.instruccion_manual == "brew install tesseract-lang"

    def test_tesseract_completo_queda_listo(self, monkeypatch):
        monkeypatch.setattr(plataforma, "buscar_tesseract", lambda: "/usr/bin/tesseract")
        monkeypatch.setattr(requisitos, "_tesseract_tiene_espanol", lambda _r: True)
        req = requisitos._requisito_tesseract()
        assert req.instalado is True
        assert req.detalle == "/usr/bin/tesseract"

    def test_listar_langs_que_falla_no_lanza(self, monkeypatch, tmp_path):
        monkeypatch.setattr(plataforma, "dirs_tessdata", lambda: [tmp_path])

        def _revienta(*_a, **_k):
            raise OSError("binario corrupto")
        monkeypatch.setattr(requisitos.subprocess, "run", _revienta)
        assert requisitos._tesseract_tiene_espanol("/ruta/tesseract") is False

    def test_sin_ruta_no_intenta_ejecutar(self, monkeypatch, tmp_path):
        monkeypatch.setattr(plataforma, "dirs_tessdata", lambda: [tmp_path])
        assert requisitos._tesseract_tiene_espanol("") is False

    def test_spa_traineddata_suelto_cuenta_como_instalado(self, monkeypatch, tmp_path):
        """Regresión de una falsa alarma real.

        `tesseract --list-langs` solo lista el tessdata de la instalación. Como
        Bashkar usa además ~/tessdata, un equipo bien configurado —con
        spa.traineddata ahí— se reportaba como «falta el español» y mandaba a
        reinstalar Tesseract sin necesidad.
        """
        (tmp_path / "spa.traineddata").write_bytes(b"x")
        monkeypatch.setattr(plataforma, "dirs_tessdata", lambda: [tmp_path])
        monkeypatch.setattr(
            requisitos.subprocess, "run",
            lambda *_a, **_k: pytest.fail("no debe preguntar al binario: el archivo está"),
        )
        assert requisitos._tesseract_tiene_espanol("/ruta/tesseract") is True

    def test_carpeta_inaccesible_no_rompe_la_busqueda(self, monkeypatch, tmp_path):
        """Una unidad de red desconectada no debe tumbar el diagnóstico."""
        class _Ruta:
            def __truediv__(self, _otro):
                raise OSError("unidad no disponible")

        monkeypatch.setattr(plataforma, "dirs_tessdata", lambda: [_Ruta(), tmp_path])
        monkeypatch.setattr(requisitos.subprocess, "run",
                            lambda *_a, **_k: pytest.fail("no debería llegar aquí"))
        (tmp_path / "spa.traineddata").write_bytes(b"x")
        assert requisitos._tesseract_tiene_espanol("/ruta/tesseract") is True


# ── Diagnóstico completo ──────────────────────────────────────────────────────

class TestDiagnostico:
    def test_incluye_python_tesseract_y_poppler(self):
        diag = requisitos.diagnosticar()
        claves = {r.clave for r in diag.requisitos}
        assert {"python", "tesseract", "poppler", "spacy_modelo"} <= claves

    def test_los_opcionales_no_bloquean(self):
        diag = requisitos.diagnosticar()
        opcionales = [r for r in diag.requisitos if not r.obligatorio]
        assert opcionales, "kraken y el dictado deberían estar como opcionales"
        assert all(r not in diag.faltantes for r in opcionales)

    def test_estado_legible(self):
        req = requisitos.Requisito("x", "X", "", instalado=True)
        assert req.estado == "listo"
        assert requisitos.Requisito("x", "X", "", instalado=False).estado == "falta"
        assert requisitos.Requisito(
            "x", "X", "", instalado=False, obligatorio=False).estado == "opcional"

    def test_nombre_del_sistema(self, monkeypatch):
        _simular(monkeypatch, "Darwin")
        assert requisitos.diagnosticar().sistema == "macOS"


class TestComandoParaTerminal:
    def test_agrupa_los_pip_en_una_sola_linea(self):
        diag = requisitos.Diagnostico(sistema="macOS", requisitos=[
            requisitos.Requisito("pip:folium", "folium", "", instalado=False,
                                 instruccion_manual="pip install folium>=0.15"),
            requisitos.Requisito("pip:lxml", "lxml", "", instalado=False,
                                 instruccion_manual="pip install lxml>=5.0"),
            requisitos.Requisito("tesseract", "Tesseract", "", instalado=False,
                                 instruccion_manual="brew install tesseract"),
        ])
        texto = requisitos.comando_terminal_completo(diag)
        lineas = texto.splitlines()
        # Un solo pip con los dos paquetes: pegar diez líneas es peor experiencia.
        assert lineas[0] == "pip install folium>=0.15 lxml>=5.0"
        assert "brew install tesseract" in lineas

    def test_sin_faltantes_devuelve_vacio(self):
        diag = requisitos.Diagnostico(sistema="Windows", requisitos=[
            requisitos.Requisito("pip:folium", "folium", "", instalado=True),
        ])
        assert requisitos.comando_terminal_completo(diag) == ""


class TestRutaPython:
    def test_sin_congelar_usa_el_interprete_actual(self, monkeypatch):
        monkeypatch.setattr(requisitos, "esta_congelado", lambda: False)
        assert requisitos.ruta_python_del_sistema() == sys.executable

    def test_congelado_no_devuelve_el_exe(self, monkeypatch):
        """El .exe no sirve para ejecutar pip; hay que dar un Python real."""
        monkeypatch.setattr(requisitos, "esta_congelado", lambda: True)
        monkeypatch.setattr(requisitos.shutil, "which",
                            lambda n: "/usr/bin/python3" if n == "python3" else None)
        assert requisitos.ruta_python_del_sistema() == "/usr/bin/python3"

    def test_congelado_sin_python_en_path_degrada(self, monkeypatch):
        monkeypatch.setattr(requisitos, "esta_congelado", lambda: True)
        monkeypatch.setattr(requisitos.shutil, "which", lambda _n: None)
        assert requisitos.ruta_python_del_sistema() == "python"


# ── El asistente gráfico ──────────────────────────────────────────────────────

# Los tests que abren la ventana de verdad NO corren en la suite por defecto.
#
# Por qué: la suite ya instancia raíces de Tk en ocho archivos
# (test_bench_gui, test_grafo_gui, test_welcome_gui, test_ling_handlers…).
# Añadir una más rebasa lo que el intérprete Tcl aguanta en un solo proceso y
# el resultado NO es un test en rojo: el proceso se ABORTA, sin traza de
# Python, varios archivos más adelante (en test_servidor_web.py). Se verificó
# de las dos maneras — sin este archivo la suite completa pasa; con él, y aun
# compartiendo una única ventana entre todos los tests de aquí, se cae.
#
# Degradar una suite de 1279 pruebas por cinco tests de ventana es mal negocio,
# y esconderlo detrás de un `try/except` sería peor: la caída es del proceso, no
# capturable. Los tests siguen existiendo y pasan (verificado: 59 en verde junto
# a los demás archivos de GUI); se ejecutan a propósito con:
#
#     set BASHKAR_TEST_GUI_WIZARD=1 && python -m pytest tests/test_requisitos.py
#
# La lógica del asistente vive en core/requisitos.py y está cubierta por los 22
# tests de arriba, que sí corren siempre. Esto de aquí solo comprueba el montaje
# de los widgets.
_GUI_ACTIVA = os.environ.get("BASHKAR_TEST_GUI_WIZARD") == "1"


@pytest.fixture(scope="module")
def asistente():
    """Una ÚNICA ventana para todo el archivo, sin mainloop."""
    tk = pytest.importorskip("tkinter")
    from setup_wizard import AsistenteInstalacion
    try:
        app = AsistenteInstalacion()
    except tk.TclError:
        pytest.skip("Sin entorno gráfico para tkinter")
    app.withdraw()
    yield app
    try:
        app.destroy()
    except Exception:
        pass


@pytest.mark.skipif(not _GUI_ACTIVA,
                    reason="ver la nota sobre raíces de Tk; BASHKAR_TEST_GUI_WIZARD=1")
class TestAsistenteGrafico:
    def test_se_construye_y_lista_los_requisitos(self, asistente):
        assert asistente._diag is not None
        assert len(asistente._filas) == len(asistente._diag.requisitos)

    def test_el_worker_no_toca_widgets(self, asistente, monkeypatch):
        """El worker solo deja mensajes en la cola; Tk se actualiza en after()."""
        monkeypatch.setattr(requisitos, "instalar_requisito",
                            lambda _r, registrar=None: (registrar and registrar("ok")) or True)
        req = requisitos.Requisito("pip:x", "x", "", instalado=False,
                                   puede_instalarse=True,
                                   instruccion_manual="pip install x")
        asistente._worker_instalar([req])
        tipos = []
        while not asistente._cola.empty():
            tipos.append(asistente._cola.get_nowait()[0])
        assert "fin" in tipos
        assert "progreso" in tipos

    def test_copiar_comandos_deja_texto_en_el_portapapeles(self, asistente):
        asistente._diag = requisitos.Diagnostico(sistema="macOS", requisitos=[
            requisitos.Requisito("tesseract", "Tesseract", "", instalado=False,
                                 instruccion_manual="brew install tesseract"),
        ])
        asistente._copiar()
        assert "brew install tesseract" in asistente.clipboard_get()

    def test_congelado_deshabilita_el_boton_de_instalar(self, asistente, monkeypatch):
        monkeypatch.setattr(requisitos, "esta_congelado", lambda: True)
        asistente._revisar()
        assert asistente.btn_instalar._habilitado is False
        # Se deja la ventana como estaba: el fixture es de módulo y la comparten
        # los demás tests.
        asistente._revisar()


@pytest.mark.skipif(not _GUI_ACTIVA,
                    reason="ver la nota sobre raíces de Tk; BASHKAR_TEST_GUI_WIZARD=1")
class TestCierreDeLaVentana:
    """DEBE SER LA ÚLTIMA CLASE DEL ARCHIVO.

    Estos tests destruyen la ventana compartida por el fixture de módulo, así
    que cualquier test posterior que la use fallaría. El orden importa: pytest
    ejecuta en el orden del archivo.
    """

    def test_destruir_cancela_el_temporizador(self, asistente):
        """Regresión: un `after` pendiente sobre widgets ya destruidos no lanza
        una excepción que se pueda capturar — aborta el proceso entero."""
        assert asistente._tarea_cola is not None
        asistente.destroy()
        assert asistente._tarea_cola is None

    def test_bombear_cola_no_actua_sobre_una_ventana_cerrada(self, asistente):
        # La ventana ya viene destruida del test anterior.
        asistente._bombear_cola()   # no debe lanzar ni reprogramarse
        assert asistente._tarea_cola is None
