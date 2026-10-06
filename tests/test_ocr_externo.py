"""core.ocr.externo: el protocolo del trabajador persistente, con un script falso."""

import sys
import textwrap

import pytest

from core.ocr.externo import MotorExterno, TrabajadorExterno

_FALSO = textwrap.dedent(r'''
    import json, sys
    print("ruido de arranque", file=sys.stderr)
    sys.stdout.write(json.dumps({"listo": True, "version": "falso 9"}) + "\n"); sys.stdout.flush()
    for linea in sys.stdin:
        p = json.loads(linea)
        if p["imagen"].endswith("malo.png"):
            r = {"ok": False, "error": "no se pudo leer"}
        else:
            r = {"ok": True, "texto": "hola " + p["imagen"][-8:], "confianza": 77.0,
                 "bloques": [{"texto": "hola", "bbox": [1, 2, 3, 4], "tipo": "titulo", "orden": 1}]}
        sys.stdout.write(json.dumps(r) + "\n"); sys.stdout.flush()
''')


@pytest.fixture
def script(tmp_path):
    s = tmp_path / "falso_trabajador.py"
    s.write_text(_FALSO, "utf-8")
    return s


def test_trabajador_arranca_una_vez_y_atiende_varias(script, tmp_path):
    t = TrabajadorExterno(sys.executable, script, timeout_arranque=60)
    try:
        a = t.pedir({"imagen": str(tmp_path / "p001.png")}, timeout=60)
        pid = t._proc.pid
        b = t.pedir({"imagen": str(tmp_path / "p002.png")}, timeout=60)
        assert t._proc.pid == pid                       # no se relanzó
        assert t.version == "falso 9" and a["texto"] != b["texto"]
    finally:
        t.cerrar()
    assert t._proc is None


def test_error_del_trabajador_es_excepcion(script, tmp_path):
    t = TrabajadorExterno(sys.executable, script, timeout_arranque=60)
    try:
        with pytest.raises(RuntimeError, match="no se pudo leer"):
            t.pedir({"imagen": str(tmp_path / "malo.png")}, timeout=60)
        # y sigue vivo para la siguiente
        assert t.pedir({"imagen": str(tmp_path / "p003.png")}, timeout=60)["ok"]
    finally:
        t.cerrar()


def test_trabajador_que_muere_al_arrancar_da_error_claro(tmp_path):
    malo = tmp_path / "muere.py"
    malo.write_text("import sys; print('falta un modulo', file=sys.stderr); sys.exit(3)", "utf-8")
    t = TrabajadorExterno(sys.executable, malo, timeout_arranque=60)
    with pytest.raises(RuntimeError, match="no respondió"):
        t.pedir({"imagen": "x"}, timeout=60)


def test_motor_externo_convierte_a_resultado(script, tmp_path, monkeypatch):
    class Falso(MotorExterno):
        nombre = etiqueta = "falso"
        script = "falso_trabajador.py"

    monkeypatch.setattr("core.ocr.externo.DIR_TRABAJADORES", script.parent)
    m = Falso()
    monkeypatch.setattr(m, "_python", lambda: sys.executable)
    try:
        r = m.reconocer(tmp_path / "p0001.png")
        assert r.motor == "falso" and r.confianza == 77.0
        assert r.bloques[0].tipo == "titulo" and r.bloques[0].bbox == (1, 2, 3, 4)
        assert m.version() == "falso 9"
    finally:
        m.liberar()


def test_venv_inexistente_explica_que_falta(monkeypatch, tmp_path):
    class Falso(MotorExterno):
        nombre = etiqueta = "falso"
        variable_venv = "BASHKAR_VENV_FALSO"
        paquete = "x"
    monkeypatch.setenv("BASHKAR_VENV_FALSO", str(tmp_path / "no-existe"))
    assert "falta el venv" in Falso().motivo_no_disponible()
