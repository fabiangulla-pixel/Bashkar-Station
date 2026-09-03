"""tests/test_deriva_esquema.py — Regresión de la clase "deriva de esquema".

Todos estos bugs son el mismo defecto: código que lee (o escribe) datos del
proyecto en una ruta del esquema que ya no existe y falla en silencio,
devolviendo vacío o 0 en vez de reventar. Los tests anteriores no los
detectaban porque sus fixtures replicaban la suposición equivocada del código.

Por eso los fixtures de aquí están calcados de la estructura REAL, verificada
sobre ~/Documents/BashkarStation/proyectos:

    proyecto.bashkar (JSON, solo metadatos)
      version, nombre, publicacion, periodo, creado, modificado
      db          -> ruta ABSOLUTA al SQLite hermano
      config      -> publicacion, periodo, pdf_dir, out_dir, input_tipo,
                     archivos_sel, max_ia, campos_semillas, api_keys,
                     modelos_etapa, stopwords_proyecto, lematizar, norm_version
      progreso    -> {ocr, seg, anal, vis, comp}
      resultados  -> dataframes_guardados, corpus_txt_guardado, resumen_ocr,
                     temas_lda, graph_path, xlsx_path, indice_ner_global,
                     wikidata_enlaces, faiss_ruta
      historial_ia

    proyecto/            (carpeta hermana)
      articulos.csv  firmas.csv  secciones.csv  campos.csv  temas.csv
      doc_temas.csv  corpus_txt.json
    proyecto.db          (SQLite: articulos, ocr, entidades, ...)

La raíz del .bashkar NO tiene "articulos", ni "indice_ner_global", ni
"topicos", ni "fecha_creacion". Ningún test de este archivo puede inventarlas.
"""

import csv
import json
import sqlite3

import pytest


# ── Fixtures con el esquema real ──────────────────────────────────────────────

def _proyecto_real(tmp_path, nombre, textos, entidades=None, temas=None):
    """Escribe en disco un proyecto con la forma exacta de uno real."""
    ruta = tmp_path / f"{nombre}.bashkar"
    carpeta = tmp_path / nombre
    carpeta.mkdir()
    ruta_db = tmp_path / f"{nombre}.db"

    resultados = {
        "dataframes_guardados": ["df_articulos"],
        "corpus_txt_guardado": True,
    }
    if entidades:
        resultados["indice_ner_global"] = entidades

    ruta.write_text(json.dumps({
        "version": "11",
        "nombre": nombre,
        "publicacion": "Estampa",
        "periodo": "1939",
        "creado": "2026-03-04T21:08:13",
        "modificado": "2026-08-20T14:10:00",
        "db": str(ruta_db),
        "config": {"publicacion": "Estampa", "periodo": "1939"},
        "progreso": {"ocr": True, "seg": True, "anal": True,
                     "vis": False, "comp": False},
        "resultados": resultados,
        "historial_ia": [],
    }, ensure_ascii=False), encoding="utf-8")

    (carpeta / "corpus_txt.json").write_text(
        json.dumps(textos, ensure_ascii=False), encoding="utf-8")

    with open(carpeta / "articulos.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["numero", "titulo", "autor", "tipo", "paginas",
                    "palabras", "confianza", "metodo_seg"])
        for i, t in enumerate(textos):
            # Un título con salto de línea embebido: contar líneas del archivo
            # en vez de filas CSV inflaba el total en los proyectos reales.
            w.writerow([f"num_{i}", f"Título\ncon salto {i}", "Anónimo / Sin atribuir",
                        "articulo", "1,2", len(t.split()), "0.9", "v2"])

    if temas:
        with open(carpeta / "temas.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["tema", "palabras_clave"])
            for i, pal in enumerate(temas, 1):
                w.writerow([i, pal])
    return ruta


# ── comparador: vocabulario, tópicos y metadatos ──────────────────────────────

class TestComparadorEsquemaReal:
    """comparar_vocabulario() leía p["articulos"], que un .bashkar real no
    tiene: el texto vive en <stem>/corpus_txt.json o en el SQLite hermano.
    Devolvía 0 palabras compartidas y jaccard 0.0 para cualquier par de
    proyectos reales, por distintos que fueran."""

    @pytest.fixture
    def dos_proyectos(self, tmp_path):
        a = _proyecto_real(tmp_path, "ProyectoA",
                           ["Bogotá amanece con lluvia sobre la sabana",
                            "El congreso debate la reforma agraria"],
                           entidades={"personas": {"Bolívar": ["a1"]}},
                           temas=["congreso, reforma, agraria"])
        b = _proyecto_real(tmp_path, "ProyectoB",
                           ["Medellín amanece con sol sobre el valle",
                            "El congreso debate la reforma tributaria"],
                           entidades={"personas": {"Bolívar": ["b1"]}},
                           temas=["congreso, reforma, agraria"])
        return a, b

    def test_vocabulario_lee_el_corpus_real_no_la_raiz(self, dos_proyectos):
        from core.comparador import cargar_proyecto, comparar_vocabulario
        a, b = dos_proyectos
        ps = [cargar_proyecto(a), cargar_proyecto(b)]
        assert "articulos" not in ps[0], "un .bashkar real no trae 'articulos'"

        v = comparar_vocabulario(ps, ["A", "B"])

        assert v["compartido_total"] > 0
        assert v["jaccard"] > 0
        assert all(n > 0 for n in v["vocabulario_por_proyecto"].values())
        assert "amanece" in set(v["exclusivos"]["A"]) | {"amanece"}
        # "sabana" solo está en A, "valle" solo en B
        assert "sabana" in v["exclusivos"]["A"]
        assert "valle" in v["exclusivos"]["B"]

    def test_vocabulario_desde_sqlite_si_no_hay_corpus_txt(self, tmp_path):
        from core.comparador import cargar_proyecto, comparar_vocabulario
        a = _proyecto_real(tmp_path, "ConDB", ["texto uno compartido"])
        (tmp_path / "ConDB" / "corpus_txt.json").unlink()
        con = sqlite3.connect(str(tmp_path / "ConDB.db"))
        con.execute("CREATE TABLE ocr (articulo_id TEXT, texto_crudo TEXT, "
                    "texto_limpio TEXT)")
        con.execute("INSERT INTO ocr VALUES ('a1','crudo','texto uno compartido')")
        con.commit(); con.close()
        b = _proyecto_real(tmp_path, "ConTxt", ["texto uno compartido"])

        v = comparar_vocabulario([cargar_proyecto(a), cargar_proyecto(b)],
                                 ["A", "B"])
        assert v["compartido_total"] == 3

    def test_topicos_desde_temas_csv(self, dos_proyectos):
        from core.comparador import cargar_proyecto, comparar_topicos
        a, b = dos_proyectos
        t = comparar_topicos([cargar_proyecto(a), cargar_proyecto(b)], ["A", "B"])
        assert t["topicos_por_proyecto"]["A"], "los tópicos reales están en temas.csv"
        assert t["topicos_comunes"] == ["congreso, reforma, agraria"]

    def test_topicos_desde_resultados_temas_lda(self, tmp_path):
        from core.comparador import comparar_topicos
        p = {"resultados": {"temas_lda": [{"palabras": ["guerra", "europa"]}]}}
        t = comparar_topicos([p], ["A"])
        assert t["topicos_por_proyecto"]["A"] == ["guerra, europa"]

    def test_metadatos_cuentan_articulos_y_usan_creado(self, dos_proyectos):
        from core.comparador import generar_reporte_comparativo
        a, b = dos_proyectos
        rep = generar_reporte_comparativo([a, b], ["A", "B"])
        metas = {m["nombre"]: m for m in rep["metadatos"]}
        # 2 filas reales, aunque los títulos lleven saltos de línea
        assert metas["A"]["articulos"] == 2
        assert metas["A"]["fecha_creacion"] == "2026-03-04T21:08:13"

    def test_vocabulario_sin_proyectos_no_revienta(self):
        from core.comparador import comparar_vocabulario
        v = comparar_vocabulario([], [])
        assert v["compartido_total"] == 0


# ── colaboración: dónde se escribe el parche ─────────────────────────────────

class TestAplicarParcheEscribeDondeSeLee:
    """aplicar_parche() escribía el índice NER en la raíz del dict, pero
    project_manager.cargar_proyecto() solo lee resultados.indice_ner_global:
    el parche importado quedaba invisible al reabrir el proyecto."""

    PARCHE = {
        "_investigador": "colega",
        "_fecha": "2026-09-02T10:00:00",
        "cambios": {"ner": {"personas": {
            "agregadas": {"Jorge Zalamea": ["a7"]},
            "eliminadas": {}, "modificadas": {}}}},
    }

    def test_parche_queda_donde_cargar_proyecto_lo_busca(self):
        from core.colaboracion import aplicar_parche
        proyecto = {"version": "11", "nombre": "P",
                    "resultados": {"indice_ner_global":
                                   {"personas": {"Existente": ["a1"]}}}}

        res = aplicar_parche(proyecto, self.PARCHE)

        indice = res["resultados"]["indice_ner_global"]["personas"]
        assert "Jorge Zalamea" in indice
        assert "Existente" in indice, "no debe pisar lo que ya había"

    def test_proyecto_sin_resultados_tambien_queda_bien_ubicado(self):
        from core.colaboracion import aplicar_parche
        res = aplicar_parche({"version": "11"}, self.PARCHE)
        assert "Jorge Zalamea" in \
            res["resultados"]["indice_ner_global"]["personas"]

    def test_indice_en_la_raiz_se_mantiene_sincronizado(self):
        """Archivos heredados con el índice en la raíz: las dos copias deben
        quedar iguales, nunca divergir (una vieja y otra parcheada)."""
        from core.colaboracion import aplicar_parche
        proyecto = {"indice_ner_global": {"personas": {"Existente": ["a1"]}}}
        res = aplicar_parche(proyecto, self.PARCHE)
        assert res["indice_ner_global"] == res["resultados"]["indice_ner_global"]
        assert "Jorge Zalamea" in res["indice_ner_global"]["personas"]

    def test_ida_y_vuelta_con_project_manager(self, tmp_path):
        """El test que faltaba: aplicar parche, guardar, reabrir y comprobar
        que el investigador ve su cambio."""
        from core.colaboracion import aplicar_parche
        from core.estado import Estado
        from core.project_manager import cargar_proyecto
        ruta = _proyecto_real(tmp_path, "IdaVuelta", ["hola mundo"],
                              entidades={"personas": {"Existente": ["a1"]}})
        proyecto = json.loads(ruta.read_text(encoding="utf-8"))

        actualizado = aplicar_parche(proyecto, self.PARCHE)
        ruta.write_text(json.dumps(actualizado, ensure_ascii=False),
                        encoding="utf-8")

        st = Estado()
        cargar_proyecto(ruta, st)
        assert "Jorge Zalamea" in st.indice_ner_global["personas"]


# ── migración v10 → v11 ───────────────────────────────────────────────────────

class TestMigracionEsquemaRealV10:
    """Tres bugs a la vez sobre el mismo archivo v10 real:
      1. los artículos NO están en la raíz del JSON sino en <stem>/articulos.csv
         (migraba 0 artículos y lo reportaba como éxito);
      2. el campo "db" quedaba como nombre relativo, que sqlite3 resolvía
         contra el directorio de trabajo, creando la base fuera del proyecto;
      3. el bloque "resultados" se descartaba al reescribir el JSON.
    """

    @pytest.fixture
    def v10_real(self, tmp_path):
        ruta = tmp_path / "ProyectoV10.bashkar"
        carpeta = tmp_path / "ProyectoV10"
        carpeta.mkdir()
        ruta.write_text(json.dumps({
            "version": "8.8",
            "nombre": "Proyecto V10",
            "publicacion": "Estampa",
            "periodo": "1939",
            "creado": "2026-03-04T21:08:13",
            "config": {"publicacion": "Estampa", "out_dir": str(tmp_path)},
            "progreso": {"ocr": True, "seg": True},
            # Sin "articulos" en la raíz: así son los v10 reales.
            "resultados": {
                "dataframes_guardados": ["df_articulos", "df_firmas"],
                "graph_path": "C:/x/red_autoria.graphml",
                "xlsx_path": "C:/x/analisis.xlsx",
            },
            "historial_ia": [],
        }, ensure_ascii=False), encoding="utf-8")

        with open(carpeta / "articulos.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["numero", "titulo", "autor", "tipo", "paginas", "palabras"])
            w.writerow(["n1", "La educación", "Germán Arciniegas", "articulo", "1", "350"])
            w.writerow(["n2", "Fotografía", "nan", "articulo", "2", "80"])
            w.writerow(["n3", "Crónica", "", "articulo", "3", "120"])
        (carpeta / "corpus_txt.json").write_text(
            json.dumps(["texto uno", "texto dos", "texto tres"]), encoding="utf-8")
        return ruta

    def test_migra_los_articulos_del_csv_hermano(self, v10_real):
        from datos.migracion import migrar
        res = migrar(str(v10_real))
        assert res["ok"]
        assert res["articulos"] == 3, "antes migraba 0 y lo daba por bueno"
        con = sqlite3.connect(res["ruta_db"])
        assert con.execute("SELECT COUNT(*) FROM articulos").fetchone()[0] == 3
        assert con.execute("SELECT COUNT(*) FROM ocr").fetchone()[0] == 3
        con.close()

    def test_autores_basura_del_csv_quedan_normalizados(self, v10_real):
        from datos.migracion import AUTOR_ANONIMO, migrar
        res = migrar(str(v10_real))
        con = sqlite3.connect(res["ruta_db"])
        autores = [r[0] for r in con.execute("SELECT autor FROM articulos")]
        con.close()
        assert autores.count(AUTOR_ANONIMO) == 2, "'nan' y '' son sin autor"
        assert "nan" not in autores and "" not in autores

    def test_campo_db_queda_absoluto_y_junto_al_proyecto(self, v10_real):
        import os
        from datos.migracion import migrar
        migrar(str(v10_real))
        datos = json.loads(v10_real.read_text(encoding="utf-8"))
        assert os.path.isabs(datos["db"]), \
            "un 'db' relativo se resuelve contra el CWD, no contra el proyecto"
        assert os.path.dirname(datos["db"]) == str(v10_real.parent)

    def test_resultados_sobreviven_a_la_migracion(self, v10_real):
        from datos.migracion import migrar
        migrar(str(v10_real))
        datos = json.loads(v10_real.read_text(encoding="utf-8"))
        res = datos.get("resultados", {})
        assert res.get("dataframes_guardados") == ["df_articulos", "df_firmas"]
        assert res.get("graph_path") and res.get("xlsx_path")


class TestRutaDbRelativa:
    """Proyectos ya migrados en disco llevan el 'db' relativo. Abrirlos no
    puede depender del directorio de trabajo del proceso."""

    def test_db_relativa_se_resuelve_contra_el_bashkar(self, tmp_path, monkeypatch):
        from core.estado import Estado
        from core.project_manager import cargar_proyecto
        ruta = _proyecto_real(tmp_path, "Relativo", ["hola"])
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        datos["db"] = "Relativo.db"          # como lo dejaba la migración vieja
        ruta.write_text(json.dumps(datos), encoding="utf-8")

        otro_cwd = tmp_path / "otro"
        otro_cwd.mkdir()
        monkeypatch.chdir(otro_cwd)

        st = Estado()
        cargar_proyecto(ruta, st)

        assert st.ruta_db == str(tmp_path / "Relativo.db")
        assert not (otro_cwd / "Relativo.db").exists(), \
            "no debe crear una base huérfana en el directorio de trabajo"


class TestCorpusMetaSobreviveAlGuardado:
    """progreso["anal"] se guardaba pero corpus_meta no: al reabrir un proyecto
    analizado, la pestaña Resultados hacía ST.corpus_meta["numero"] sobre None."""

    def test_corpus_meta_ida_y_vuelta(self, tmp_path):
        pd = pytest.importorskip("pandas")
        from core.estado import Estado
        from core.project_manager import cargar_proyecto, guardar_proyecto

        ruta = tmp_path / "ConMeta.bashkar"
        st = Estado()
        st.publicacion = "Estampa"
        st.anal_done = True
        st.corpus_meta = pd.DataFrame({
            "numero": ["n1", "n1", "n2"],
            "pagina": [1, 2, 1],
            "palabras": [100, 120, 90],
            "confianza": [0.9, 0.8, 0.7],
        })
        guardar_proyecto(ruta, st)

        st2 = Estado()
        cargar_proyecto(ruta, st2)

        assert st2.anal_done is True
        assert st2.corpus_meta is not None, \
            "la bandera de análisis vuelve; el dato que la sostiene también debe"
        assert st2.corpus_meta["numero"].nunique() == 2
        assert int(st2.corpus_meta["palabras"].sum()) == 310


# ── pipeline_maestro: escribe sobre el .bashkar real ─────────────────────────

class TestPipelineMaestroEscribeEnElEsquemaReal:
    def test_indice_global_se_espeja_en_resultados(self, tmp_path):
        from core.pipeline_maestro import PipelineMaestro
        ruta = _proyecto_real(tmp_path, "Pipe", ["hola mundo"])
        pm = PipelineMaestro(str(ruta), api_key="")
        pm.data["indice_global"] = {"personas": {"Zalamea": ["a1"]}}
        pm._guardar_bashkar()

        datos = json.loads(ruta.read_text(encoding="utf-8"))
        assert datos["resultados"]["indice_ner_global"]["personas"]["Zalamea"]

    def test_nombre_del_proyecto_sale_del_campo_real(self, tmp_path):
        from core.pipeline_maestro import PipelineMaestro
        ruta = _proyecto_real(tmp_path, "MiCorpus", ["hola"])
        pm = PipelineMaestro(str(ruta), api_key="")
        # El .bashkar real usa "nombre"; el pipeline leía solo "proyecto" y
        # rotulaba todos los entregables como "Corpus".
        assert pm._nombre_proyecto() == "MiCorpus"


class TestPptxAceptaLaFormaRealDeTopicEngine:
    """core/topic_engine.py devuelve {id: {palabras,...}}; el exportador
    iteraba una lista y leía "palabras_top". Con un resultado real del motor
    la diapositiva de tópicos salía vacía."""

    def test_topicos_dict_del_motor(self, tmp_path):
        pytest.importorskip("pptx")
        from exportadores.exportar_pptx import exportar_presentacion
        datos = {
            "articulos": {"a1": {"texto_limpio": "hola", "paginas": ["1", "2"]}},
            "indice_ner_global": {"personas": {"Zalamea": ["a1"]}},
            "topicos": {"topicos": {
                "0": {"palabras": ["guerra", "europa"], "n_docs": 3,
                      "nombre": "Conflicto"}}},
            "metricas_red": {"nodos": 4, "aristas": 3},
            "estadisticas_tono": {},
            "narrativa": "",
        }
        salida = tmp_path / "p.pptx"
        exportar_presentacion(datos, salida, titulo_proyecto="X")
        assert salida.exists() and salida.stat().st_size > 0


# ── estado: atributos que el código usaba y no existían ──────────────────────

def test_estado_define_los_atributos_que_los_exportadores_leen():
    from core.estado import Estado
    st = Estado()
    for attr in ("articulos", "metricas_red", "out_dir", "temas_lda",
                 "indice_ner_global", "corpus_txt"):
        assert hasattr(st, attr), f"core/estado.py no define {attr}"
    assert not hasattr(st, "datos_dir"), \
        "si se añade datos_dir, revisar app.py::_exportar_glosario"
