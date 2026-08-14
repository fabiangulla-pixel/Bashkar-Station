"""Tests de la imagen nueva de la interfaz (sesión 56).

Dos capas separadas a propósito:

1. El adaptador `state_from_bashkar` y los tokens de `ui_redesign`, que son
   datos puros y se prueban sin abrir ninguna ventana. Ahí vive el riesgo real:
   `ST.corpus_meta` y `ST.df_articulos` son DataFrames y cualquier `if df` o
   `df in (None, "")` los hace estallar (bug de la sesión 43).
2. El panel «Inicio» montado en la ventana de verdad, con la app headless.
"""

import pytest

import ui_redesign
from core.estado import Estado
from ui_redesign import Theme, state_from_bashkar

tk = pytest.importorskip("tkinter")


# ─────────────────────────── adaptador de estado ────────────────────────────

def test_estado_vacio_no_revienta():
    st = Estado()
    d = state_from_bashkar(st)
    assert d.pages_total == 0
    assert d.articles == 0
    assert d.entities == 0
    assert d.ocr_quality is None
    assert [p.key for p in d.pipeline] == [
        "ocr", "norm", "seg", "ner", "anal", "export"]
    assert all(p.status == "pending" for p in d.pipeline)


def test_adaptador_con_dataframes_reales():
    """El caso que rompía: DataFrames donde antes se evaluaba la verdad."""
    pd = pytest.importorskip("pandas")
    st = Estado()
    st.publicacion = "Revista Estampa"
    st.periodo = "1938-1940"
    st.corpus_meta = pd.DataFrame({
        "numero": ["mar_1939"] * 3,
        "confianza": [70.0, 80.0, None],
    })
    st.df_articulos = pd.DataFrame({"id": ["a", "b"]})
    st.corpus_txt = ["texto uno", "texto dos", "   "]

    d = state_from_bashkar(st)
    assert d.publication == "Revista Estampa"
    assert d.period == "1938-1940"
    assert d.pages_total == 3
    assert d.pages_processed == 2          # la tercera está en blanco
    assert d.articles == 2
    assert d.ocr_quality == pytest.approx(75.0)   # ignora el None


def test_etapas_stale_se_muestran_como_aviso():
    st = Estado()
    st.marcar_etapa("ocr", "ready")
    st.marcar_etapa("norm", "ready")
    st.marcar_etapa("ocr", "stale")        # propaga stale hacia adelante
    d = state_from_bashkar(st)
    estados = {p.key: p.status for p in d.pipeline}
    assert estados["ocr"] == "warning"
    assert estados["norm"] == "warning"
    assert estados["seg"] == "pending"


def test_ner_y_exportacion_se_deducen_de_los_artefactos():
    st = Estado()
    st.indice_ner_global = {"personas": {"Franco": ["a1"], "López": ["a2"]},
                            "lugares": {"Bogotá": ["a1"]}}
    st.xlsx_path = "C:/tmp/corpus.xlsx"
    d = state_from_bashkar(st)
    assert d.entities == 3
    estados = {p.key: p.status for p in d.pipeline}
    assert estados["ner"] == "completed"
    assert estados["export"] == "completed"


def test_ia_externa_apaga_el_modo_local():
    st = Estado()
    assert state_from_bashkar(st).local_mode is True
    st.ia_habilitada = True
    d = state_from_bashkar(st)
    assert d.local_mode is False
    assert d.external_ai_enabled is True


# ────────────────────────── identidad visual ────────────────────────────────

def test_la_paleta_de_app_sale_de_los_tokens():
    """Si alguien vuelve a incrustar colores en app.py, esto lo delata."""
    import app as appmod

    assert appmod._PALETA_DARK["CONTENT_BG"] == Theme.BG
    assert appmod._PALETA_DARK["AZ3"] == Theme.COPPER
    assert appmod._PALETA_DARK["TXT_PRI"] == Theme.TEXT
    # Las dos paletas tienen que ofrecer exactamente las mismas claves: el
    # modo claro se aplica con _aplicar_paleta y una clave de menos deja una
    # variable global apuntando al color del otro tema.
    assert set(appmod._PALETA_DARK) == set(appmod._PALETA_LIGHT)


def test_no_quedan_colores_de_vs_code_en_app():
    """La identidad ya no imita a VS Code ni al dark de GitHub."""
    from pathlib import Path

    import app as appmod

    fuente = Path(appmod.__file__).read_text(encoding="utf-8")
    for viejo in ("#0078D4", "#1E1E1E", "#252526", "#0D1117", "#CDD6F4",
                  "#F59E0B", "#1C2128"):
        assert viejo not in fuente, f"{viejo} sigue incrustado en app.py"


# ──────────────────────────── panel Inicio ──────────────────────────────────

@pytest.fixture
def app_inicio():
    import app as appmod
    appmod.BashkarApp._cargar_ultimo_proyecto = lambda self: None
    try:
        a = appmod.BashkarApp()
    except tk.TclError:
        pytest.skip("Sin entorno gráfico para tkinter")
    for _ in range(3):
        a.update()
    yield a, appmod
    try:
        a.destroy()
    except Exception:
        pass


def test_inicio_es_la_pagina_de_arranque(app_inicio):
    a, appmod = app_inicio
    assert a._pagina_activa.get() == "inicio"
    assert a._ctx_activo.get() == "inicio"
    assert hasattr(a, "_inicio_shell")


def test_el_tablero_se_monta_sin_chrome(app_inicio):
    a, _ = app_inicio
    shell = a._inicio_shell
    assert shell.chrome is False
    assert shell.topbar is None and shell.sidebar is None
    # …pero el tablero sí existe y tiene tarjetas dentro.
    assert shell.dashboard.winfo_children()


def test_el_tablero_relee_el_estado_al_volver(app_inicio):
    a, appmod = app_inicio
    appmod.ST.publicacion = "Revista Estampa"
    appmod.ST.corpus_txt = ["una página con texto"]
    a._mostrar_pagina("cfg")
    a._mostrar_pagina("inicio")
    for _ in range(3):
        a.update()
    a._inicio_refrescar()
    assert a._inicio_shell.state.publication == "Revista Estampa"
    assert a._inicio_shell.state.pages_processed == 1


def test_las_acciones_navegan_a_paginas_reales(app_inicio):
    a, _ = app_inicio
    for clave, destino in a._INICIO_DESTINOS.items():
        a._inicio_navegar(clave)
        assert a._pagina_activa.get() == destino, clave


def test_el_nombre_del_proyecto_llega_a_la_topbar(app_inicio):
    """Hasta la sesión 56 el Label del sidebar pisaba al de la topbar."""
    a, _ = app_inicio
    a._set_pub_hdr("Revista Estampa · 1939")
    assert a._lbl_pub_hdr.cget("text") == "Revista Estampa · 1939"


def test_la_pastilla_de_ia_sigue_al_interruptor(app_inicio):
    a, appmod = app_inicio
    a._var_ia_habilitada.set(True)
    a._topbar_toggle_ia()
    assert "activa" in a._pill_ia[2].cget("text")
    a._var_ia_habilitada.set(False)
    a._topbar_toggle_ia()
    assert "desactivada" in a._pill_ia[2].cget("text")


def test_el_tema_claro_alcanza_al_tablero(app_inicio):
    """
    Cambiar de tema tiene que reescribir también los tokens de ui_redesign.
    Si no, la ventana se aclara y el panel Inicio se queda oscuro dentro.
    """
    a, appmod = app_inicio
    try:
        a._toggle_theme()                      # oscuro → claro
        for _ in range(3):
            a.update()
        assert Theme.BG == appmod._PALETA_LIGHT["CONTENT_BG"]
        assert a._inicio_shell.dashboard.cget("bg") == \
            appmod._PALETA_LIGHT["CONTENT_BG"]
        assert a._contenedores_pagina["inicio"].cget("bg") == \
            appmod._PALETA_LIGHT["CONTENT_BG"]
    finally:
        a._toggle_theme()                      # y de vuelta a oscuro
        for _ in range(3):
            a.update()
    assert Theme.BG == appmod._PALETA_DARK["CONTENT_BG"]


def test_los_componentes_no_congelan_el_color_en_la_firma():
    """
    `Card` y `HoverButton` deben resolver el color al construirse, no en el
    valor por defecto del parámetro: eso se evalúa al definir la clase y
    `aplicar_tema` ya no lo alcanzaría nunca.
    """
    import inspect

    from ui_redesign import Card, HoverButton

    for clase in (Card, HoverButton):
        for nombre, p in inspect.signature(clase.__init__).parameters.items():
            if nombre in ("bg", "fg", "hover_bg", "active_fg", "font"):
                assert p.default is None, f"{clase.__name__}.{nombre}"


def test_el_tablero_no_secuestra_la_rueda_del_raton(app_inicio):
    """
    Un bind_all sobre <MouseWheel> dejaría sin scroll a los otros 30 paneles;
    por eso el tablero engancha la rueda widget a widget.
    """
    import re
    from pathlib import Path

    a, _ = app_inicio
    codigo = Path(ui_redesign.__file__).read_text(encoding="utf-8")
    # Se busca la llamada, no la palabra: el comentario que explica por qué no
    # se usa bind_all también contiene el término.
    assert not re.search(r"\.bind_all\s*\(", codigo)
    assert a._inicio_shell.dashboard_canvas.bind("<MouseWheel>")
