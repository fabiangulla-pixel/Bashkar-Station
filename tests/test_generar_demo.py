"""Demo pública (bloque D de PLAN_MVP.md): generador y coherencia de cifras."""
import importlib.util
import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DATOS = RAIZ / "demo" / "datos"


def _mod():
    spec = importlib.util.spec_from_file_location("generar_demo", RAIZ / "scripts" / "generar_demo.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_paginas_y_etiquetas():
    m = _mod()
    assert m.paginas_de("p0004-p0005-p0006") == ["p0004", "p0005", "p0006"]
    assert m.paginas_de("p0001") == ["p0001"]
    assert m.paginas_de(None) == []
    assert m.etiqueta_numero("rev_estampa_abr_1939") == "Abril de 1939"


def test_grafo_une_solo_lo_que_comparte_unidades():
    m = _mod()
    ents = [{"t": "A", "c": "personas", "u": ["u1", "u2", "u3"]},
            {"t": "B", "c": "lugares", "u": ["u1", "u2"]},
            {"t": "C", "c": "organizaciones", "u": ["u3"]},
            {"t": "1939", "c": "fechas", "u": ["u1", "u2"]}]
    g = m.construir_grafo(ents, n_nodos=10, peso_min=2)
    nombres = {n["id"]: n["t"] for n in g["nodos"]}
    assert "1939" not in nombres.values()          # las fechas no van al grafo
    pares = {frozenset((nombres[a["a"]], nombres[a["b"]])) for a in g["aristas"]}
    assert pares == {frozenset(("A", "B"))}        # A-C solo comparte 1 unidad


def test_los_datos_publicados_coinciden_con_la_verificacion():
    # Las cifras de la demo salen de los datos; el informe de verificación,
    # de la corrida con la interfaz. Si divergen, una de las dos está mal.
    corpus = json.loads((DATOS / "corpus.json").read_text(encoding="utf-8"))
    k = corpus["cifras"]
    informe = (RAIZ / "docs" / "verificacion_corpus_estampa.md").read_text(encoding="utf-8")

    def cifra(etiqueta):
        m = re.search(etiqueta + r"[^\n]*?\|\s*\*{0,2}([\d.]+)", informe)
        return int(m.group(1).replace(".", ""))
    assert k["paginas"] == 792 and k["unidades"] == 639
    assert k["entidades_unicas"] == cifra(r"\| Únicas")
    assert k["menciones"] == cifra(r"\| Pares entidad")
    assert k["entidades_canonicas"] == cifra(r"\| Entidades canónicas")
    assert k["relaciones"] == cifra(r"\| Relaciones")


def test_cada_unidad_esta_en_su_numero_y_sus_paginas_existen():
    corpus = json.loads((DATOS / "corpus.json").read_text(encoding="utf-8"))
    total = 0
    for n in corpus["numeros"]:
        datos = json.loads((DATOS / "numeros" / f"{n['id']}.json").read_text(encoding="utf-8"))
        paginas = {p["p"] for p in datos["paginas"]}
        assert len(paginas) == n["paginas"]
        for u in datos["unidades"]:
            assert u["id"].startswith(n["id"] + "-a")
            assert set(u["paginas"]) <= paginas, u["id"]
        total += len(datos["unidades"])
    assert total == corpus["cifras"]["unidades"]


def test_el_tei_publicado_trae_las_entidades():
    from core.tei_engine import contar_entidades_en_tei, validar_tei
    tei = DATOS / "descargas" / "corpus_tei.xml"
    assert validar_tei(tei, entidades_esperadas=1) == []
    assert contar_entidades_en_tei(tei) > 13000


def test_la_plantilla_muestra_el_aviso_de_la_bnc():
    html = (RAIZ / "demo" / "plantilla" / "index.html").read_text(encoding="utf-8")
    assert "autorización de la" in html and "Biblioteca Nacional de Colombia" in html


def test_la_portada_no_es_el_lomo_del_volumen():
    m = _mod()
    paginas = [{"p": "p0001", "texto": "La imagen que se muestra corresponde al lomo " * 5},
               {"p": "p0002", "texto": "SECCION DE ENCUADERNACION BIBLIOTECA NACIONAL"},
               {"p": "p0003", "texto": ""},
               {"p": "p0004", "texto": "BIBLIOTECA NACIONAL DE COLOMBIA ENERO 14 estampa"}]
    assert m.pagina_portada(paginas) == "p0004"
    assert m.pagina_portada([{"p": "p0001", "texto": "x " * 500}]) == "p0001"


def test_las_variantes_de_escritura_se_funden_sin_perder_unidades():
    m = _mod()
    ents = [{"t": "BOGOTA", "c": "lugares", "u": ["u3", "u1"]},
            {"t": "Bogotá", "c": "lugares", "u": ["u1", "u2"]},
            {"t": "Bogotá", "c": "organizaciones", "u": ["u9"]},
            {"t": "Hitler", "c": "personas", "u": ["u1"]}]
    r = m.fundir_variantes(ents)
    bog = next(e for e in r if e["c"] == "lugares")
    assert bog["t"] == "Bogotá" and bog["f"] == ["BOGOTA"]      # a igualdad, no la de mayúsculas
    assert sorted(bog["u"]) == ["u1", "u2", "u3"]
    assert len(r) == 3 and "f" not in next(e for e in r if e["t"] == "Hitler")
    assert any(e["c"] == "organizaciones" and e["t"] == "Bogotá" for e in r)   # otra categoría no se mezcla


def test_la_descripcion_del_modelo_no_pasa_por_transcripcion():
    m = _mod()
    assert m.es_descripcion_del_modelo("La imagen que se muestra corresponde al lomo de un libro")
    assert m.es_descripcion_del_modelo("Esta página no contiene texto legible para transcribir.")
    assert not m.es_descripcion_del_modelo("La imagen de la Virgen fue llevada en procesión")
    assert not m.es_descripcion_del_modelo("ESTAMPAS DEL MUNDO")
