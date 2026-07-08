"""tests/test_user_prefs.py — Preferencias de usuario persistentes (~/.bashkar/prefs.json)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import user_prefs  # noqa: E402


def _redirigir(monkeypatch, tmp_path):
    monkeypatch.setattr(user_prefs, "PREFS_PATH", tmp_path / ".bashkar" / "prefs.json")


def test_cargar_prefs_sin_archivo_devuelve_vacio(monkeypatch, tmp_path):
    _redirigir(monkeypatch, tmp_path)
    assert user_prefs.cargar_prefs() == {}


def test_guardar_y_obtener_pref_roundtrip(monkeypatch, tmp_path):
    _redirigir(monkeypatch, tmp_path)
    user_prefs.guardar_pref("mostrar_inicio", False)
    assert user_prefs.obtener_pref("mostrar_inicio") is False
    assert user_prefs.PREFS_PATH.exists()


def test_obtener_pref_con_default(monkeypatch, tmp_path):
    _redirigir(monkeypatch, tmp_path)
    assert user_prefs.obtener_pref("no_existe", default=42) == 42


def test_guardar_pref_no_pisa_otras_claves(monkeypatch, tmp_path):
    _redirigir(monkeypatch, tmp_path)
    user_prefs.guardar_pref("a", 1)
    user_prefs.guardar_pref("b", 2)
    prefs = user_prefs.cargar_prefs()
    assert prefs == {"a": 1, "b": 2}


def test_cargar_prefs_archivo_corrupto_no_lanza(monkeypatch, tmp_path):
    _redirigir(monkeypatch, tmp_path)
    user_prefs.PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    user_prefs.PREFS_PATH.write_text("{esto no es json", encoding="utf-8")
    assert user_prefs.cargar_prefs() == {}
