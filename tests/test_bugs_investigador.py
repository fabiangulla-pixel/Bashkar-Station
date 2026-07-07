"""
Tests de regresión de los bugs encontrados durante la sesión del investigador
(corrida completa del pipeline sobre el corpus real de Estampa).

Cada test fija un bug concreto para que no reaparezca:
  1. ocr_llm: respuestas-rechazo del LLM contaminaban el corpus
  2. sentiment_engine.analizar_intensidad: set[:3] no es subscriptable
  3. stylometry_engine.atribuir_autoria: matriz sparse en np.dot
  4. morfologia_historica: regex -ares producía falsos positivos masivos
  5. tei_engine: xml:id con espacios/dígitos → XML inválido
  6. excel_export: columnas opcionales None / confianza_autor ausente
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


# ── 1. ocr_llm: rechazo del LLM no debe sobrescribir el original ─────────────

class TestRechazoLLM:
    def test_es_respuesta_invalida_detecta_rechazo(self):
        from core.ocr_llm import _es_respuesta_invalida
        original = "Texto de prensa histórica con suficiente longitud. " * 20
        rechazo = ("No puedo corregir este texto porque el OCR ha producido "
                   "un resultado que no contiene palabras legibles.")
        assert _es_respuesta_invalida(rechazo, original) is True

    def test_es_respuesta_invalida_acepta_correccion(self):
        from core.ocr_llm import _es_respuesta_invalida
        original = "El presidonte do la republica visito la ciudod."
        corregido = "El presidente de la república visitó la ciudad."
        assert _es_respuesta_invalida(corregido, original) is False

    def test_correccion_demasiado_corta_es_invalida(self):
        from core.ocr_llm import _es_respuesta_invalida
        original = "palabra " * 300       # texto largo
        corregido = "ok"                  # respuesta drásticamente recortada
        assert _es_respuesta_invalida(corregido, original) is True

    def test_filtrar_vision_descarta_rechazo(self):
        from core.ocr_llm import _filtrar_vision
        assert _filtrar_vision("I cannot transcribe this image.") == ""
        assert _filtrar_vision("Lo siento, no puedo leer esto.") == ""
        ok = "BOGOTÁ — La ciudad amaneció en calma."
        assert _filtrar_vision(ok) == ok


# ── 2. analizar_intensidad: no debe lanzar por set[:3] ───────────────────────

class TestIntensidad:
    def test_cuantificadores_repetidos_no_lanzan(self):
        from core.sentiment_engine import analizar_intensidad
        # 'todo' y 'nada' repetidos generan un set > 3 elementos
        texto = ("Todo nada todo nada nunca siempre jamás absolutamente "
                 "totalmente completamente todo nada")
        r = analizar_intensidad(texto)
        assert r["score_intensidad"] > 0
        assert isinstance(r["marcadores"], list)

    def test_intensidad_texto_neutro(self):
        from core.sentiment_engine import analizar_intensidad
        r = analizar_intensidad("La reunión comenzó a las tres de la tarde.")
        assert r["score_intensidad"] == 0.0


# ── 3. atribuir_autoria: maneja matrices sparse de TF-IDF ────────────────────

class TestAtribucionAutoria:
    def test_atribucion_con_sparse(self):
        from core.stylometry_engine import atribuir_autoria
        firmados = {
            "Autor A": ["la casa estaba sobre la colina verde y tranquila",
                        "la colina verde tranquila albergaba la casa antigua"],
            "Autor B": ["el motor rugía con fuerza en la carretera veloz",
                        "la carretera veloz vibraba bajo el motor potente"],
        }
        anonimos = {"x1": "la casa antigua sobre la colina verde y tranquila"}
        res = atribuir_autoria(firmados, anonimos)
        assert "x1" in res
        assert res["x1"][0]["autor"] in ("Autor A", "Autor B")
        assert 0.0 <= res["x1"][0]["similitud"] <= 1.0


# ── 4. morfología: -ares no debe marcar 'lugares', 'hogares' ─────────────────

class TestMorfologiaFalsosPositivos:
    def test_lugares_hogares_no_son_futuro_subjuntivo(self):
        from core.morfologia_historica import analizar_densidad_historica
        texto = ("Visitó muchos lugares y hogares de millares de familias. "
                 "Los pesares y azares de los militares fueron ejemplares.")
        d = analizar_densidad_historica(texto)
        marc = d.get("marcadores_detectados", {})
        assert marc.get("futuro_subjuntivo", 0) == 0

    def test_futuro_subjuntivo_real_si_se_detecta(self):
        from core.morfologia_historica import analizar_densidad_historica
        texto = "Si alguien infringiere la norma, cuando llegare el día, será juzgado."
        d = analizar_densidad_historica(texto)
        assert d.get("marcadores_detectados", {}).get("futuro_subjuntivo", 0) >= 1

    def test_ejemplos_arcaismos_son_palabras_completas(self):
        from core.morfologia_historica import analizar_densidad_historica
        texto = "Era un hombre bellísimo y grandísimo, ilustrísimo señor."
        d = analizar_densidad_historica(texto)
        ejemplos = [e["token"] for e in d.get("ejemplos", [])]
        # los superlativos deben aparecer completos, no como sufijo "ísimo"
        assert any("ísim" in e and len(e) > 5 for e in ejemplos)


# ── 5. TEI: xml:id debe ser NCName válido ────────────────────────────────────

class TestTeiXmlId:
    def test_ncname_espacios(self):
        from core.tei_engine import _ncname
        assert " " not in _ncname("Sin titulo")

    def test_ncname_empieza_por_digito(self):
        from core.tei_engine import _ncname
        out = _ncname("123")
        assert out[0].isalpha() or out[0] == "_"

    def test_corpus_tei_valido(self, tmp_path):
        from core.tei_engine import exportar_corpus_tei, validar_tei
        arts = [
            {"id": "Sin titulo", "texto": "Un texto de prueba.",
             "titulo": "Sin título", "autor": "Anónimo",
             "fecha": "1939-03", "ner": {}},
            {"id": "247", "texto": "Otro texto.", "titulo": "T2",
             "autor": "X", "fecha": "1939", "ner": {}},
        ]
        p = exportar_corpus_tei(arts, tmp_path / "c.xml")
        assert validar_tei(p) == []


# ── 6. excel_export: datos opcionales None y columnas faltantes ──────────────

class TestExcelOpcionales:
    def test_generar_figuras_con_visual_none(self):
        import pandas as pd

        from core.excel_export import generar_figuras_completas
        datos = {
            "publicacion": "Estampa",
            "df_firmas": pd.DataFrame({"numero": ["n1"], "firma": ["A"]}),
            "df_secciones": pd.DataFrame(
                {"numero": ["n1"], "seccion": ["Editorial"], "menciones": [3]}),
            "df_campos": pd.DataFrame({"numero": ["n1"], "politica": [1.0]}),
            "df_temas": pd.DataFrame({"tema": [1], "palabras_clave": ["a, b"]}),
            "df_doc_temas": None,
            "df_articulos": pd.DataFrame(
                {"numero": ["n1"], "titulo": ["T"], "autor": ["A"],
                 "seccion": ["Editorial"], "palabras": [100]}),
            "datos_visual": None,          # antes: AttributeError
            "datos_comparativo": None,
        }
        figs = generar_figuras_completas(datos)
        assert isinstance(figs, dict)

    def test_excel_sin_confianza_autor(self, tmp_path):
        import pandas as pd

        from core.excel_export import (
            construir_excel_completo,
            generar_figuras_completas,
        )
        df_art = pd.DataFrame(
            {"numero": ["n1", "n1"], "titulo": ["A", "B"],
             "autor": ["X", "Y"], "seccion": ["Ed", "Cr"],
             "palabras": [100, 200]})       # sin columna confianza_autor
        datos = {
            "publicacion": "Estampa",
            "df_firmas": pd.DataFrame({"numero": ["n1"], "firma": ["X"]}),
            "df_secciones": pd.DataFrame(
                {"numero": ["n1"], "seccion": ["Ed"], "menciones": [2]}),
            "df_campos": pd.DataFrame({"numero": ["n1"], "politica": [1.0]}),
            "df_temas": pd.DataFrame({"tema": [1], "palabras_clave": ["a, b"]}),
            "df_doc_temas": None,
            "df_articulos": df_art,
            "datos_visual": None, "datos_comparativo": None,
        }
        figs = generar_figuras_completas(datos)
        out = construir_excel_completo(datos, figs, tmp_path / "x.xlsx")
        assert Path(out).exists()
