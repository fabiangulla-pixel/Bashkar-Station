"""Identificadores estables de artículo y entidades en el TEI.

Fallo 2 del diagnóstico MVP (14-nov-2026): el NER indexaba por TÍTULO del
artículo y el exportador TEI buscaba ``art_0000``…: el TEI nunca traía
entidades (0 de 161 en la muestra real de Estampa, abril de 1939), y
``validar_tei()`` lo daba por válido. Además, dos artículos con el mismo
título se fundían en uno.
"""
import json
from pathlib import Path

import pandas as pd

FIXTURE = Path(__file__).parent / "fixtures" / "ner_estampa_abr1939_muestra.json"


def _muestra():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _entidades_exportables(indice) -> set:
    # El TEI omite entidades de 2 caracteres o menos (ruido de OCR).
    return {(cat, e) for cat, ents in indice.items() for e in ents if len(e.strip()) > 2}


# ── Identificadores ───────────────────────────────────────────────────────────

def test_segmentar_numero_asigna_ids_unicos(tmp_path):
    from core.article_segmenter import segmentar_numero
    carpeta = tmp_path / "rev_x_1939"
    carpeta.mkdir()
    for i in range(1, 4):
        (carpeta / f"p{i:04d}.txt").write_text(
            f"TITULO {i}\n\n" + "palabra " * 300, encoding="utf-8")
    arts = segmentar_numero(tmp_path, "rev_x_1939")
    assert arts, "la segmentación no devolvió artículos"
    ids = [a["id"] for a in arts]
    assert len(set(ids)) == len(ids)
    assert all(i.startswith("rev_x_1939-a") for i in ids)


def test_asignar_ids_respeta_los_existentes_y_es_determinista():
    from core.article_segmenter import asignar_ids_articulos
    arts = [{"numero": "n1", "titulo": "Moda"}, {"numero": "n1", "id": "n1-a0001"},
            {"numero": "n1", "titulo": "Moda"}]
    asignar_ids_articulos(arts)
    assert [a["id"] for a in arts] == ["n1-a0002", "n1-a0001", "n1-a0003"]


# ── TEI con entidades ─────────────────────────────────────────────────────────

def _estado_migrado():
    from core.estado import Estado
    from core.project_manager import migrar_ids_articulos
    m = _muestra()
    st = Estado()
    st.df_articulos = pd.DataFrame(m["articulos"])
    st.indice_ner_global = m["indice_ner_global"]
    res = migrar_ids_articulos(st)
    return st, res


def test_migracion_traduce_titulos_a_ids_sin_perder_entidades():
    st, res = _estado_migrado()
    assert res["migrado"] and res["titulos_ambiguos"] == 0
    ids = set(st.df_articulos["id"])
    pares = [(c, e, a) for c, ents in st.indice_ner_global.items()
             for e, arts in ents.items() for a in arts]
    assert len(pares) == 169
    assert all(a in ids for _, _, a in pares)


def test_tei_de_la_muestra_contiene_todas_sus_entidades(tmp_path):
    import xml.etree.ElementTree as ET

    from core.servicios_exportacion import articulos_para_tei
    from core.tei_engine import TEI_NS, exportar_corpus_tei, validar_tei
    st, _ = _estado_migrado()
    arts = articulos_para_tei(["texto"] * 5, st.indice_ner_global,
                              articulos=st.df_articulos)
    ruta = tmp_path / "corpus.xml"
    exportar_corpus_tei(arts, ruta)

    root = ET.parse(ruta).getroot()
    en_tei = {(a.get("type"), a.text) for a in root.iter(f"{{{TEI_NS}}}annotation")}
    esperadas = _entidades_exportables(st.indice_ner_global)
    assert len(esperadas) >= 150          # 161 menos las de ≤2 caracteres
    assert en_tei == esperadas
    assert validar_tei(ruta, entidades_esperadas=161) == []


def test_validar_tei_falla_si_el_proyecto_tiene_entidades_y_el_tei_ninguna(tmp_path):
    from core.tei_engine import exportar_corpus_tei, validar_tei
    ruta = tmp_path / "sin_entidades.xml"
    exportar_corpus_tei([{"id": "a1", "texto": "Texto sin entidades."}], ruta)
    errores = validar_tei(ruta, entidades_esperadas=161)
    assert any("no contiene ninguna" in e for e in errores)
    assert validar_tei(ruta) == []        # sin expectativa, sigue siendo válido


def test_dos_articulos_con_el_mismo_titulo_conservan_sus_entidades():
    from core.servicios_exportacion import articulos_para_tei
    arts = [{"numero": "n1", "titulo": "Moda", "texto": "uno"},
            {"numero": "n1", "titulo": "Moda", "texto": "dos"}]
    from core.article_segmenter import asignar_ids_articulos
    asignar_ids_articulos(arts)
    indice = {"personas": {"Coco Chanel": [arts[0]["id"]],
                           "Elsa Schiaparelli": [arts[1]["id"]]}}
    tei = articulos_para_tei(ner_global=indice, articulos=arts)
    assert tei[0]["ner"] == {"personas": ["Coco Chanel"]}
    assert tei[1]["ner"] == {"personas": ["Elsa Schiaparelli"]}


def test_exportar_tei_articulos_ya_no_descarta_las_entidades(tmp_path):
    from core.servicios_exportacion import exportar_tei_articulos
    from core.tei_engine import contar_entidades_en_tei
    arts = [{"id": "n1-a0001", "titulo": "T", "texto": "Texto."}]
    ruta = tmp_path / "cli.xml"
    exportar_tei_articulos(arts, ruta, "Estampa", "1939",
                           ner_global={"lugares": {"Bogotá": ["n1-a0001"]}})
    assert contar_entidades_en_tei(ruta) == 1


def test_titulos_repetidos_en_proyecto_antiguo_se_informan():
    from core.estado import Estado
    from core.project_manager import migrar_ids_articulos
    st = Estado()
    st.df_articulos = pd.DataFrame([{"numero": "n1", "titulo": "Moda"},
                                    {"numero": "n1", "titulo": "Moda"}])
    st.indice_ner_global = {"personas": {"Coco Chanel": ["Moda"]}}
    res = migrar_ids_articulos(st)
    assert res["titulos_ambiguos"] == 1
    assert st.indice_ner_global["personas"]["Coco Chanel"] == ["n1-a0001", "n1-a0002"]


# ── Segmentador por defecto igual en todas las interfaces ─────────────────────

def test_el_escritorio_segmenta_con_v1_por_defecto():
    # Con v2 por defecto el escritorio daba 599 unidades para Estampa ene–may
    # 1939 y la CLI/API/web (v1) 639, la cifra publicada. Se comprueba en el
    # código fuente para no abrir otra raíz de Tk en la suite.
    import re
    fuente = (Path(__file__).parents[1] / "paneles" / "analisis.py").read_text(encoding="utf-8")
    m = re.search(r"_var_seg_v2 = tk\.BooleanVar\(value=(\w+)\)", fuente)
    assert m and m.group(1) == "False"
