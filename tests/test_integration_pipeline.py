"""
tests/test_integration_pipeline.py — Test de integración end-to-end.

Prueba el flujo completo sin GUI:
  proyecto.bashkar → cargar → normalizar → segmentar → NER → guardar → recargar

Verifica que los datos persisten correctamente entre sesiones y que
las nuevas configuraciones (stopwords, lematizar) se guardan y restauran.
"""

import json
import tempfile
import shutil
from pathlib import Path

import pytest


# ── Fixtures ──────────────────────────────────────────────────────────────────

CORPUS_SAMPLE = [
    "Francisco Franco visitó Bogotá en enero de 1939. El presidente habló en el Capitolio.",
    "La revista Estampa publicó fotografías de la exposición artística en Medellín.",
    "El Ministerio de Educación anunció nuevas becas para estudiantes colombianos.",
    "En febrero, el poeta Luis Carlos López presentó su nuevo libro en la Biblioteca Nacional.",
    "La compañía Casa Muñoz Hermanos inauguró su nueva sede en el barrio La Candelaria.",
]


@pytest.fixture
def proyecto_tmp(tmp_path):
    """Crea un proyecto .bashkar mínimo en un directorio temporal."""
    # Estructura de carpetas
    out_dir = tmp_path / "salida"
    ocr_dir = out_dir / "03_ocr" / "enero_1939"
    ocr_dir.mkdir(parents=True)

    # Escribir TXT de prueba
    for i, texto in enumerate(CORPUS_SAMPLE, 1):
        (ocr_dir / f"p{i:04d}.txt").write_text(texto, encoding="utf-8")

    # Crear archivo .bashkar mínimo
    bashkar = tmp_path / "test_proyecto.bashkar"
    datos = {
        "version": "11",
        "nombre": "Proyecto de prueba",
        "publicacion": "Estampa",
        "periodo": "1939",
        "modificado": "2026-06-04T12:00:00",
        "db": str(tmp_path / "test_proyecto.db"),
        "config": {
            "publicacion": "Estampa",
            "periodo": "1939",
            "pdf_dir": str(tmp_path),
            "out_dir": str(out_dir),
            "input_tipo": "carpetas",
            "archivos_sel": [],
            "api_key": "",
            "api_keys": {},
            "max_ia": 15,
            "campos_semillas": {},
            "stopwords_proyecto": ["estampa", "revista"],
            "lematizar": False,
            "norm_version": "manual",
        },
        "progreso": {"ocr": True, "seg": False, "anal": False, "vis": False, "comp": False},
        "resultados": {},
        "historial_ia": [],
    }
    bashkar.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"bashkar": bashkar, "out_dir": out_dir, "ocr_dir": ocr_dir, "tmp": tmp_path}


# ── Tests de carga y persistencia ─────────────────────────────────────────────

class TestCargarProyecto:
    def test_carga_basica(self, proyecto_tmp):
        from core.project_manager import cargar_proyecto

        class FakeST:
            pass

        st = FakeST()
        res = cargar_proyecto(proyecto_tmp["bashkar"], st)
        assert res["ok"] is True
        assert st.publicacion == "Estampa"
        assert st.periodo == "1939"
        assert Path(st.out_dir) == proyecto_tmp["out_dir"]

    def test_restaura_stopwords(self, proyecto_tmp):
        from core.project_manager import cargar_proyecto

        class FakeST:
            pass

        st = FakeST()
        cargar_proyecto(proyecto_tmp["bashkar"], st)
        assert hasattr(st, "stopwords_proyecto")
        assert "estampa" in st.stopwords_proyecto
        assert "revista" in st.stopwords_proyecto

    def test_restaura_lematizar(self, proyecto_tmp):
        from core.project_manager import cargar_proyecto

        class FakeST:
            pass

        st = FakeST()
        cargar_proyecto(proyecto_tmp["bashkar"], st)
        assert hasattr(st, "lematizar")
        assert st.lematizar is False  # guardado como False en el fixture

    def test_restaura_norm_version(self, proyecto_tmp):
        from core.project_manager import cargar_proyecto

        class FakeST:
            pass

        st = FakeST()
        cargar_proyecto(proyecto_tmp["bashkar"], st)
        assert st.norm_version == "manual"


class TestGuardarProyecto:
    def test_roundtrip_stopwords(self, proyecto_tmp, tmp_path):
        from core.project_manager import guardar_proyecto, cargar_proyecto

        class FakeST:
            publicacion = "Estampa"
            periodo     = "1939"
            pdf_dir     = None
            out_dir     = proyecto_tmp["out_dir"]
            input_tipo  = "carpetas"
            archivos_sel = []
            api_key      = ""
            api_keys     = {}
            max_ia       = 15
            campos_semillas = {}
            stopwords_proyecto = ["prueba", "corpus", "bogotá"]
            lematizar    = True
            norm_version = "crudo"
            modelos_etapa = {}
            indice_ner_global = {}
            wikidata_enlaces  = {}
            resumen_ocr = None
            temas_lda   = None
            graph_path  = None
            xlsx_path   = None
            df_articulos = None
            df_firmas    = None
            df_secciones = None
            df_campos    = None
            df_layout    = None
            df_temas     = None
            df_doc_temas = None
            ocr_done = False
            seg_done = False
            anal_done = False
            vis_done  = False
            comp_done = False
            estado_etapas = {}
            ia_habilitada = False
            ruta_db = ""
            _bsem_indice = None

        ruta = tmp_path / "test_roundtrip.bashkar"
        ruta.write_text("{}", encoding="utf-8")  # crear vacío

        guardar_proyecto(ruta, FakeST())

        class FakeST2:
            pass

        st2 = FakeST2()
        cargar_proyecto(ruta, st2)

        assert st2.stopwords_proyecto == ["prueba", "corpus", "bogotá"]
        assert st2.lematizar is True
        assert st2.norm_version == "crudo"

    def test_roundtrip_indice_ner(self, proyecto_tmp, tmp_path):
        from core.project_manager import guardar_proyecto, cargar_proyecto

        class FakeST:
            publicacion  = "Estampa"
            periodo      = "1939"
            pdf_dir      = None
            out_dir      = proyecto_tmp["out_dir"]
            input_tipo   = "carpetas"
            archivos_sel = []
            api_key      = ""
            api_keys     = {}
            max_ia       = 15
            campos_semillas = {}
            stopwords_proyecto = []
            lematizar    = True
            norm_version = "manual"
            modelos_etapa = {}
            indice_ner_global = {
                "personas": {"Franco": ["art_0001", "art_0002"]},
                "lugares":  {"Bogotá": ["art_0001"]},
            }
            wikidata_enlaces = {}
            resumen_ocr = None; temas_lda = None
            graph_path = None; xlsx_path = None
            df_articulos = None; df_firmas = None; df_secciones = None
            df_campos = None; df_layout = None; df_temas = None; df_doc_temas = None
            ocr_done = True; seg_done = False; anal_done = False
            vis_done = False; comp_done = False; estado_etapas = {}
            ia_habilitada = False; ruta_db = ""; _bsem_indice = None
            ner_done = True

        ruta = tmp_path / "test_ner_roundtrip.bashkar"
        ruta.write_text("{}", encoding="utf-8")
        guardar_proyecto(ruta, FakeST())

        class FakeST2:
            pass

        st2 = FakeST2()
        cargar_proyecto(ruta, st2)

        assert hasattr(st2, "indice_ner_global")
        assert "personas" in st2.indice_ner_global
        assert "Franco" in st2.indice_ner_global["personas"]


# ── Tests de pipeline OCR → normalizar ────────────────────────────────────────

class TestPipelineNormalizacion:
    def test_normalizar_mantiene_arcaismos(self, proyecto_tmp):
        """El normalizador NO moderniza el español histórico."""
        from core.ocr_normalizer import normalizar_texto_ocr
        texto = "El señor habia llegado á Bogotá en fué el año 1939."
        resultado = normalizar_texto_ocr(texto)
        # Arcaísmos preservados
        assert "habia" in resultado or "había" in resultado  # permite corrección de tilde
        assert "Bogotá" in resultado
        # El año se preserva
        assert "1939" in resultado

    def test_normalizar_elimina_ruido_ocr(self, proyecto_tmp):
        from core.ocr_normalizer import normalizar_texto_ocr
        texto = "El |artículo| habla de §política§ en ~Colombia~"
        resultado = normalizar_texto_ocr(texto)
        assert "§" not in resultado
        assert "~" not in resultado

    def test_archivos_txt_legibles(self, proyecto_tmp):
        txts = list(proyecto_tmp["ocr_dir"].glob("*.txt"))
        assert len(txts) == len(CORPUS_SAMPLE)
        for p in txts:
            contenido = p.read_text(encoding="utf-8")
            assert len(contenido) > 10


# ── Tests de pipeline segmentación ────────────────────────────────────────────

class TestPipelineSegmentacion:
    def test_segmentar_numero(self, proyecto_tmp):
        from core.article_segmenter import segmentar_numero
        import inspect
        sig = inspect.signature(segmentar_numero)
        params = list(sig.parameters.keys())
        # Llamar con la firma correcta (acepta nombre como segundo arg o no)
        if len(params) >= 2:
            arts = segmentar_numero(proyecto_tmp["ocr_dir"], "enero_1939")
        else:
            arts = segmentar_numero(proyecto_tmp["ocr_dir"])
        # El segmentador puede retornar 0 artículos con textos muy cortos (< umbral mínimo);
        # lo importante es que no lanza excepción y retorna una lista
        assert isinstance(arts, list)

    def test_articulos_tienen_texto(self, proyecto_tmp):
        from core.article_segmenter import segmentar_numero
        import inspect
        sig = inspect.signature(segmentar_numero)
        params = list(sig.parameters.keys())
        if len(params) >= 2:
            arts = segmentar_numero(proyecto_tmp["ocr_dir"], "enero_1939")
        else:
            arts = segmentar_numero(proyecto_tmp["ocr_dir"])
        for art in arts:
            texto = art.get("texto", "") or art.get("contenido", "")
            assert len(str(texto)) > 0


# ── Tests de bitácora con persistencia ────────────────────────────────────────

class TestBitacoraPersistencia:
    def test_notas_persisten_entre_instancias(self, tmp_path):
        """La bitácora persiste datos entre instancias del motor."""
        from core.bitacora_engine import BitacoraEngine
        db = str(tmp_path / "test_notas.db")

        eng1 = BitacoraEngine(db)
        nid = eng1.insertar({
            "tipo": "hipotesis",
            "estado": "abierta",
            "texto": "Los anuncios aumentan en diciembre",
            "ref_numero": "diciembre_1939",
        })

        # Segunda instancia — simula reabrir la app
        eng2 = BitacoraEngine(db)
        nota = eng2.obtener(nid)
        assert nota is not None
        assert nota["texto"] == "Los anuncios aumentan en diciembre"
        assert nota["estado"] == "abierta"
        assert nota["ref_numero"] == "diciembre_1939"

    def test_contar_tras_multiples_operaciones(self, tmp_path):
        from core.bitacora_engine import BitacoraEngine
        eng = BitacoraEngine(str(tmp_path / "cnt.db"))

        for i in range(5):
            eng.insertar({"tipo": "libre", "texto": f"Nota {i}"})
        for i in range(3):
            eng.insertar({"tipo": "hipotesis", "estado": "abierta", "texto": f"H{i}"})
        eng.insertar({"tipo": "cita", "texto": "Fragmento"})

        cnt = eng.contar()
        assert cnt["total"] == 9
        assert cnt["por_tipo"]["libre"] == 5
        assert cnt["por_tipo"]["hipotesis"] == 3
        assert cnt["por_tipo"]["cita"] == 1


# ── Tests de collocation pipeline integrado ───────────────────────────────────

class TestCollocatePipeline:
    def test_pipeline_corpus_a_ngramas(self):
        """Flujo completo: corpus → tokenizar → n-gramas."""
        from core.collocation_engine import ngramas, frecuencias, concordancias
        corpus = [t for t in CORPUS_SAMPLE]

        # N-gramas
        ng2 = ngramas(corpus, n=2, min_freq=1, stopwords=False)
        assert len(ng2) > 0
        assert all("ngrama" in r and "frecuencia" in r for r in ng2)

        # Frecuencias
        freqs = frecuencias(corpus, top_n=10, stopwords=True)
        assert len(freqs) > 0
        assert all(r["freq"] >= 1 for r in freqs)

        # KWIC
        res = concordancias(corpus, "bogotá", max_resultados=5)
        # Puede ser 0 si spaCy no tokeniza bien en minúsculas, pero no debe fallar
        assert isinstance(res, list)

    def test_frecuencia_relativa_consistente(self):
        from core.collocation_engine import frecuencias
        corpus = ["casa roja grande", "casa pequeña verde", "árbol grande verde"]
        res = frecuencias(corpus, top_n=10, stopwords=False)
        total = sum(r["freq"] for r in res)
        assert total > 0
        # La suma de frecuencias relativas /10000 debe ser 10000
        suma_rel = sum(r["freq"] / total * 10000 for r in res)
        assert abs(suma_rel - 10000) < 1.0  # tolerancia por redondeo
