"""Servicio de entidades (extraído de app.py, sesión 71)."""

from core import servicios_entidades as SE
from core.confianza_engine import score_ner_entidad


# ── Confianza: ninguna señal inventada ───────────────────────────────────────

def test_con_todas_las_senales_el_puntaje_no_cambia():
    # Pesos 0.3/0.25/0.45 suman 1: idéntico a la fórmula anterior.
    assert score_ner_entidad(True, False, 0.8, 0.6) == round(0.3 + 0.25 * 0.8 + 0.45 * 0.6, 3)


def test_senal_ausente_no_cuenta_ni_como_cero_ni_inventada():
    solo_ner = score_ner_entidad(None, False, 0.8, None)
    assert solo_ner == 0.8
    # El cálculo anterior del panel: llm = conf + 0.05 inventado.
    inventado = score_ner_entidad(False, False, 0.8, 0.85)
    assert inventado != score_ner_entidad(False, False, 0.8, None)
    assert score_ner_entidad(None, False, 0.0, None) == 0.0


def test_calificar_no_pasa_confianza_de_llm(monkeypatch):
    vistas = []
    import core.confianza_engine as CE
    real = CE.score_ner_entidad

    def espia(en_kb, verificada, spacy_conf, llm_conf):
        vistas.append(llm_conf)
        return real(en_kb, verificada, spacy_conf, llm_conf)
    monkeypatch.setattr(CE, "score_ner_entidad", espia)
    fuente, _ = SE.fuente_para_validar(None, {"personas": {"Gaitán": ["a1"]}})
    r = SE.calificar_entidades(fuente)
    assert vistas == [None]
    # Desde memoria no hay confianza medida ni base consultada: ninguna señal,
    # puntaje 0 y semáforo rojo ("validar a mano"), no un 0.75 inventado.
    assert r[0]["entidad"] == "Gaitán" and r[0]["score"] == 0.0 and r[0]["nivel"] == "red"


def test_fuente_prefiere_la_base_y_agrupa():
    filas = [{"categoria": "PER", "texto": " Gaitán ", "articulo_id": "a1", "confianza": 0.9},
             {"categoria": "PER", "texto": "Gaitán", "articulo_id": "a2", "confianza": 0.9},
             {"categoria": "PER", "texto": "Gaitán", "articulo_id": "a2", "confianza": 0.9},
             {"categoria": "LOC", "texto": "", "articulo_id": "a3"}]
    fuente, origen = SE.fuente_para_validar(filas, {"lugares": {"X": ["a9"]}})
    assert origen == "DB"
    assert fuente == {"personas": {"Gaitán": {"arts": ["a1", "a2"], "confianza": 0.9}}}
    sin_dato, _ = SE.fuente_para_validar([{"categoria": "LOC", "texto": "Bogotá"}])
    assert sin_dato["lugares"]["Bogotá"]["confianza"] is None
    assert SE.fuente_para_validar([], {}) == ({}, "")


# ── Evolución de la red ──────────────────────────────────────────────────────

def test_indice_por_numero():
    meta = {"a1": {"numero": "E17"}, "a2": {"numero": "E18"}, "a3": {"pagina": "E18_p0003"}}
    idx = {"personas": {"Gaitán": ["a1", "a2"], "López": ["a3"]}}
    r = SE.indice_por_numero(meta, idx)
    assert r["E17"]["personas"] == {"Gaitán": ["a1"]}
    assert r["E18"]["personas"] == {"Gaitán": ["a2"]}
    assert r["E18_p00"]["personas"] == {"López": ["a3"]}
    assert SE.indice_por_numero(object(), idx) == {}  # DataFrame u otro: no disponible


# ── Búsqueda léxica ──────────────────────────────────────────────────────────

def test_busqueda_no_encuentra_terminos_dentro_de_otra_palabra():
    corpus = ["La leyenda de la parte antigua", "Una nueva ley de arte"]
    r = SE.buscar_lexico(corpus, "ley arte")
    assert [x["articulo_id"] for x in r] == ["1"]   # antes también salía el 0
    assert r[0]["similitud"] == 1.0 and r[0]["rank"] == 1


def test_busqueda_conserva_flexiones_y_respeta_k():
    corpus = ["los gobiernos liberales", "gobierno conservador", "nada que ver", ""]
    r = SE.buscar_lexico(corpus, "gobierno", k=1)
    assert len(r) == 1 and r[0]["similitud"] == 1.0
    assert len(SE.buscar_lexico(corpus, "gobierno")) == 2
    assert SE.buscar_lexico(corpus, "de") == []   # términos de 1-2 letras se ignoran
    assert len(SE.buscar_lexico(["nuevas leyes"], "ley")) == 1


def test_busqueda_usa_titulos_del_meta():
    r = SE.buscar_lexico(["texto con bogota"], "bogota", corpus_meta={"0": {"titulo": "Crónica"}})
    assert r[0]["titulo"] == "Crónica"
