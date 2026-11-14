"""Las exportaciones declaran los metadatos reales del proyecto.

Fallo 3 del diagnóstico MVP (14-nov-2026): todo TEI decía «Corpus Estampa»,
editor «Instituto Caro y Cuervo», lugar «Bogotá», fuente «Revista Estampa
1930-1940» y que las entidades se identificaron «mediante NER híbrido (spaCy
+ Claude)» con «corrección asistida por IA», aunque no se hubiera usado IA. El
BibTeX ponía año 1935 y editor ICyC si no los sabía; el Excel decía siempre
«ESTAMPA» y «enero–junio 1939».
"""
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

PROHIBIDO_SIN_DATOS = ("spaCy + Claude", "Corpus Estampa", "enero–junio",
                       "Instituto Caro y Cuervo", "Bogotá", "1930-1940",
                       "asistida por IA", "1935")

ESTAMPA = SimpleNamespace(
    publicacion="Estampa", periodo="enero–mayo de 1939",
    perfil_corpus={}, ner_motor="BERT (mrm8488/bert-spanish-cased-finetuned-ner)",
    corpus_meta=pd.DataFrame({"metodo": ["vision_ocr", "vision_ocr"]}),
    config_exportacion={
        "lugar": "Bogotá",
        "creditos": [
            {"rol": "Financiación",
             "nombre": "Beca a Nuevos Investigadores en Estudios Editoriales, "
                       "Ministerio de las Culturas, las Artes y los Saberes de Colombia"},
            {"rol": "Institución mentora de la beca (sin afiliación)",
             "nombre": "Instituto Caro y Cuervo"},
        ],
    })

OTRO = SimpleNamespace(
    publicacion="Caras y Caretas", periodo="1920", perfil_corpus={},
    ner_motor="spaCy es_core_news_sm", corpus_meta=None, config_exportacion={})


def _tei(tmp_path, st, nombre, historial=None) -> str:
    from core.metadatos_exportacion import metadatos_proyecto
    from core.tei_engine import exportar_corpus_tei
    ruta = tmp_path / f"{nombre}.xml"
    exportar_corpus_tei([{"id": "a-a0001", "titulo": "T", "texto": "Texto."}], ruta,
                        metadatos=metadatos_proyecto(st, nombre, historial))
    return ruta.read_text(encoding="utf-8")


def test_tei_de_otro_corpus_no_trae_nada_de_estampa(tmp_path):
    xml = _tei(tmp_path, OTRO, "Prueba Caras y Caretas")
    assert "Caras y Caretas" in xml and "1920" in xml
    assert "spaCy es_core_news_sm" in xml
    for frase in PROHIBIDO_SIN_DATOS:
        assert frase not in xml, frase


def test_tei_de_estampa_declara_sus_creditos_y_herramientas(tmp_path):
    xml = _tei(tmp_path, ESTAMPA, "Estampa 1939")
    assert "enero–mayo de 1939" in xml
    assert "Institución mentora de la beca (sin afiliación)" in xml
    assert "Ministerio de las Culturas" in xml
    assert "vision_ocr" in xml and "mrm8488" in xml
    assert "Bogotá" in xml                       # declarado en el proyecto
    # El ICyC aparece como mentor, no como editor del corpus.
    assert "<publisher>Instituto Caro y Cuervo</publisher>" not in xml
    for frase in ("spaCy + Claude", "enero–junio", "asistida por IA", "1930-1940"):
        assert frase not in xml, frase


def test_tei_declara_ia_solo_si_consta(tmp_path):
    sin = _tei(tmp_path, OTRO, "sin_ia")
    con = _tei(tmp_path, OTRO, "con_ia", historial=[{"proveedor": "anthropic"}])
    assert "No consta uso de servicios de IA" in sin and "anthropic" not in sin
    assert "Se usó IA de: anthropic" in con


def test_tei_sigue_siendo_valido(tmp_path):
    from core.tei_engine import validar_tei
    _tei(tmp_path, ESTAMPA, "valido")
    assert validar_tei(tmp_path / "valido.xml") == []


def test_bibtex_sin_anio_ni_editor_inventados(tmp_path):
    from core.tei_engine import exportar_bibtex
    ruta = tmp_path / "x.bib"
    exportar_bibtex([{"id": "a1", "titulo": "T"}], ruta)
    bib = ruta.read_text(encoding="utf-8")
    assert "1935" not in bib and "Instituto Caro y Cuervo" not in bib
    exportar_bibtex([{"id": "a1", "titulo": "T"}], ruta, fuente="Estampa",
                    periodo="enero–mayo de 1939")
    bib = ruta.read_text(encoding="utf-8")
    assert "year = {1939}" in bib and "journal = {Estampa}" in bib


def test_excel_usa_publicacion_y_periodo_del_proyecto(tmp_path):
    from openpyxl import load_workbook

    from core.excel_export import construir_excel_completo, generar_figuras_completas
    datos = {
        "publicacion": "Caras y Caretas", "periodo": "1920",
        "df_firmas": pd.DataFrame({"numero": ["n1"], "firma": ["X"]}),
        "df_secciones": pd.DataFrame({"numero": ["n1"], "seccion": ["Ed"], "menciones": [2]}),
        "df_campos": pd.DataFrame({"numero": ["n1"], "politica": [1.0]}),
        "df_temas": pd.DataFrame({"tema": [1], "palabras_clave": ["a, b"]}),
        "df_doc_temas": None,
        "df_articulos": pd.DataFrame({"numero": ["n1"], "titulo": ["A"], "autor": ["X"],
                                      "seccion": ["Ed"], "palabras": [100]}),
        "datos_visual": None, "datos_comparativo": None,
    }
    out = construir_excel_completo(datos, generar_figuras_completas(datos),
                                   tmp_path / "x.xlsx")
    ws = load_workbook(Path(out)).worksheets[0]
    assert "CARAS Y CARETAS" in ws["A1"].value and "ESTAMPA" not in ws["A1"].value
    assert "1920" in ws["A2"].value and "enero–junio" not in ws["A2"].value


def test_creditos_y_motor_ner_se_guardan_en_el_proyecto(tmp_path, monkeypatch):
    import core.project_manager as pm
    from core import user_prefs
    from core.estado import Estado
    monkeypatch.setattr(pm, "_dir_proyectos", lambda: tmp_path)
    monkeypatch.setattr(user_prefs, "CREDENCIALES_PATH", tmp_path / "c.json")
    ruta = pm.nuevo_proyecto("Metadatos", "Estampa", "enero–mayo de 1939")
    st = Estado()
    st.config_exportacion = ESTAMPA.config_exportacion
    st.ner_motor = ESTAMPA.ner_motor
    pm.guardar_proyecto(ruta, st)
    st2 = Estado()
    pm.cargar_proyecto(ruta, st2)
    assert st2.config_exportacion == ESTAMPA.config_exportacion
    assert st2.ner_motor == ESTAMPA.ner_motor
