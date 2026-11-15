"""LICENCIAS_DE_TERCEROS.md declara cada dependencia y cada modelo (hito B4)."""
import importlib.util
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def _mod():
    spec = importlib.util.spec_from_file_location(
        "verificar_licencias", RAIZ / "scripts" / "verificar_licencias.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_no_falta_ninguna_dependencia_ni_modelo():
    assert _mod().faltantes() == []


def test_una_dependencia_nueva_sin_declarar_se_detecta(tmp_path, monkeypatch):
    m = _mod()
    lock = tmp_path / "lock.txt"
    lock.write_text((RAIZ / "requirements.lock.txt").read_text(encoding="utf-8")
                    + "\npaquete-inventado==1.0\n", encoding="utf-8")
    monkeypatch.setattr(m, "LOCK", lock)
    assert m.faltantes() == ["paquete paquete-inventado"]


def test_los_avisos_clave_estan_en_el_documento():
    texto = (RAIZ / "LICENCIAS_DE_TERCEROS.md").read_text(encoding="utf-8")
    for clave in ("AGPL-3.0", "qwen-research", "GPL-3.0", "No se distribuye",
                  "Rail-M", "No declarada"):
        assert clave in texto, clave
