"""GEXF del grafo canónico (extraído de app.py)."""

import json
from xml.etree import ElementTree as ET

from core.exploradores import exportar_gexf

NS = {"g": "http://gexf.net/1.3"}


def test_nombres_con_comillas_y_confianza_nula_dan_xml_valido(tmp_path):
    grafo = {"nodos": [{"id": "Q1", "nombre": 'El "Tiempo" & <Cía>', "tipo": "ORG"},
                       {"id": "Q2", "nombre": "Gaitán"}],
             "aristas": [{"origen_id": "Q1", "destino_id": "Q2",
                          "predicado": "menciona", "confianza": None}]}
    r = exportar_gexf(grafo, tmp_path / "g.gexf")
    assert (r["n_nodos"], r["n_aristas"]) == (2, 1)
    raiz = ET.parse(tmp_path / "g.gexf").getroot()
    nodo = raiz.find(".//g:node[@id='Q1']", NS)
    assert nodo.get("label") == 'El "Tiempo" & <Cía>'
    assert raiz.find(".//g:edge", NS).get("weight") == "1.0"


def test_deja_manifiesto_de_proveniencia(tmp_path):
    exportar_gexf({"nodos": [], "aristas": []}, tmp_path / "g.gexf")
    man = json.loads((tmp_path / "g.gexf.proveniencia.json").read_text(encoding="utf-8"))
    assert man["formato"] == "GEXF"
