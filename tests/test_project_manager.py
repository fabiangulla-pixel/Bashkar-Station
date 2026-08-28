"""tests/test_project_manager.py — Tests del gestor de proyectos v11."""
import json
from pathlib import Path

import pytest


@pytest.fixture
def dir_proyectos(tmp_path, monkeypatch):
    """Redirige _dir_proyectos() a un directorio temporal.

    También redirige el almacén de credenciales: sin esto, los tests que
    guardan claves escribirían en el ~/.bashkar REAL del desarrollador.
    """
    import core.project_manager as pm
    from core import user_prefs
    monkeypatch.setattr(pm, "_dir_proyectos", lambda: tmp_path)
    monkeypatch.setattr(
        user_prefs, "CREDENCIALES_PATH", tmp_path / "home" / "credenciales.json"
    )
    return tmp_path


class TestNuevoProyecto:
    def test_crea_bashkar(self, dir_proyectos):
        from core.project_manager import nuevo_proyecto
        ruta = nuevo_proyecto("Test Estampa", "Estampa", "1939")
        assert ruta.exists()
        assert ruta.suffix == ".bashkar"

    def test_json_valido(self, dir_proyectos):
        from core.project_manager import nuevo_proyecto
        ruta = nuevo_proyecto("Test", "Pub")
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        assert datos["nombre"] == "Test"
        assert datos["publicacion"] == "Pub"
        assert datos["version"] == "11"

    def test_campo_db_presente(self, dir_proyectos):
        from core.project_manager import nuevo_proyecto
        ruta = nuevo_proyecto("Test DB", "Estampa")
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        assert "db" in datos

    def test_db_sqlite_creada(self, dir_proyectos):
        from core.project_manager import nuevo_proyecto
        ruta = nuevo_proyecto("Test DB2", "Estampa")
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        ruta_db = datos.get("db", "")
        if ruta_db:
            assert Path(ruta_db).exists()

    def test_no_sobreescribe_existente(self, dir_proyectos):
        from core.project_manager import nuevo_proyecto
        r1 = nuevo_proyecto("Mismo Nombre", "Estampa")
        r2 = nuevo_proyecto("Mismo Nombre", "Estampa")
        assert r1 != r2

    def test_progreso_inicial_falso(self, dir_proyectos):
        from core.project_manager import nuevo_proyecto
        ruta = nuevo_proyecto("Test Prog", "Pub")
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        for v in datos["progreso"].values():
            assert v is False


class TestGuardarCargar:
    class _ST:
        """Mock mínimo del estado ST para tests."""
        publicacion = "Estampa"
        periodo = "1939"
        pdf_dir = None
        out_dir = None
        input_tipo = "pdf"
        archivos_sel = []
        api_key = "sk-test"
        max_ia = 15
        campos_semillas = {}
        ocr_done = False
        seg_done = False
        anal_done = False
        vis_done = False
        comp_done = False
        resumen_ocr = None
        temas_lda = None
        graph_path = None
        xlsx_path = None
        df_articulos = None
        indice_ner_global = {}
        api_keys = {"anthropic": "sk-test"}
        modelos_etapa = {}
        repo = None
        ruta_db = ""
        wikidata_enlaces = {}

    def test_guardar_y_cargar_basico(self, dir_proyectos):
        from core.project_manager import (
            cargar_proyecto,
            guardar_proyecto,
            nuevo_proyecto,
        )
        ruta = nuevo_proyecto("Test GC", "Estampa")
        st = self._ST()
        guardar_proyecto(ruta, st)
        st2 = self._ST()
        res = cargar_proyecto(ruta, st2)
        assert res["ok"] is True
        assert st2.publicacion == "Estampa"
        assert st2.periodo == "1939"

    def test_cargar_preserva_nombre(self, dir_proyectos):
        from core.project_manager import (
            cargar_proyecto,
            guardar_proyecto,
            nuevo_proyecto,
        )
        ruta = nuevo_proyecto("Mi proyecto", "Estampa")
        st = self._ST()
        guardar_proyecto(ruta, st)
        res = cargar_proyecto(ruta, st)
        assert res["nombre"] == "Mi proyecto"

    def test_cargar_conecta_repo(self, dir_proyectos):
        from core.project_manager import (
            cargar_proyecto,
            guardar_proyecto,
            nuevo_proyecto,
        )
        ruta = nuevo_proyecto("Test Repo", "Estampa")
        st = self._ST()
        guardar_proyecto(ruta, st)
        res = cargar_proyecto(ruta, st)
        assert res["ok"] is True
        # repo debe estar conectado si datos/repositorio está disponible
        # (puede ser None si no está instalado, pero no debe lanzar excepción)

    def test_cargar_inexistente(self, dir_proyectos):
        from core.project_manager import cargar_proyecto
        res = cargar_proyecto(dir_proyectos / "no_existe.bashkar", self._ST())
        assert res["ok"] is False

    def test_guardar_persiste_api_keys(self, dir_proyectos):
        from core.project_manager import (
            cargar_proyecto,
            guardar_proyecto,
            nuevo_proyecto,
        )
        ruta = nuevo_proyecto("Test Keys", "Estampa")
        st = self._ST()
        st.api_keys = {"anthropic": "sk-ant-xxx", "openai": ""}
        guardar_proyecto(ruta, st)
        st2 = self._ST()
        st2.api_keys = {}
        cargar_proyecto(ruta, st2)
        assert st2.api_keys.get("anthropic") == "sk-ant-xxx"

    def test_el_proyecto_nunca_contiene_la_clave(self, dir_proyectos):
        """Regresión: un .bashkar se comparte y se sincroniza a la nube.

        Una API key escrita ahí es una filtración silenciosa. Esta prueba mira
        los BYTES del archivo, no la estructura: da igual bajo qué campo se
        cuele, no debe aparecer.
        """
        from core.project_manager import guardar_proyecto, nuevo_proyecto
        ruta = nuevo_proyecto("Test Fuga", "Estampa")
        st = self._ST()
        st.api_key = "sk-ant-SECRETO-LEGADO"
        st.api_keys = {
            "anthropic": "sk-ant-SECRETO",
            "openai": "sk-proj-SECRETO",
            "gemini": "AIzaSECRETO",
            "ollama": "http://localhost:11434",
        }
        guardar_proyecto(ruta, st)

        crudo = ruta.read_text(encoding="utf-8")
        assert "SECRETO" not in crudo
        # …y la URL local de Ollama sí se conserva: no es un secreto.
        assert "http://localhost:11434" in crudo

    def test_cargar_migra_y_limpia_claves_de_proyecto_viejo(self, dir_proyectos):
        """Un proyecto creado por la versión anterior trae claves dentro.

        Al abrirlo deben moverse al almacén del usuario y desaparecer del
        archivo, avisando para que el usuario las rote.
        """
        import json

        from core.project_manager import cargar_proyecto, nuevo_proyecto
        from core.user_prefs import cargar_credenciales

        ruta = nuevo_proyecto("Test Legado", "Estampa")
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        datos.setdefault("config", {})
        datos["config"]["api_keys"] = {
            "openai": "sk-proj-VIEJO",
            "ollama": "http://localhost:11434",
        }
        datos["config"]["api_key"] = "sk-proj-VIEJO"
        ruta.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")

        st = self._ST()
        st.api_keys = {}
        res = cargar_proyecto(ruta, st)

        assert res["credenciales_migradas"] is True
        assert "VIEJO" not in ruta.read_text(encoding="utf-8")
        assert cargar_credenciales().get("openai") == "sk-proj-VIEJO"
        assert st.api_keys.get("openai") == "sk-proj-VIEJO"
        assert "ROTA" in res["mensaje"]

    def test_guardar_persiste_ner(self, dir_proyectos):
        from core.project_manager import (
            cargar_proyecto,
            guardar_proyecto,
            nuevo_proyecto,
        )
        ruta = nuevo_proyecto("Test NER", "Estampa")
        st = self._ST()
        st.indice_ner_global = {
            "personas": {"Arciniegas": ["art_001"]},
            "lugares": {},
            "organizaciones": {},
            "fechas": {},
            "obras_publicaciones": {},
            "eventos_historicos": {},
        }
        guardar_proyecto(ruta, st)
        st2 = self._ST()
        cargar_proyecto(ruta, st2)
        assert "Arciniegas" in st2.indice_ner_global.get("personas", {})


class TestMigracionAutomatica:
    def test_v10_migra_al_cargar(self, dir_proyectos):
        import json

        from core.project_manager import cargar_proyecto

        # Crear un .bashkar v10 manualmente
        ruta = dir_proyectos / "viejo.bashkar"
        datos_v10 = {
            "version": "10",
            "nombre": "Estampa vieja",
            "publicacion": "Estampa",
            "periodo": "1939",
            "config": {"api_key": "sk-test"},
            "articulos": [
                {"id": "art_001", "titulo": "Prueba",
                 "ocr": {"texto_limpio": "Texto de prueba.", "confianza": 0.8, "motor": "tesseract"}}
            ],
            "progreso": {},
            "historial_ia": [],
        }
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(datos_v10, f)

        class _ST:
            publicacion = ""; periodo = ""; pdf_dir = None; out_dir = None
            input_tipo = "pdf"; archivos_sel = []; api_key = ""; max_ia = 15
            campos_semillas = {}; ocr_done = False; seg_done = False
            anal_done = False; vis_done = False; comp_done = False
            resumen_ocr = None; temas_lda = None; graph_path = None
            xlsx_path = None; df_articulos = None; indice_ner_global = {}
            api_keys = {}; modelos_etapa = {}; repo = None; ruta_db = ""
            wikidata_enlaces = {}

        res = cargar_proyecto(ruta, _ST())
        assert res["ok"] is True
        # Tras cargar, el archivo debe haber sido migrado (version == "11")
        with open(ruta, encoding="utf-8") as f:
            datos_post = json.load(f)
        assert datos_post.get("version") == "11"
        assert res.get("migrado") is True


class TestReconstruirCorpusTxtDesdeOcr:
    """Regresión: cargar_proyecto() reconstruía corpus_txt leyendo solo la
    ÚLTIMA página de cada número (bug real encontrado importando el corpus
    completo de Vision OCR, 792 páginas — solo 5 quedaban en corpus_txt,
    una por número). Debe leer TODAS las páginas de cada carpeta 03_ocr/<numero>/.
    """

    def test_reconstruye_todas_las_paginas_no_solo_la_ultima(self, dir_proyectos, tmp_path):
        from core.project_manager import cargar_proyecto, nuevo_proyecto

        ruta = nuevo_proyecto("Test Reconstruccion", "Estampa")
        datos_dir = tmp_path / "datos_proyecto"
        for numero, n_paginas in (("rev_ene_1939", 3), ("rev_feb_1939", 2)):
            num_dir = datos_dir / "03_ocr" / numero
            num_dir.mkdir(parents=True)
            for i in range(1, n_paginas + 1):
                (num_dir / f"p{i:04d}.txt").write_text(f"texto de {numero} pagina {i}",
                                                          encoding="utf-8")

        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        datos["config"]["out_dir"] = str(datos_dir)
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(datos, f)

        class _ST:
            publicacion = "Estampa"; periodo = "1939"; pdf_dir = None
            out_dir = None
            input_tipo = "pdf"; archivos_sel = []; api_key = ""; max_ia = 15
            campos_semillas = {}; ocr_done = False; seg_done = False
            anal_done = False; vis_done = False; comp_done = False
            resumen_ocr = None; temas_lda = None; graph_path = None
            xlsx_path = None; df_articulos = None; indice_ner_global = {}
            api_keys = {}; modelos_etapa = {}; repo = None; ruta_db = ""
            wikidata_enlaces = {}

        st = _ST()
        res = cargar_proyecto(ruta, st)
        assert res["ok"] is True
        # 3 páginas de rev_ene_1939 + 2 de rev_feb_1939 = 5 documentos,
        # no 2 (uno por número, el bug viejo)
        assert len(st.corpus_txt) == 5
        assert "pagina 1" in st.corpus_txt[0]
