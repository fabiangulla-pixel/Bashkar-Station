"""tests/test_ner_engine.py — Tests del pipeline NER."""
import pytest


class TestOfflineForzadoAntesDeImportarTransformers:
    """Sesión 63: causa real del segfault documentado en TestGuiNerEvitaSegfault.

    core/ner_roberta_local.py necesita fijar HF_HUB_OFFLINE=1 ANTES de que
    huggingface_hub se importe por primera vez en el proceso — esa librería
    lee la variable como constante de módulo una sola vez, y fijarla después
    (como hacía el código viejo, que primero hacía `from transformers import
    pipeline` y solo entonces forzaba offline) no tiene efecto. Estos tests
    protegen ese orden, que es invisible en una revisión superficial del
    diff porque el código "se ve" correcto línea por línea."""

    def test_ruta_cache_hf_seria_la_misma_que_calcularia_huggingface_hub(self, tmp_path, monkeypatch):
        from core.ner_roberta_local import _ruta_cache_hf
        monkeypatch.delenv("HUGGINGFACE_HUB_CACHE", raising=False)
        monkeypatch.setenv("HF_HOME", str(tmp_path))
        ruta = _ruta_cache_hf("org/modelo-de-prueba")
        assert ruta == tmp_path / "hub" / "models--org--modelo-de-prueba"

    def test_huggingface_hub_cache_tiene_prioridad_sobre_hf_home(self, tmp_path, monkeypatch):
        from core.ner_roberta_local import _ruta_cache_hf
        monkeypatch.setenv("HF_HOME", str(tmp_path / "no-deberia-usarse"))
        monkeypatch.setenv("HUGGINGFACE_HUB_CACHE", str(tmp_path / "cache-explicita"))
        ruta = _ruta_cache_hf("org/modelo-de-prueba")
        assert ruta == tmp_path / "cache-explicita" / "models--org--modelo-de-prueba"

    def test_forzar_offline_no_importa_huggingface_hub(self, tmp_path, monkeypatch):
        """El chequeo de caché debe ser puramente de sistema de archivos —
        importar huggingface_hub aquí es justo el bug que se está evitando."""
        import sys

        from core.ner_roberta_local import _forzar_offline_si_ya_cacheado
        monkeypatch.setenv("HUGGINGFACE_HUB_CACHE", str(tmp_path))
        monkeypatch.setitem(sys.modules, "huggingface_hub", None)  # ImportError si algo lo intenta
        monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
        _forzar_offline_si_ya_cacheado("org/no-cacheado")  # no debe lanzar ImportError
        assert "HF_HUB_OFFLINE" not in __import__("os").environ

    def test_forzar_offline_activa_la_variable_si_esta_cacheado(self, tmp_path, monkeypatch):
        from core.ner_roberta_local import _forzar_offline_si_ya_cacheado
        modelo = "org/modelo-cacheado"
        snapshot = tmp_path / "models--org--modelo-cacheado" / "snapshots" / "abc123"
        snapshot.mkdir(parents=True)
        (snapshot / "config.json").write_text("{}", encoding="utf-8")
        monkeypatch.setenv("HUGGINGFACE_HUB_CACHE", str(tmp_path))
        monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
        _forzar_offline_si_ya_cacheado(modelo)
        assert __import__("os").environ["HF_HUB_OFFLINE"] == "1"

    def test_importar_el_modulo_deja_offline_congelado_a_true(self):
        """Reproducción a nivel de proceso del bug real: si HF_HUB_OFFLINE no
        queda en firme ANTES de que algo importe huggingface_hub, `pipeline()`
        sale a red aunque el modelo esté cacheado — y esa llamada de red fue
        la que reventaba con access violation en Windows (sesión 63,
        confirmado con faulthandler sobre el corpus real de Estampa).
        Se salta si el modelo real no está descargado en esta máquina: no
        tiene sentido forzar una descarga desde un test."""
        import subprocess
        import sys
        from pathlib import Path

        pytest.importorskip("huggingface_hub")
        from huggingface_hub import try_to_load_from_cache

        from core.ner_roberta_local import _MODELO_NER
        if not isinstance(try_to_load_from_cache(_MODELO_NER, "config.json"), str):
            pytest.skip(f"{_MODELO_NER} no está cacheado en esta máquina")

        raiz = Path(__file__).resolve().parent.parent
        codigo = (
            "import core.ner_roberta_local\n"
            "import huggingface_hub.constants as c\n"
            "print('OFFLINE=' + str(c.HF_HUB_OFFLINE))\n"
        )
        r = subprocess.run(
            [sys.executable, "-c", codigo],
            capture_output=True, text=True, cwd=raiz, timeout=60,
        )
        assert r.returncode == 0, f"stderr: {r.stderr}"
        assert "OFFLINE=True" in r.stdout, (
            f"HF_HUB_OFFLINE no quedó en True tras importar core.ner_roberta_local "
            f"— stdout: {r.stdout!r}"
        )


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

    def test_fragmentar_por_tokens_respeta_el_limite_del_modelo(self):
        """Sesión 63: la ventana deslizante se medía en PALABRAS (450),
        asumiendo ~1 subtoken por palabra. Con texto OCR histórico real
        (números, mayúsculas, ruido) el tokenizador WordPiece parte más de lo
        esperado (~1.4 subtokens/palabra medido sobre el corpus real de
        Estampa) — CADA fragmento de 450 "palabras" terminaba superando los
        512 subtokens del modelo, y pipeline() reventaba con RuntimeError,
        silenciado por el `except Exception: continue` de ner_roberta():
        171 de 171 fragmentos fallando sin aviso sobre un número completo
        real (89 páginas), 0 entidades donde debería haber habido cientos.
        _fragmentar_por_tokens() ahora mide en subtokens reales del propio
        tokenizador — este test usa un tokenizador falso donde CADA palabra
        produce 3 subtokens (simula texto denso) para probarlo sin necesitar
        el modelo real."""
        from core.ner_roberta_local import (
            _SOLAPE_TOKENS,
            _VENTANA_TOKENS,
            _fragmentar_por_tokens,
        )

        class _TokenizadorFalso:
            """3 'subtokens' por palabra, como el texto OCR denso real."""
            def __call__(self, texto, add_special_tokens=False):
                return {"input_ids": list(range(len(texto.split()) * 3))}

            def decode(self, ids, skip_special_tokens=True):
                return " ".join(f"w{i}" for i in range(len(ids) // 3))

        tok = _TokenizadorFalso()
        # 450 "palabras" (lo que antes era una ventana completa) → 1350
        # subtokens con este tokenizador denso: muy por encima de 512.
        texto = " ".join(f"palabra{i}" for i in range(450))
        fragmentos = _fragmentar_por_tokens(texto, tok)
        assert len(fragmentos) > 1, "un texto de 1350 subtokens debe partirse en más de un fragmento"
        for frag in fragmentos:
            n_subtokens = len(tok(frag)["input_ids"])
            assert n_subtokens <= _VENTANA_TOKENS, (
                f"un fragmento de _fragmentar_por_tokens tiene {n_subtokens} subtokens, "
                f"por encima del límite ({_VENTANA_TOKENS}) — exactamente el bug que "
                "hacía reventar pipeline() con RuntimeError"
            )
        assert _SOLAPE_TOKENS < _VENTANA_TOKENS

    def test_fragmentar_por_tokens_texto_corto_no_se_parte(self):
        from core.ner_roberta_local import _fragmentar_por_tokens

        class _TokenizadorFalso:
            def __call__(self, texto, add_special_tokens=False):
                return {"input_ids": list(range(5))}

        texto = "Un texto corto."
        assert _fragmentar_por_tokens(texto, _TokenizadorFalso()) == [texto]

    def test_ner_roberta_texto_denso_no_pierde_fragmentos(self):
        """Reproducción con el modelo real de la causa exacta del bug: texto
        con muchos números y mayúsculas sostenidas (denso en subtokens),
        suficiente para que la ventana vieja de 450 palabras superara los
        512 subtokens. No debe emitir RuntimeWarning (fragmentos perdidos)."""
        import warnings

        from core.ner_roberta_local import ner_roberta, roberta_disponible
        if not roberta_disponible():
            pytest.skip("RoBERTa no disponible")
        frase_densa = "1939, 1938, 1937: LA GUERRA, EL FRENTE, LA REPÚBLICA — 12,50 pesos. "
        texto = frase_densa * 60  # denso, similar al ruido OCR real
        with warnings.catch_warnings(record=True) as capturadas:
            warnings.simplefilter("always")
            entidades = ner_roberta(texto)
        avisos_de_fallo = [w for w in capturadas if issubclass(w.category, RuntimeWarning)
                           and "fragmentos fallaron" in str(w.message)]
        assert not avisos_de_fallo, f"fragmentos perdidos: {[str(w.message) for w in avisos_de_fallo]}"
        assert isinstance(entidades, list)

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
    """Regresión: app.py llama recursos.aplicar_limites_cpu() al arrancar
    (línea ~26) y sus dos sitios que invocan pipeline_ner
    (_worker_ner_articulo, _worker_ner_corpus) segfaulteaban al cargar
    RoBERTa — reproducido con el camino de llamada exacto de la GUI, sesión
    62 (28-ago-2026).

    Sesión 63: reproducido de nuevo end-to-end sobre el corpus real de
    Estampa (mrm8488/bert-spanish-cased-finetuned-ner + faulthandler) y
    diagnosticado la causa real: no era threading torch/tokenizers como creyó
    sesión 62. core/ner_roberta_local.py importaba `transformers` (que
    arrastra huggingface_hub) ANTES de forzar HF_HUB_OFFLINE=1;
    huggingface_hub congela esa variable como constante en su propio import,
    así que fijarla después no evitaba que `pipeline()` saliera a red aunque
    el modelo ya estuviera cacheado — esa llamada de red reventaba con access
    violation en Windows. Arreglado ahí (offline forzado a nivel de módulo,
    antes de cualquier import de transformers) y confirmado sin segfault
    sobre un número completo de 89 páginas reales. usar_roberta vuelve a ser
    el default salvo elección explícita de "spacy"/"fallback" en Motor NER.
    Verificación a nivel de fuente (no instancia Tk real) porque el segfault
    en sí no es capturable por pytest — lo que se puede probar es que el
    kwarg sigue respetando esa elección."""

    def test_ambos_sitios_de_gui_respetan_spacy_fallback_explicito(self):
        raiz = __import__("pathlib").Path(__file__).resolve().parent.parent
        app_src = (raiz / "app.py").read_text(encoding="utf-8")
        llamadas = [
            app_src[m.start():m.start() + 400]
            for m in __import__("re").finditer(r"pipeline_ner\(", app_src)
        ]
        assert len(llamadas) >= 2, "se esperaban al menos 2 llamadas a pipeline_ner en app.py"
        for bloque in llamadas:
            assert 'usar_roberta=(motor not in ("spacy", "fallback"))' in bloque, (
                "una llamada a pipeline_ner en app.py ya no respeta la elección "
                'explícita de "spacy"/"fallback" en Motor NER'
            )
