"""Prueba funcional (sin micrófono) del botón «🎙 Referencia humana» del
Etiquetador (sesión 74): abre la ventana, simula dictado con un
DictadoSession falso y verifica que lo guardado sea legible por
core.benchmark_regresion. No usa clics reales ni audio — invoca los
métodos _etzr_* directo, como test_etz_vinculo_gui.py hace con _etz_*."""

import json

import pytest

tk = pytest.importorskip("tkinter")


@pytest.fixture
def app_etz():
    import app as appmod
    appmod.BashkarApp._cargar_ultimo_proyecto = lambda self: None
    try:
        a = appmod.BashkarApp()
    except tk.TclError:
        pytest.skip("Sin entorno gráfico para tkinter")

    a._mostrar_pagina("etz")
    for _ in range(3):
        a.update()

    yield a
    try:
        a.destroy()
    except Exception:
        pass


def _bench(tmp_path):
    man = {"corpus_id": "prueba", "referencia": {"tipo": "humana", "transcriptor": "F. G."},
           "casos": [{"page_id": "p0001", "referencia": "referencia/p0001.txt"}]}
    (tmp_path / "benchmark.json").write_text(json.dumps(man), encoding="utf-8")
    return tmp_path


def _apuntar_carpeta_default(monkeypatch, carpeta):
    """El panel busca el benchmark en Path("benchmark/estampa-1939"); en el
    test lo redirigimos a la carpeta temporal, dejando intacto cualquier
    otro uso real de Path dentro del módulo."""
    import paneles.etiquetador_zonas as mod
    real_path = mod.Path

    def fake_path(arg="", *a, **k):
        if arg == "benchmark/estampa-1939":
            return carpeta
        return real_path(arg, *a, **k)

    monkeypatch.setattr(mod, "Path", fake_path)


def test_sin_zonas_etiquetadas_avisa_y_no_abre_ventana(app_etz, monkeypatch):
    a = app_etz
    a._etz_zonas = []
    avisos = []
    monkeypatch.setattr(
        "tkinter.messagebox.showwarning", lambda *a_, **k: avisos.append(a_))
    a._etz_dictar_referencia_zonas()
    assert avisos and not hasattr(a, "_etzr_win")


def test_ventana_abre_una_caja_por_zona_en_orden_de_lectura(app_etz, tmp_path, monkeypatch):
    a = app_etz
    from core.zone_labeler import Zona
    z1 = Zona(tipo="titulo", x0=0.1, y0=0.1, x1=0.9, y1=0.2, orden=2)
    z2 = Zona(tipo="cuerpo", x0=0.1, y0=0.2, x1=0.9, y1=0.4, orden=1)
    a._etz_zonas = [z1, z2]
    a._etz_pagina.set("p0001")
    a._etz_numero.set("num1")

    carpeta = _bench(tmp_path)
    _apuntar_carpeta_default(monkeypatch, carpeta)

    a._etz_dictar_referencia_zonas()
    for _ in range(3):
        a.update()

    assert len(a._etzr_cajas) == 2
    # primera caja en la lista corresponde a la zona de orden 1 (cuerpo)
    assert a._etzr_cajas[0][0] is z2
    assert a._etzr_cajas[1][0] is z1
    a._etzr_win.destroy()


def test_dictado_falso_inserta_en_la_zona_activa_y_guardar_escribe_json(
        app_etz, tmp_path, monkeypatch):
    a = app_etz
    from core.zone_labeler import Zona
    z1 = Zona(tipo="cuerpo", x0=0.1, y0=0.1, x1=0.9, y1=0.3, orden=1)
    a._etz_zonas = [z1]
    a._etz_pagina.set("p0001")
    a._etz_numero.set("num1")

    carpeta = _bench(tmp_path)
    _apuntar_carpeta_default(monkeypatch, carpeta)

    a._etz_dictar_referencia_zonas()
    for _ in range(3):
        a.update()

    class SesionFalsa:
        """Sustituye a core.voice_dictation.DictadoSession: entrega un texto
        fijo sin tocar micrófono ni red, igual que pediría un test offscreen."""
        def __init__(self, callback, idioma="es-CO", modo_online=True):
            self.callback = callback
        def iniciar(self):
            self.callback("el gobierno dicta esto")
        def detener(self):
            pass
        def estado(self):
            return "detenido"

    import core.voice_dictation as vd
    monkeypatch.setattr(vd, "DictadoSession", SesionFalsa)

    a._etzr_txt_activo = a._etzr_cajas[0][1]
    a._etzr_dictar_toggle()
    for _ in range(3):
        a.update()

    assert a._etzr_cajas[0][1].get("1.0", "end").strip() == "el gobierno dicta esto"

    a._etzr_guardar(carpeta, "p0001")
    ruta = carpeta / "referencia" / "p0001.json"
    assert ruta.exists()

    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert datos["zonas"][0]["texto"] == "el gobierno dicta esto"
    assert datos["zonas"][0]["tipo"] == "cuerpo"
    assert datos["transcriptor"] == "F. G."

    a._etzr_win.destroy()
