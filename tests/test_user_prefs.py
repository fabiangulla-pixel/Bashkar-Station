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


# ── Credenciales ─────────────────────────────────────────────────────────────

def _redirigir_credenciales(monkeypatch, tmp_path):
    monkeypatch.setattr(
        user_prefs, "CREDENCIALES_PATH", tmp_path / ".bashkar" / "credenciales.json"
    )


def test_es_secreto_distingue_clave_de_url_local():
    assert user_prefs.es_secreto("sk-ant-abc123")
    assert user_prefs.es_secreto("AIzaSyAbc")
    # Ollama y LM Studio se configuran con URL, no con secreto.
    assert not user_prefs.es_secreto("http://localhost:11434")
    assert not user_prefs.es_secreto("https://localhost:1234")
    assert not user_prefs.es_secreto("")
    assert not user_prefs.es_secreto(None)


def test_credenciales_roundtrip(monkeypatch, tmp_path):
    _redirigir_credenciales(monkeypatch, tmp_path)
    user_prefs.guardar_credenciales({"openai": "sk-proj-xyz"})
    assert user_prefs.cargar_credenciales() == {"openai": "sk-proj-xyz"}


def test_guardar_credenciales_vacia_borra_la_entrada(monkeypatch, tmp_path):
    _redirigir_credenciales(monkeypatch, tmp_path)
    user_prefs.guardar_credenciales({"openai": "sk-proj-xyz", "gemini": "AIzaX"})
    user_prefs.guardar_credenciales({"openai": ""})
    assert user_prefs.cargar_credenciales() == {"gemini": "AIzaX"}


def test_cargar_credenciales_corrupto_no_lanza(monkeypatch, tmp_path):
    _redirigir_credenciales(monkeypatch, tmp_path)
    user_prefs.CREDENCIALES_PATH.parent.mkdir(parents=True, exist_ok=True)
    user_prefs.CREDENCIALES_PATH.write_text("no json", encoding="utf-8")
    assert user_prefs.cargar_credenciales() == {}


def test_separar_secretos_deja_pasar_las_urls_locales():
    secretos, publicos = user_prefs.separar_secretos({
        "anthropic": "sk-ant-1",
        "openai": "",
        "ollama": "http://localhost:11434",
    })
    assert secretos == {"anthropic": "sk-ant-1"}
    assert publicos == {"ollama": "http://localhost:11434"}


def test_credenciales_no_viven_junto_a_las_prefs():
    """El archivo de secretos es distinto del de preferencias: así prefs.json
    puede compartirse para depurar sin arrastrar claves."""
    assert user_prefs.CREDENCIALES_PATH != user_prefs.PREFS_PATH
