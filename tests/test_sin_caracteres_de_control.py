r"""Ningún archivo de texto del repo lleva caracteres de control.

Escribir rutas de Windows o regex desde un heredoc convierte en silencio
``\b`` en retroceso, ``\v`` en tabulador vertical o ``\t`` en tabulador. No da
error: una ruta deja de existir (sesión 72: el motor Surya buscaba
``C:\devenv-surya``) o una rama de regex deja de coincidir. El CHANGELOG llevó
dos retrocesos commiteados desde la sesión 71 sin que nada lo notara.
"""

import subprocess
import unicodedata
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
EXTENSIONES = {".py", ".md", ".toml", ".txt", ".json", ".yaml", ".yml", ".cfg", ".ini",
               ".spec", ".bat", ".ps1", ".sh", ".html", ".css", ".js"}
PERMITIDOS = {"\n", "\r", "\t"}       # el tabulador se vigila aparte en .py
# Librerías de terceros minificadas: traen U+0085 legítimo y no se editan aquí.
EXCLUIDOS = ("lib/", "core/lib/")


def _archivos():
    salida = subprocess.run(["git", "ls-files"], cwd=RAIZ, capture_output=True, text=True,
                            encoding="utf-8")
    if salida.returncode != 0:
        pytest.skip("no es un repositorio git")
    return [RAIZ / f for f in salida.stdout.splitlines()
            if Path(f).suffix.lower() in EXTENSIONES and (RAIZ / f).is_file()
            and not f.startswith(EXCLUIDOS)]


def test_sin_caracteres_de_control():
    malos = []
    for f in _archivos():
        texto = f.read_text("utf-8", errors="replace")
        for i, c in enumerate(texto):
            if unicodedata.category(c) == "Cc" and c not in PERMITIDOS:
                linea = texto.count("\n", 0, i) + 1
                malos.append(f"{f.relative_to(RAIZ)}:{linea} U+{ord(c):04X}")
                break
    assert not malos, "Caracteres de control (¿escape de un heredoc?):\n" + "\n".join(malos)


def test_sin_tabuladores_en_python():
    malos = [str(f.relative_to(RAIZ)) for f in _archivos()
             if f.suffix == ".py" and "\t" in f.read_text("utf-8", errors="replace")]
    assert not malos, f"Tabuladores en .py (¿\\t de un heredoc?): {malos}"


def test_metadata_extractor_infiere_el_creador():
    r"""La regex del creador traía dos retrocesos literales donde iba ``\b``
    (desde el commit inicial, 7-jul-2026): nunca coincidía y el campo salía
    siempre vacío. Lo encontró test_sin_caracteres_de_control (sesión 72)."""
    from core.metadata_extractor import _inferir_campo_desde_snippets
    snippets = [{"snippet": "Crónica escrita por Germán Arciniegas en Bogotá"}]
    assert _inferir_campo_desde_snippets(snippets, "creador") == "Germán Arciniegas"
