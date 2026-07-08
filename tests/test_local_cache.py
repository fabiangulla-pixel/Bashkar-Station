"""tests/test_local_cache.py — Caché derivada siempre en disco local."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import local_cache  # noqa: E402


def test_ruta_cache_usa_localappdata(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    destino = local_cache.ruta_cache("thumbs")
    assert destino == tmp_path / "BashkarStation" / "thumbs"
    assert destino.exists()


def test_ruta_cache_fallback_sin_localappdata(monkeypatch, tmp_path):
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    destino = local_cache.ruta_cache("thumbs")
    assert destino == tmp_path / ".cache" / "bashkar_station" / "thumbs"
    assert destino.exists()


def test_clave_cache_estable_para_mismo_archivo(tmp_path):
    f = tmp_path / "img.png"
    f.write_bytes(b"contenido")
    assert local_cache.clave_cache(f) == local_cache.clave_cache(f)


def test_clave_cache_cambia_si_el_archivo_cambia(tmp_path):
    f = tmp_path / "img.png"
    f.write_bytes(b"contenido")
    clave_antes = local_cache.clave_cache(f)
    time.sleep(0.01)
    f.write_bytes(b"contenido modificado")
    clave_despues = local_cache.clave_cache(f)
    assert clave_antes != clave_despues


def test_clave_cache_archivo_inexistente_no_lanza(tmp_path):
    f = tmp_path / "no_existe.png"
    assert isinstance(local_cache.clave_cache(f), str)
