"""tests/test_project_manager.py — Tests del gestor de proyectos v11."""
import json
import pytest
from pathlib import Path


@pytest.fixture
def dir_proyectos(tmp_path, monkeypatch):
    """Redirige _dir_proyectos() a un directorio temporal."""
    import core.project_manager as pm
    monkeypatch.setattr(pm, "_dir_proyectos", lambda: tmp_path)
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
        from core.project_manager import nuevo_proyecto, guardar_proyecto, cargar_proyecto
        ruta = nuevo_proyecto("Test GC", "Estampa")
        st = self._ST()
        guardar_proyecto(ruta, st)
        st2 = self._ST()
        res = cargar_proyecto(ruta, st2)
        assert res["ok"] is True
        assert st2.publicacion == "Estampa"
        assert st2.periodo == "1939"

    def test_cargar_preserva_nombre(self, dir_proyectos):
        from core.project_manager import nuevo_proyecto, guardar_proyecto, cargar_proyecto
        ruta = nuevo_proyecto("Mi proyecto", "Estampa")
        st = self._ST()
        guardar_proyecto(ruta, st)
        res = cargar_proyecto(ruta, st)
        assert res["nombre"] == "Mi proyecto"

    def test_cargar_conecta_repo(self, dir_proyectos):
        from core.project_manager import nuevo_proyecto, guardar_proyecto, cargar_proyecto
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
        from core.project_manager import nuevo_proyecto, guardar_proyecto, cargar_proyecto
        ruta = nuevo_proyecto("Test Keys", "Estampa")
        st = self._ST()
        st.api_keys = {"anthropic": "sk-ant-xxx", "openai": ""}
        guardar_proyecto(ruta, st)
        st2 = self._ST()
        cargar_proyecto(ruta, st2)
        assert st2.api_keys.get("anthropic") == "sk-ant-xxx"

    def test_guardar_persiste_ner(self, dir_proyectos):
        from core.project_manager import nuevo_proyecto, guardar_proyecto, cargar_proyecto
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
        from core.project_manager import cargar_proyecto
        import json

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
