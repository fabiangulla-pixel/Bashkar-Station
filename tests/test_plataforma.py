"""
tests/test_plataforma.py — Capa de sistema operativo (core/plataforma.py).

Estos tests simulan los TRES sistemas, no solo aquel donde corre la suite.
Es la única forma de verificar el camino de macOS y de Linux desde Windows,
que es la máquina de desarrollo del proyecto: sin simulación, el código de
`open`/`xdg-open` y las rutas de Homebrew quedarían sin ejecutar hasta tener
el hardware delante.

Lo que la simulación NO prueba: que `open` de macOS abra realmente el visor
correcto, ni que Homebrew esté en esos prefijos en una instalación concreta.
Prueba que la app toma la rama correcta y construye el comando correcto.
"""

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import plataforma  # noqa: E402


# ══════════════════════════════════════════════════════════════════════════════
# Utilidades de simulación
# ══════════════════════════════════════════════════════════════════════════════

_TOKENS = {
    "windows": ("Windows", "win32"),
    "macos":   ("Darwin",  "darwin"),
    "linux":   ("Linux",   "linux"),
}


def simular(monkeypatch, sistema: str) -> None:
    """Hace creer al módulo que corre en `sistema`.

    Se fijan los dos indicadores a la vez (platform.system y sys.platform)
    porque dejarlos incoherentes describiría una máquina que no existe.
    """
    nombre, plat = _TOKENS[sistema]
    monkeypatch.setattr(platform, "system", lambda: nombre)
    monkeypatch.setattr(sys, "platform", plat)


@pytest.fixture(params=["windows", "macos", "linux"])
def cualquier_sistema(request, monkeypatch):
    simular(monkeypatch, request.param)
    return request.param


# ══════════════════════════════════════════════════════════════════════════════
# es_windows / es_macos / es_linux
# ══════════════════════════════════════════════════════════════════════════════

class TestDeteccionSistema:
    def test_exactamente_uno_verdadero(self, cualquier_sistema):
        banderas = [plataforma.es_windows(), plataforma.es_macos(), plataforma.es_linux()]
        assert sum(banderas) == 1

    def test_windows(self, monkeypatch):
        simular(monkeypatch, "windows")
        assert plataforma.es_windows() is True
        assert plataforma.es_macos() is False
        assert plataforma.es_linux() is False

    def test_macos(self, monkeypatch):
        simular(monkeypatch, "macos")
        assert plataforma.es_macos() is True
        assert plataforma.es_windows() is False

    def test_linux(self, monkeypatch):
        simular(monkeypatch, "linux")
        assert plataforma.es_linux() is True
        assert plataforma.es_windows() is False

    def test_sistema_desconocido_no_miente(self, monkeypatch):
        # Un BSD no es Linux: se responde que no, y el resto del módulo lo
        # trata por el camino POSIX sin necesidad de declararlo Linux.
        monkeypatch.setattr(platform, "system", lambda: "FreeBSD")
        monkeypatch.setattr(sys, "platform", "freebsd14")
        assert not plataforma.es_windows()
        assert not plataforma.es_macos()
        assert not plataforma.es_linux()

    def test_respaldo_a_sys_platform_si_platform_system_vacio(self, monkeypatch):
        # platform.system() devuelve "" en algunos entornos congelados.
        monkeypatch.setattr(platform, "system", lambda: "")
        monkeypatch.setattr(sys, "platform", "darwin")
        assert plataforma.es_macos() is True

    def test_platform_system_que_lanza_no_tumba_la_deteccion(self, monkeypatch):
        def _explota():
            raise OSError("sin /proc")
        monkeypatch.setattr(platform, "system", _explota)
        monkeypatch.setattr(sys, "platform", "linux")
        assert plataforma.es_linux() is True


# ══════════════════════════════════════════════════════════════════════════════
# abrir_en_sistema
# ══════════════════════════════════════════════════════════════════════════════

class _PopenFalso:
    """Doble de subprocess.Popen que registra el comando y finge un código."""

    def __init__(self, registro, returncode=0, colgar=False):
        self.registro = registro
        self.returncode = returncode
        self.colgar = colgar

    def __call__(self, cmd, *a, **k):
        self.registro.append(cmd)
        return self

    def wait(self, timeout=None):
        if self.colgar:
            raise subprocess.TimeoutExpired(cmd="x", timeout=timeout or 0)
        return self.returncode


class TestAbrirEnSistema:
    def test_windows_usa_startfile(self, monkeypatch, tmp_path):
        simular(monkeypatch, "windows")
        visto = []
        monkeypatch.setattr(os, "startfile", visto.append, raising=False)
        f = tmp_path / "a.pdf"
        f.write_text("x", encoding="utf-8")
        assert plataforma.abrir_en_sistema(f) is True
        assert visto == [str(f)]

    def test_windows_sin_startfile_devuelve_false(self, monkeypatch, tmp_path):
        # Caso real al simular Windows desde macOS/Linux: os.startfile no existe.
        simular(monkeypatch, "windows")
        monkeypatch.delattr(os, "startfile", raising=False)
        assert plataforma.abrir_en_sistema(tmp_path / "a.pdf") is False

    def test_windows_startfile_que_lanza_devuelve_false(self, monkeypatch, tmp_path):
        simular(monkeypatch, "windows")

        def _explota(_ruta):
            raise OSError("no hay asociación para .xyz")
        monkeypatch.setattr(os, "startfile", _explota, raising=False)
        assert plataforma.abrir_en_sistema(tmp_path / "a.xyz") is False

    def test_macos_usa_open(self, monkeypatch, tmp_path):
        simular(monkeypatch, "macos")
        registro = []
        monkeypatch.setattr(subprocess, "Popen", _PopenFalso(registro))
        f = tmp_path / "informe.pdf"
        assert plataforma.abrir_en_sistema(f) is True
        assert registro == [["open", str(f)]]

    def test_linux_usa_xdg_open(self, monkeypatch, tmp_path):
        simular(monkeypatch, "linux")
        registro = []
        monkeypatch.setattr(subprocess, "Popen", _PopenFalso(registro))
        f = tmp_path / "informe.pdf"
        assert plataforma.abrir_en_sistema(f) is True
        assert registro == [["xdg-open", str(f)]]

    def test_codigo_de_salida_distinto_de_cero_es_fallo(self, monkeypatch, tmp_path):
        simular(monkeypatch, "linux")
        monkeypatch.setattr(subprocess, "Popen", _PopenFalso([], returncode=4))
        assert plataforma.abrir_en_sistema(tmp_path / "a.pdf") is False

    def test_visor_que_sigue_vivo_cuenta_como_exito(self, monkeypatch, tmp_path):
        # xdg-open puede hacer exec del visor y quedarse ocupando el proceso
        # mientras el usuario mira el archivo: eso es que SÍ se abrió.
        simular(monkeypatch, "linux")
        monkeypatch.setattr(subprocess, "Popen", _PopenFalso([], colgar=True))
        assert plataforma.abrir_en_sistema(tmp_path / "a.pdf") is True

    def test_comando_inexistente_devuelve_false_sin_lanzar(self, monkeypatch, tmp_path):
        simular(monkeypatch, "linux")

        def _no_existe(*a, **k):
            raise FileNotFoundError("xdg-open")
        monkeypatch.setattr(subprocess, "Popen", _no_existe)
        assert plataforma.abrir_en_sistema(tmp_path / "a.pdf") is False

    @pytest.mark.skipif(shutil.which("xdg-open") is not None,
                        reason="Esta máquina sí tiene xdg-open: abriría el archivo de verdad")
    def test_sin_mocks_falta_xdg_open_de_verdad(self, monkeypatch, tmp_path):
        # Sin dobles: se invoca de verdad un comando que no está en el sistema
        # (el caso de un Linux mínimo sin xdg-utils) y no debe propagar nada.
        simular(monkeypatch, "linux")
        f = tmp_path / "a.pdf"
        f.write_text("x", encoding="utf-8")
        assert plataforma.abrir_en_sistema(f) is False

    def test_acepta_str_y_path(self, monkeypatch, tmp_path):
        simular(monkeypatch, "macos")
        registro = []
        monkeypatch.setattr(subprocess, "Popen", _PopenFalso(registro))
        plataforma.abrir_en_sistema(str(tmp_path))
        plataforma.abrir_en_sistema(tmp_path)
        assert registro[0] == registro[1]


# ══════════════════════════════════════════════════════════════════════════════
# Carpetas de usuario
# ══════════════════════════════════════════════════════════════════════════════

class TestDirDatosUsuario:
    def test_windows_usa_localappdata(self, monkeypatch, tmp_path):
        simular(monkeypatch, "windows")
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
        d = plataforma.dir_datos_usuario("Bashkar")
        assert d == Path(tmp_path / "Local") / "Bashkar"

    def test_windows_sin_localappdata_cae_al_home(self, monkeypatch):
        simular(monkeypatch, "windows")
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
        d = plataforma.dir_datos_usuario("Bashkar")
        assert d == Path.home() / "AppData" / "Local" / "Bashkar"

    def test_macos_usa_application_support(self, monkeypatch):
        simular(monkeypatch, "macos")
        d = plataforma.dir_datos_usuario("Bashkar")
        assert d == Path.home() / "Library" / "Application Support" / "Bashkar"

    def test_macos_ignora_xdg(self, monkeypatch, tmp_path):
        # XDG_DATA_HOME puede estar definido en un Mac con herramientas Unix;
        # ahí no manda: la convención de macOS es ~/Library.
        simular(monkeypatch, "macos")
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        assert "Library" in str(plataforma.dir_datos_usuario("Bashkar"))

    def test_linux_respeta_xdg_data_home(self, monkeypatch, tmp_path):
        simular(monkeypatch, "linux")
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "datos"))
        assert plataforma.dir_datos_usuario("Bashkar") == Path(tmp_path / "datos") / "Bashkar"

    def test_linux_sin_xdg_usa_local_share(self, monkeypatch):
        simular(monkeypatch, "linux")
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        d = plataforma.dir_datos_usuario("Bashkar")
        assert d == Path.home() / ".local" / "share" / "Bashkar"

    def test_no_crea_la_carpeta(self, monkeypatch, tmp_path):
        simular(monkeypatch, "linux")
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "nueva"))
        d = plataforma.dir_datos_usuario("Bashkar")
        assert not d.exists()

    def test_devuelve_path_en_los_tres(self, cualquier_sistema):
        assert isinstance(plataforma.dir_datos_usuario("Bashkar"), Path)


class TestDirConfigUsuario:
    def test_windows_usa_appdata_movil(self, monkeypatch, tmp_path):
        simular(monkeypatch, "windows")
        monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
        assert plataforma.dir_config_usuario("Bashkar") == Path(tmp_path / "Roaming") / "Bashkar"

    def test_linux_respeta_xdg_config_home(self, monkeypatch, tmp_path):
        simular(monkeypatch, "linux")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
        assert plataforma.dir_config_usuario("Bashkar") == Path(tmp_path / "cfg") / "Bashkar"

    def test_linux_sin_xdg_usa_punto_config(self, monkeypatch):
        simular(monkeypatch, "linux")
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        assert plataforma.dir_config_usuario("Bashkar") == Path.home() / ".config" / "Bashkar"

    def test_macos_comparte_carpeta_con_los_datos(self, monkeypatch):
        # Deliberado: macOS no separa config de datos para apps de terceros.
        simular(monkeypatch, "macos")
        assert plataforma.dir_config_usuario("B") == plataforma.dir_datos_usuario("B")

    def test_linux_separa_config_de_datos(self, monkeypatch):
        simular(monkeypatch, "linux")
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        assert plataforma.dir_config_usuario("B") != plataforma.dir_datos_usuario("B")


class TestDirTempAscii:
    def test_posix_devuelve_none(self, monkeypatch):
        for sistema in ("macos", "linux"):
            simular(monkeypatch, sistema)
            assert plataforma.dir_temp_ascii() is None

    def test_windows_devuelve_temp_del_sistema(self, monkeypatch):
        simular(monkeypatch, "windows")
        d = plataforma.dir_temp_ascii()
        # En una máquina Windows real existe; simulado desde otra, devuelve None.
        assert d is None or d.lower().endswith("temp")

    def test_windows_sin_carpeta_devuelve_none(self, monkeypatch, tmp_path):
        simular(monkeypatch, "windows")
        monkeypatch.setenv("SystemRoot", str(tmp_path / "no_existe"))
        assert plataforma.dir_temp_ascii() is None


# ══════════════════════════════════════════════════════════════════════════════
# nombre_ejecutable / buscar_binario
# ══════════════════════════════════════════════════════════════════════════════

class TestNombreEjecutable:
    def test_windows_agrega_exe(self, monkeypatch):
        simular(monkeypatch, "windows")
        assert plataforma.nombre_ejecutable("tesseract") == "tesseract.exe"

    def test_windows_no_duplica_exe(self, monkeypatch):
        simular(monkeypatch, "windows")
        assert plataforma.nombre_ejecutable("tesseract.exe") == "tesseract.exe"

    def test_posix_no_agrega_nada(self, monkeypatch):
        for sistema in ("macos", "linux"):
            simular(monkeypatch, sistema)
            assert plataforma.nombre_ejecutable("tesseract") == "tesseract"


class TestBuscarBinario:
    def test_el_path_manda(self, monkeypatch, cualquier_sistema):
        monkeypatch.setattr(shutil, "which", lambda n: "/ruta/del/path/" + n)
        assert plataforma.buscar_binario("tesseract") == "/ruta/del/path/tesseract"

    def test_candidato_extra_como_archivo(self, monkeypatch, tmp_path):
        simular(monkeypatch, "macos")
        monkeypatch.setattr(shutil, "which", lambda n: None)
        exe = tmp_path / "tesseract"
        exe.write_text("#!/bin/sh", encoding="utf-8")
        assert plataforma.buscar_binario("tesseract", [exe]) == str(exe)

    def test_candidato_extra_como_carpeta(self, monkeypatch, tmp_path):
        simular(monkeypatch, "linux")
        monkeypatch.setattr(shutil, "which", lambda n: None)
        (tmp_path / "tesseract").write_text("#!/bin/sh", encoding="utf-8")
        assert plataforma.buscar_binario("tesseract", [tmp_path]) == str(tmp_path / "tesseract")

    def test_candidato_extra_carpeta_con_bin(self, monkeypatch, tmp_path):
        simular(monkeypatch, "linux")
        monkeypatch.setattr(shutil, "which", lambda n: None)
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        (bin_dir / "pdftoppm").write_text("x", encoding="utf-8")
        assert plataforma.buscar_binario("pdftoppm", [tmp_path]) == str(bin_dir / "pdftoppm")

    def test_windows_busca_con_extension_exe(self, monkeypatch, tmp_path):
        simular(monkeypatch, "windows")
        monkeypatch.setattr(shutil, "which", lambda n: None)
        (tmp_path / "tesseract.exe").write_text("MZ", encoding="utf-8")
        assert plataforma.buscar_binario("tesseract", [tmp_path]) == str(tmp_path / "tesseract.exe")

    def test_devuelve_cadena_vacia_si_no_esta(self, monkeypatch, cualquier_sistema):
        monkeypatch.setattr(shutil, "which", lambda n: None)
        assert plataforma.buscar_binario("binario_que_no_existe_1234") == ""

    def test_candidatos_vacios_o_none_no_rompen(self, monkeypatch):
        simular(monkeypatch, "linux")
        monkeypatch.setattr(shutil, "which", lambda n: None)
        assert plataforma.buscar_binario("nada_1234", ["", None]) == ""

    def test_which_que_lanza_no_propaga(self, monkeypatch):
        simular(monkeypatch, "macos")

        def _explota(_n):
            raise OSError("PATH corrupto")
        monkeypatch.setattr(shutil, "which", _explota)
        assert plataforma.buscar_binario("nada_1234") == ""


class TestDirsBinariosTipicos:
    def test_macos_incluye_homebrew_de_apple_silicon(self, monkeypatch):
        simular(monkeypatch, "macos")
        assert Path("/opt/homebrew/bin") in plataforma._dirs_binarios_tipicos()

    def test_macos_no_incluye_program_files(self, monkeypatch):
        simular(monkeypatch, "macos")
        assert all("Program Files" not in str(d)
                   for d in plataforma._dirs_binarios_tipicos())

    def test_linux_incluye_usr_bin(self, monkeypatch):
        simular(monkeypatch, "linux")
        assert Path("/usr/bin") in plataforma._dirs_binarios_tipicos()

    def test_windows_incluye_program_files(self, monkeypatch):
        simular(monkeypatch, "windows")
        dirs = plataforma._dirs_binarios_tipicos()
        assert any("Program Files" in str(d) for d in dirs)

    def test_sin_duplicados(self, cualquier_sistema):
        dirs = [str(d).lower() for d in plataforma._dirs_binarios_tipicos()]
        assert len(dirs) == len(set(dirs))


# ══════════════════════════════════════════════════════════════════════════════
# Tesseract y poppler
# ══════════════════════════════════════════════════════════════════════════════

class TestBuscarTesseract:
    def test_toma_el_del_path(self, monkeypatch, cualquier_sistema):
        monkeypatch.setattr(shutil, "which", lambda n: "/usr/bin/" + n)
        assert plataforma.buscar_tesseract() == "/usr/bin/tesseract"

    def test_macos_mira_en_homebrew(self, monkeypatch, tmp_path):
        # Se redirige el prefijo de Homebrew a una carpeta temporal para poder
        # comprobar, desde Windows, que ese candidato se consulta de verdad.
        simular(monkeypatch, "macos")
        monkeypatch.setattr(shutil, "which", lambda n: None)
        brew = tmp_path / "opt" / "homebrew" / "bin"
        brew.mkdir(parents=True)
        (brew / "tesseract").write_text("#!/bin/sh", encoding="utf-8")
        monkeypatch.setattr(plataforma, "_candidatos_tesseract", lambda: [brew])
        assert plataforma.buscar_tesseract() == str(brew / "tesseract")

    def test_cadena_vacia_si_no_hay(self, monkeypatch):
        simular(monkeypatch, "macos")
        monkeypatch.setattr(shutil, "which", lambda n: None)
        monkeypatch.setattr(plataforma, "_candidatos_tesseract", list)
        monkeypatch.setattr(plataforma, "_dirs_binarios_tipicos", list)
        assert plataforma.buscar_tesseract() == ""

    def test_devuelve_str_en_los_tres(self, cualquier_sistema):
        assert isinstance(plataforma.buscar_tesseract(), str)


class TestCandidatosTesseract:
    def test_windows_apunta_a_tesseract_ocr(self, monkeypatch):
        simular(monkeypatch, "windows")
        assert any("Tesseract-OCR" in str(p) for p in plataforma._candidatos_tesseract())

    def test_macos_apunta_a_prefijos_de_homebrew(self, monkeypatch):
        simular(monkeypatch, "macos")
        rutas = plataforma._candidatos_tesseract()
        assert Path("/opt/homebrew/bin") in rutas
        assert Path("/usr/local/bin") in rutas

    def test_linux_apunta_a_usr_bin(self, monkeypatch):
        simular(monkeypatch, "linux")
        assert Path("/usr/bin") in plataforma._candidatos_tesseract()


class TestDirsTessdata:
    def test_el_home_va_primero_en_los_tres(self, cualquier_sistema):
        assert plataforma.dirs_tessdata()[0] == Path.home() / "tessdata"

    def test_macos_usa_share_de_homebrew(self, monkeypatch):
        simular(monkeypatch, "macos")
        assert Path("/opt/homebrew/share/tessdata") in plataforma.dirs_tessdata()

    def test_linux_usa_usr_share(self, monkeypatch):
        simular(monkeypatch, "linux")
        assert any("usr" in str(p) and "tessdata" in str(p)
                   for p in plataforma.dirs_tessdata())

    def test_windows_usa_program_files(self, monkeypatch):
        simular(monkeypatch, "windows")
        assert any("Program Files" in str(p) for p in plataforma.dirs_tessdata())

    def test_ninguna_ruta_cableada_al_usuario_del_desarrollador(self):
        # Antes había un C:\Users\Lenovo\tessdata literal: solo servía en una
        # máquina y encima era redundante con Path.home(), que aquí resuelve a
        # esa misma carpeta. Por eso se comprueba el código fuente y no la
        # lista: la lista contiene el home del usuario que corra los tests.
        fuente = Path(plataforma.__file__).read_text(encoding="utf-8")
        assert "Users\\Lenovo" not in fuente
        assert "Users/Lenovo" not in fuente


class TestBuscarPoppler:
    def test_toma_pdftoppm_del_path(self, monkeypatch, cualquier_sistema):
        monkeypatch.setattr(shutil, "which", lambda n: "/usr/bin/" + n)
        assert plataforma.buscar_poppler() == "/usr/bin/pdftoppm"

    def test_macos_mira_en_homebrew(self, monkeypatch, tmp_path):
        simular(monkeypatch, "macos")
        monkeypatch.setattr(shutil, "which", lambda n: None)
        brew = tmp_path / "homebrew" / "bin"
        brew.mkdir(parents=True)
        (brew / "pdftoppm").write_text("#!/bin/sh", encoding="utf-8")
        monkeypatch.setattr(plataforma, "_candidatos_poppler", lambda: [brew])
        assert plataforma.buscar_poppler() == str(brew / "pdftoppm")

    def test_windows_encuentra_el_zip_descomprimido_en_profundidad(self, monkeypatch, tmp_path):
        # Poppler para Windows no tiene instalador: el binario queda enterrado.
        simular(monkeypatch, "windows")
        monkeypatch.setattr(shutil, "which", lambda n: None)
        hondo = tmp_path / "poppler-24.02.0" / "Library" / "bin"
        hondo.mkdir(parents=True)
        (hondo / "pdftoppm.exe").write_text("MZ", encoding="utf-8")
        monkeypatch.setattr(plataforma, "_candidatos_poppler", lambda: [tmp_path])
        monkeypatch.setattr(plataforma, "_dirs_binarios_tipicos", list)
        assert plataforma.buscar_poppler() == str(hondo / "pdftoppm.exe")

    def test_posix_no_recorre_en_profundidad(self, monkeypatch, tmp_path):
        # En macOS/Linux poppler viene del gestor de paquetes y queda en un bin
        # plano; recorrer /usr entero sería carísimo y no debe ocurrir.
        simular(monkeypatch, "linux")
        monkeypatch.setattr(shutil, "which", lambda n: None)
        hondo = tmp_path / "a" / "b" / "c"
        hondo.mkdir(parents=True)
        (hondo / "pdftoppm").write_text("x", encoding="utf-8")
        monkeypatch.setattr(plataforma, "_candidatos_poppler", lambda: [tmp_path])
        monkeypatch.setattr(plataforma, "_dirs_binarios_tipicos", list)
        assert plataforma.buscar_poppler() == ""

    def test_cadena_vacia_si_no_hay(self, monkeypatch):
        simular(monkeypatch, "macos")
        monkeypatch.setattr(shutil, "which", lambda n: None)
        monkeypatch.setattr(plataforma, "_candidatos_poppler", list)
        monkeypatch.setattr(plataforma, "_dirs_binarios_tipicos", list)
        assert plataforma.buscar_poppler() == ""


class TestDirPoppler:
    def test_devuelve_la_carpeta_no_el_ejecutable(self, monkeypatch, tmp_path):
        simular(monkeypatch, "linux")
        monkeypatch.setattr(shutil, "which", lambda n: None)
        (tmp_path / "pdftoppm").write_text("x", encoding="utf-8")
        monkeypatch.setattr(plataforma, "_candidatos_poppler", lambda: [tmp_path])
        assert plataforma.dir_poppler() == str(tmp_path)

    def test_cadena_vacia_si_no_hay_poppler(self, monkeypatch):
        simular(monkeypatch, "macos")
        monkeypatch.setattr(shutil, "which", lambda n: None)
        monkeypatch.setattr(plataforma, "_candidatos_poppler", list)
        monkeypatch.setattr(plataforma, "_dirs_binarios_tipicos", list)
        assert plataforma.dir_poppler() == ""


# ══════════════════════════════════════════════════════════════════════════════
# Integración: el resto de la app usa esta capa y respeta la prioridad previa
# ══════════════════════════════════════════════════════════════════════════════

_RAIZ = Path(__file__).parent.parent


class TestPrioridadDeLosArchivosDeConfiguracion:
    """tesseract_path.txt y poppler_path.txt mandan sobre la detección.

    Es la ruta que fijó el usuario o el instalador en Windows; que ahora exista
    una búsqueda automática no puede pisarla.
    """

    def test_tesseract_txt_gana_a_la_deteccion(self, monkeypatch, tmp_path):
        from core import ocr_engine
        monkeypatch.setattr(ocr_engine, "_MODULE_ROOT", tmp_path)
        elegido = tmp_path / "tesseract_elegido_a_mano.exe"
        elegido.write_text("MZ", encoding="utf-8")
        (tmp_path / "tesseract_path.txt").write_text(str(elegido), encoding="utf-8")
        monkeypatch.setattr(plataforma, "buscar_tesseract", lambda: "/otro/tesseract")
        assert ocr_engine._get_tesseract_cmd() == str(elegido)

    def test_sin_txt_cae_en_la_deteccion_del_sistema(self, monkeypatch, tmp_path):
        from core import ocr_engine
        monkeypatch.setattr(ocr_engine, "_MODULE_ROOT", tmp_path)
        monkeypatch.setattr(plataforma, "buscar_tesseract",
                            lambda: "/opt/homebrew/bin/tesseract")
        assert ocr_engine._get_tesseract_cmd() == "/opt/homebrew/bin/tesseract"

    def test_ultimo_recurso_es_el_nombre_pelado(self, monkeypatch, tmp_path):
        # Sin ruta ninguna se conserva el comportamiento histórico: pytesseract
        # falla con el mensaje de siempre, que el usuario ya sabe interpretar.
        from core import ocr_engine
        monkeypatch.setattr(ocr_engine, "_MODULE_ROOT", tmp_path)
        monkeypatch.setattr(plataforma, "buscar_tesseract", lambda: "")
        assert ocr_engine._get_tesseract_cmd() == "tesseract"

    def test_txt_que_apunta_a_ruta_inexistente_no_se_usa(self, monkeypatch, tmp_path):
        from core import ocr_engine
        monkeypatch.setattr(ocr_engine, "_MODULE_ROOT", tmp_path)
        (tmp_path / "tesseract_path.txt").write_text(r"Z:\se\borro.exe", encoding="utf-8")
        monkeypatch.setattr(plataforma, "buscar_tesseract", lambda: "/usr/bin/tesseract")
        assert ocr_engine._get_tesseract_cmd() == "/usr/bin/tesseract"

    def test_poppler_txt_gana_al_path(self, monkeypatch, tmp_path):
        from core import ocr_engine
        monkeypatch.setattr(ocr_engine, "_MODULE_ROOT", tmp_path)
        bin_dir = tmp_path / "poppler" / "bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / plataforma.nombre_ejecutable("pdftoppm")).write_text("x", encoding="utf-8")
        (tmp_path / "poppler_path.txt").write_text(str(bin_dir), encoding="utf-8")
        monkeypatch.setattr(shutil, "which", lambda n: "/usr/bin/pdftoppm")
        assert ocr_engine._get_poppler_path() == str(bin_dir)

    def test_poppler_en_el_path_no_necesita_ruta_explicita(self, monkeypatch, tmp_path):
        from core import ocr_engine
        monkeypatch.setattr(ocr_engine, "_MODULE_ROOT", tmp_path)
        monkeypatch.setattr(shutil, "which", lambda n: "/usr/bin/pdftoppm")
        assert ocr_engine._get_poppler_path() is None

    def test_poppler_detectado_se_cachea_en_el_txt(self, monkeypatch, tmp_path):
        # La búsqueda en Windows recorre el zip descomprimido en profundidad:
        # repetirla en cada página sería carísimo.
        from core import ocr_engine
        monkeypatch.setattr(ocr_engine, "_MODULE_ROOT", tmp_path)
        monkeypatch.setattr(shutil, "which", lambda n: None)
        monkeypatch.setattr(plataforma, "dir_poppler", lambda: "/opt/homebrew/bin")
        assert ocr_engine._get_poppler_path() == "/opt/homebrew/bin"
        assert (tmp_path / "poppler_path.txt").read_text(encoding="utf-8") == "/opt/homebrew/bin"

    def test_text_extractor_no_duplica_la_busqueda(self, monkeypatch):
        from core import ocr_engine, text_extractor
        monkeypatch.setattr(ocr_engine, "_get_poppler_path", lambda: "/ruta/unica")
        assert text_extractor._get_poppler_path() == "/ruta/unica"


class TestNadaDependeYaDeWindowsDirectamente:
    """Guardas de regresión: lo que rompía el arranque fuera de Windows."""

    def test_no_queda_ningun_os_startfile_en_el_codigo_de_la_app(self):
        # os.startfile no existe fuera de Windows: cada llamada era un
        # AttributeError garantizado en macOS y en Linux.
        fuentes = [_RAIZ / "app.py", _RAIZ / "cli.py", _RAIZ / "servidor_web.py"]
        # plataforma.py queda fuera: es el único sitio donde os.startfile puede
        # aparecer, y ahí va detrás de un getattr y de la comprobación de SO.
        fuentes += [f for f in sorted((_RAIZ / "core").glob("*.py"))
                    if f.name != "plataforma.py"]
        fuentes += sorted((_RAIZ / "exportadores").glob("*.py"))
        culpables = [f.name for f in fuentes
                     if f.exists() and "os.startfile" in f.read_text(encoding="utf-8")]
        assert culpables == []

    def test_ningun_modulo_de_core_cablea_la_carpeta_del_desarrollador(self):
        culpables = []
        for f in sorted((_RAIZ / "core").glob("*.py")):
            texto = f.read_text(encoding="utf-8")
            if "Users\\Lenovo" in texto or "Users/Lenovo" in texto:
                culpables.append(f.name)
        assert culpables == []

    def test_el_venv_de_kraken_no_esta_cableado_a_una_unidad(self, monkeypatch):
        # En Windows sigue siendo D:\ por MAX_PATH; fuera de Windows tiene que
        # ser el home, que es donde un usuario puede crearlo sin permisos.
        from core import ocr_kraken
        simular(monkeypatch, "macos")
        candidatos = ocr_kraken._candidatos_venv_kraken()
        assert Path("D:/kraken_env") not in candidatos
        assert Path("C:/kraken_env") not in candidatos
        assert Path.home() / "kraken_env" in candidatos

        simular(monkeypatch, "windows")
        assert Path("D:/kraken_env") in ocr_kraken._candidatos_venv_kraken()

    def test_el_venv_de_kraken_es_configurable_por_entorno(self, monkeypatch, tmp_path):
        from core import ocr_kraken
        monkeypatch.setenv("BASHKAR_KRAKEN_VENV", str(tmp_path))
        assert ocr_kraken._candidatos_venv_kraken()[0] == tmp_path

    def test_ejecutables_del_venv_segun_sistema(self, monkeypatch, tmp_path):
        from core import ocr_kraken
        simular(monkeypatch, "windows")
        assert ocr_kraken._bin_venv(tmp_path, "python") == tmp_path / "Scripts" / "python.exe"
        simular(monkeypatch, "linux")
        assert ocr_kraken._bin_venv(tmp_path, "python") == tmp_path / "bin" / "python"

    def test_tessdata_del_layout_usa_la_capa_de_sistema(self, monkeypatch, tmp_path):
        from core import layout_tesseract
        monkeypatch.delenv("TESSDATA_PREFIX", raising=False)
        falsa = tmp_path / "tessdata"
        falsa.mkdir()
        (falsa / "spa.traineddata").write_text("x", encoding="utf-8")
        monkeypatch.setattr(plataforma, "dirs_tessdata", lambda: [falsa])
        layout_tesseract._asegurar_tessdata()
        assert os.environ["TESSDATA_PREFIX"] == str(falsa)

    def test_pero_no_ofrece_unidades_de_windows_fuera_de_windows(self, monkeypatch):
        from core import ocr_pero
        simular(monkeypatch, "linux")
        # Solo se comprueba que la rama no cablee C:/ ni D:/; la lista final
        # está filtrada por existencia y en esta máquina sale vacía.
        assert ocr_pero.rutas_config_probables() == []


# ══════════════════════════════════════════════════════════════════════════════
# Contrato del módulo
# ══════════════════════════════════════════════════════════════════════════════

class TestContrato:
    def test_solo_biblioteca_estandar(self):
        # Si este módulo dependiera de un paquete externo no podría usarse en el
        # arranque, que es justo cuando hay que decidir dónde está tesseract.
        fuente = (Path(plataforma.__file__)).read_text(encoding="utf-8")
        externos = ("import numpy", "import fitz", "import pytesseract",
                    "import PIL", "import pandas", "from core.")
        assert all(mod not in fuente for mod in externos)

    def test_exporta_lo_que_promete(self):
        for nombre in plataforma.__all__:
            assert hasattr(plataforma, nombre), nombre
