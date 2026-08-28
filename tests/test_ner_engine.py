"""tests/test_ner_engine.py — Tests del pipeline NER."""
import pytest


class TestNEREngine:
    def test_pipeline_retorna_categorias_correctas(self):
        from core.ner_engine import CATEGORIAS, pipeline_ner
        resultado = pipeline_ner("texto de prueba", nlp=None, usar_roberta=False)
        assert isinstance(resultado, dict)
        assert set(resultado.keys()) == set(CATEGORIAS)

    def test_pipeline_retorna_listas(self):
        from core.ner_engine import pipeline_ner
        resultado = pipeline_ner("texto de prueba", nlp=None, usar_roberta=False)
        for cat, items in resultado.items():
            assert isinstance(items, list), f"{cat} no es lista"

    def test_pipeline_texto_vacio(self):
        from core.ner_engine import pipeline_ner
        resultado = pipeline_ner("", nlp=None, usar_roberta=False)
        for cat, items in resultado.items():
            assert items == [], f"{cat} no está vacío para texto vacío"

    def test_pipeline_con_roberta(self):
        """Si RoBERTa está disponible, detecta entidades reales."""
        from core.ner_engine import pipeline_ner
        from core.ner_roberta_local import roberta_disponible
        if not roberta_disponible():
            pytest.skip("RoBERTa no disponible")
        texto = "German Arciniegas visito Bogota y Medellin en Colombia."
        resultado = pipeline_ner(texto, nlp=None, usar_roberta=True)
        # Con texto real debe encontrar al menos algo en personas o lugares
        total = sum(len(v) for v in resultado.values())
        assert total > 0, "RoBERTa no encontró entidades en texto con nombres propios"

    def test_indice_global_vacio(self):
        from core.ner_engine import CATEGORIAS, indice_global_vacio
        indice = indice_global_vacio()
        assert set(indice.keys()) == set(CATEGORIAS)
        for cat in CATEGORIAS:
            assert isinstance(indice[cat], dict)
            assert len(indice[cat]) == 0

    def test_actualizar_indice(self):
        from core.ner_engine import actualizar_indice_global, indice_global_vacio
        indice = indice_global_vacio()
        ner = {"personas": ["Arciniegas"], "lugares": ["Bogota"],
               "organizaciones": [], "fechas": [], "obras_publicaciones": [], "eventos_historicos": []}
        actualizar_indice_global(indice, "art_001", ner)
        assert "Arciniegas" in indice["personas"]
        assert "art_001" in indice["personas"]["Arciniegas"]

    def test_actualizar_sin_duplicados(self):
        from core.ner_engine import actualizar_indice_global, indice_global_vacio
        indice = indice_global_vacio()
        ner = {"personas": ["Arciniegas"], "lugares": [], "organizaciones": [],
               "fechas": [], "obras_publicaciones": [], "eventos_historicos": []}
        actualizar_indice_global(indice, "art_001", ner)
        actualizar_indice_global(indice, "art_001", ner)
        assert len(indice["personas"]["Arciniegas"]) == 1

    def test_actualizar_multiples_articulos(self):
        from core.ner_engine import actualizar_indice_global, indice_global_vacio
        indice = indice_global_vacio()
        ner1 = {"personas": ["Arciniegas"], "lugares": ["Bogota"],
                "organizaciones": [], "fechas": [], "obras_publicaciones": [], "eventos_historicos": []}
        ner2 = {"personas": ["Arciniegas", "Lopez"], "lugares": ["Medellin"],
                "organizaciones": [], "fechas": [], "obras_publicaciones": [], "eventos_historicos": []}
        actualizar_indice_global(indice, "art_001", ner1)
        actualizar_indice_global(indice, "art_002", ner2)
        assert len(indice["personas"]["Arciniegas"]) == 2
        assert "art_001" in indice["personas"]["Arciniegas"]
        assert "art_002" in indice["personas"]["Arciniegas"]

    def test_exportar_csv(self, tmp_path):
        import csv

        from core.ner_engine import (
            actualizar_indice_global,
            exportar_csv,
            indice_global_vacio,
        )
        indice = indice_global_vacio()
        ner = {"personas": ["Arciniegas", "Lopez"], "lugares": ["Bogota"],
               "organizaciones": [], "fechas": [], "obras_publicaciones": [], "eventos_historicos": []}
        actualizar_indice_global(indice, "art_001", ner)
        ruta_csv = tmp_path / "ner_export.csv"
        n = exportar_csv(indice, ruta_csv)
        assert n == 3
        assert ruta_csv.exists()
        with open(ruta_csv, encoding="utf-8-sig") as f:
            filas = list(csv.DictReader(f))
        assert len(filas) == 3


class TestNERRoberta:
    def test_roberta_disponible_retorna_bool(self):
        from core.ner_roberta_local import roberta_disponible
        assert isinstance(roberta_disponible(), bool)

    def test_mapa_categorias_completo(self):
        from core.ner_roberta_local import MAPA_CATEGORIAS
        assert MAPA_CATEGORIAS["PER"] == "personas"
        assert MAPA_CATEGORIAS["LOC"] == "lugares"
        assert MAPA_CATEGORIAS["ORG"] == "organizaciones"
        assert MAPA_CATEGORIAS["MISC"] == "otros"

    def test_ner_roberta_con_texto_real(self):
        from core.ner_roberta_local import ner_roberta, roberta_disponible
        if not roberta_disponible():
            pytest.skip("RoBERTa no disponible")
        texto = "German Arciniegas nacio en Bogota y trabajo para El Tiempo."
        entidades = ner_roberta(texto)
        assert isinstance(entidades, list)
        for ent in entidades:
            assert "texto" in ent
            assert "categoria" in ent
            assert "confianza" in ent
            assert "fuente" in ent
            assert ent["fuente"] == "roberta_bne"
            assert 0 <= ent["confianza"] <= 1

    def test_ner_roberta_texto_largo(self):
        """Ventana deslizante no lanza excepción en texto largo."""
        from core.ner_roberta_local import ner_roberta, roberta_disponible
        if not roberta_disponible():
            pytest.skip("RoBERTa no disponible")
        texto = "German Arciniegas escribio sobre Colombia. " * 100  # ~5000 palabras
        entidades = ner_roberta(texto)
        assert isinstance(entidades, list)
        # No debe haber duplicados (la deduplicación debe funcionar)
        textos_unicos = set(e["texto"] for e in entidades)
        assert len(textos_unicos) == len(entidades), "hay entidades duplicadas"

    def test_ner_roberta_a_indice_formato(self):
        from core.ner_engine import CATEGORIAS
        from core.ner_roberta_local import ner_roberta_a_indice, roberta_disponible
        if not roberta_disponible():
            pytest.skip("RoBERTa no disponible")
        resultado = ner_roberta_a_indice("texto corto sin entidades")
        assert set(resultado.keys()) == set(CATEGORIAS)
        for cat, items in resultado.items():
            assert isinstance(items, list)


class TestFiltroRuidoNER:
    """Regresión: al correr el pipeline completo sobre el corpus real de
    Estampa (792 páginas, 28-ago-2026), el índice NER real salió contaminado
    con dos tipos de ruido — ver sesión 62 de [[project_bashkar_station]]."""

    def test_limpia_marcador_columna_del_prompt_vision(self):
        """core/ocr_llm.py le pide al modelo de Vision marcar cambios de
        columna con "--- COLUMNA ---" literal. Sin filtrarlo, spaCy lo
        detectaba como organización (561 apariciones sobre el corpus real)."""
        from core.ner_engine import _limpiar
        texto = "Un articulo real.\n\n--- COLUMNA ---\n\nSigue el texto aqui."
        limpio = _limpiar(texto)
        assert "COLUMNA" not in limpio
        assert "articulo real" in limpio
        assert "Sigue el texto" in limpio

    def test_limpia_marcador_ilegible(self):
        from core.ner_engine import _limpiar
        texto = "Palabra [ilegible] siguiente."
        assert "ilegible" not in _limpiar(texto)

    def test_filtra_palabras_funcion_como_persona(self):
        """"Así"/"Sólo" al inicio de oración salían como falsos positivos
        de persona en spaCy (modelo pequeño, capitalización de oración)."""
        from core.ner_engine import _es_falso_positivo_persona
        assert _es_falso_positivo_persona("Así")
        assert _es_falso_positivo_persona("sólo")
        assert not _es_falso_positivo_persona("Alfonso López")
        assert not _es_falso_positivo_persona("Hitler")

    def test_extraer_spacy_no_incluye_falsos_positivos(self):
        import spacy

        from core.ner_engine import extraer_spacy
        try:
            nlp = spacy.load("es_core_news_sm")
        except OSError:
            pytest.skip("es_core_news_sm no instalado")
        texto = ("Así llegó Hitler a Berlin. Sólo quedaban rumores. "
                 "El presidente Alfonso Lopez viajo a Bogota.")
        indice = extraer_spacy(texto, nlp)
        personas = {p.lower() for p in indice["personas"]}
        assert "así" not in personas
        assert "sólo" not in personas


class TestGuiNerEvitaSegfault:
    """Regresión: app.py TAMBIÉN llama recursos.aplicar_limites_cpu() al
    arrancar (línea ~26, igual que cli.py) y sus dos sitios que invocan
    pipeline_ner (_worker_ner_articulo, _worker_ner_corpus) no pasaban
    usar_roberta=False — el botón "Analizar NER" de la app de escritorio
    (la forma PRINCIPAL en que se usa Bashkar Station) segfaulteaba
    reproduciblemente, no solo el CLI. Reproducido y confirmado con el mismo
    camino de llamada exacto de la GUI, sesión 62 (28-ago-2026). Verificación
    a nivel de fuente (no instancia Tk real) porque el segfault en sí no es
    capturable por pytest — lo que se puede probar es que el kwarg sigue ahí."""

    def test_ambos_sitios_de_gui_pasan_usar_roberta_false(self):
        raiz = __import__("pathlib").Path(__file__).resolve().parent.parent
        app_src = (raiz / "app.py").read_text(encoding="utf-8")
        llamadas = [
            app_src[m.start():m.start() + 400]
            for m in __import__("re").finditer(r"pipeline_ner\(", app_src)
        ]
        assert len(llamadas) >= 2, "se esperaban al menos 2 llamadas a pipeline_ner en app.py"
        for bloque in llamadas:
            assert "usar_roberta=False" in bloque, (
                "una llamada a pipeline_ner en app.py no fuerza usar_roberta=False "
                "— con aplicar_limites_cpu() activo esto segfaultea"
            )
