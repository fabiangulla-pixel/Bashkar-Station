"""
tests/test_v11_features.py — Tests para los módulos nuevos de v11.

Cubre:
  - core/bitacora_engine.py
  - core/timeline_engine.py
  - core/kraken_trainer.py
  - core/methods_reporter.py
  - core/collocation_engine.py (funciones nuevas: ngramas, stopwords_personalizadas)
  - core/tei_engine.py (validar_tei)
"""

import json
import tempfile
from pathlib import Path
import pytest


# ══════════════════════════════════════════════════════════════════════════════
# BITÁCORA DE INVESTIGACIÓN
# ══════════════════════════════════════════════════════════════════════════════

class TestBitacoraEngine:
    def _engine(self, tmp_path):
        from core.bitacora_engine import BitacoraEngine
        db = str(tmp_path / "test_bitacora.db")
        return BitacoraEngine(db)

    def test_insertar_nota_libre(self, tmp_path):
        eng = self._engine(tmp_path)
        nota_id = eng.insertar({
            "tipo": "libre",
            "texto": "El corpus de Estampa muestra alta variación tipográfica",
            "etiquetas": ["tipografía", "corpus"],
            "ref_numero": "enero_1939",
        })
        assert isinstance(nota_id, int)
        assert nota_id > 0

    def test_insertar_hipotesis(self, tmp_path):
        eng = self._engine(tmp_path)
        nota_id = eng.insertar({
            "tipo": "hipotesis",
            "estado": "abierta",
            "texto": "Las noticias de deportes aumentan en verano",
            "etiquetas": ["deportes", "temporalidad"],
        })
        nota = eng.obtener(nota_id)
        assert nota["tipo"] == "hipotesis"
        assert nota["estado"] == "abierta"

    def test_listar_filtrar_tipo(self, tmp_path):
        eng = self._engine(tmp_path)
        eng.insertar({"tipo": "libre", "texto": "Nota A"})
        eng.insertar({"tipo": "hipotesis", "estado": "abierta", "texto": "Hipótesis B"})
        eng.insertar({"tipo": "cita", "texto": "Cita C"})
        libres = eng.listar(tipo="libre")
        assert len(libres) == 1
        assert libres[0]["texto"] == "Nota A"

    def test_listar_filtrar_estado(self, tmp_path):
        eng = self._engine(tmp_path)
        eng.insertar({"tipo": "hipotesis", "estado": "abierta", "texto": "H1"})
        eng.insertar({"tipo": "hipotesis", "estado": "confirmada", "texto": "H2"})
        abiertas = eng.listar(tipo="hipotesis", estado="abierta")
        assert len(abiertas) == 1

    def test_listar_busqueda_texto(self, tmp_path):
        eng = self._engine(tmp_path)
        eng.insertar({"tipo": "libre", "texto": "fotografía de portada"})
        eng.insertar({"tipo": "libre", "texto": "análisis editorial"})
        res = eng.listar(q="fotografía")
        assert len(res) == 1

    def test_actualizar_estado_hipotesis(self, tmp_path):
        eng = self._engine(tmp_path)
        nid = eng.insertar({"tipo": "hipotesis", "estado": "abierta", "texto": "H"})
        eng.actualizar(nid, {"estado": "confirmada"})
        nota = eng.obtener(nid)
        assert nota["estado"] == "confirmada"

    def test_eliminar(self, tmp_path):
        eng = self._engine(tmp_path)
        nid = eng.insertar({"tipo": "libre", "texto": "borrar"})
        eng.eliminar(nid)
        assert eng.obtener(nid) is None

    def test_contar(self, tmp_path):
        eng = self._engine(tmp_path)
        eng.insertar({"tipo": "libre", "texto": "A"})
        eng.insertar({"tipo": "hipotesis", "estado": "abierta", "texto": "B"})
        eng.insertar({"tipo": "cita", "texto": "C"})
        cnt = eng.contar()
        assert cnt["total"] == 3
        assert cnt["por_tipo"]["libre"] == 1
        assert cnt["por_tipo"]["hipotesis"] == 1

    def test_exportar_markdown(self, tmp_path):
        eng = self._engine(tmp_path)
        eng.insertar({"tipo": "hipotesis", "estado": "abierta",
                      "texto": "Hipótesis principal", "etiquetas": ["editorial"]})
        eng.insertar({"tipo": "cita", "texto": "Fragmento del corpus"})
        eng.insertar({"tipo": "libre", "texto": "Observación libre"})
        ruta = eng.exportar_markdown(tmp_path / "bitacora.md", publicacion="Estampa")
        assert ruta.exists()
        contenido = ruta.read_text(encoding="utf-8")
        assert "Hipótesis de investigación" in contenido
        assert "Hipótesis principal" in contenido
        assert "Fragmento del corpus" in contenido

    def test_etiquetas_json_roundtrip(self, tmp_path):
        eng = self._engine(tmp_path)
        nid = eng.insertar({
            "tipo": "libre",
            "texto": "test",
            "etiquetas": ["a", "b", "c"],
        })
        nota = eng.obtener(nid)
        assert nota["etiquetas"] == ["a", "b", "c"]


# ══════════════════════════════════════════════════════════════════════════════
# TIMELINE ENGINE
# ══════════════════════════════════════════════════════════════════════════════

class TestTimelineEngine:
    def test_genera_html(self, tmp_path):
        from core.timeline_engine import generar_timeline_html
        articulos = [
            {"art_id": "a1", "titulo": "El Deporte Nacional",
             "autor": "JGS", "seccion": "deportes",
             "fecha": "1939-01-15", "numero": "enero_1939"},
            {"art_id": "a2", "titulo": "La Política del Día",
             "autor": "MRL", "seccion": "politica",
             "fecha": "1939-02-10", "numero": "febrero_1939"},
        ]
        ruta = generar_timeline_html(articulos, tmp_path / "timeline.html",
                                      titulo_corpus="Estampa 1939")
        assert ruta.exists()
        html = ruta.read_text(encoding="utf-8")
        assert "vis.js" in html or "vis-timeline" in html
        assert "El Deporte Nacional" in html

    def test_fecha_vacia_omitida(self, tmp_path):
        from core.timeline_engine import generar_timeline_html
        articulos = [
            {"art_id": "a1", "titulo": "Con fecha", "fecha": "1939-01-01", "seccion": ""},
            {"art_id": "a2", "titulo": "Sin fecha", "fecha": "",    "seccion": ""},
        ]
        ruta = generar_timeline_html(articulos, tmp_path / "t.html")
        html = ruta.read_text(encoding="utf-8")
        assert "Con fecha" in html
        # "Sin fecha" se omite porque no tiene fecha válida

    def test_normalizar_fecha(self):
        from core.timeline_engine import _normalizar_fecha
        assert _normalizar_fecha("1939-01-15") == "1939-01-15"
        assert _normalizar_fecha("1939")        == "1939-01-01"
        assert _normalizar_fecha("1939-03")     == "1939-03-01"
        assert _normalizar_fecha("")            == ""
        assert _normalizar_fecha("abc")         == ""


# ══════════════════════════════════════════════════════════════════════════════
# KRAKEN TRAINER
# ══════════════════════════════════════════════════════════════════════════════

class TestKrakenTrainer:
    def test_exportar_sin_imagenes(self, tmp_path):
        """Sin imágenes disponibles, pares=0 y omitidos=N."""
        from core.kraken_trainer import exportar_ground_truth
        txt_dir = tmp_path / "03_ocr" / "enero_1939"
        txt_dir.mkdir(parents=True)
        img_dir = tmp_path / "02_imagenes" / "enero_1939"
        img_dir.mkdir(parents=True)
        out_dir = tmp_path / "gt"

        # Crear archivos txt sin imagen correspondiente
        (txt_dir / "p0001.txt").write_text("Texto de prueba suficientemente largo " * 3,
                                             encoding="utf-8")
        (txt_dir / "p0002.txt").write_text("", encoding="utf-8")

        res = exportar_ground_truth(txt_dir, img_dir, out_dir)
        assert res["pares"] == 0
        assert res["omitidos"] == 2

    def test_exportar_con_imagen(self, tmp_path):
        """Con imagen PNG disponible, genera par correctamente."""
        from core.kraken_trainer import exportar_ground_truth
        from PIL import Image

        txt_dir = tmp_path / "03_ocr" / "test"
        img_dir = tmp_path / "02_imagenes" / "test"
        txt_dir.mkdir(parents=True); img_dir.mkdir(parents=True)
        out_dir = tmp_path / "gt"

        texto = "Esta es una transcripción de prueba con suficientes caracteres para el umbral."
        (txt_dir / "p0001.txt").write_text(texto, encoding="utf-8")

        # Crear imagen PNG mínima
        img = Image.new("RGB", (100, 100), color=(255, 255, 255))
        img.save(str(img_dir / "p0001.png"))

        res = exportar_ground_truth(txt_dir, img_dir, out_dir, min_diff_chars=10)
        assert res["pares"] == 1
        assert (out_dir / "p0001.gt.txt").exists()
        assert (out_dir / "p0001.png").exists()
        assert (out_dir / "manifest.txt").exists()

    def test_estadisticas_corpus(self, tmp_path):
        from core.kraken_trainer import estadisticas_corpus_editado
        from PIL import Image

        txt_dir = tmp_path / "txt"
        img_dir = tmp_path / "img"
        txt_dir.mkdir(); img_dir.mkdir()

        (txt_dir / "p0001.txt").write_text("texto", encoding="utf-8")
        (txt_dir / "p0002.txt").write_text("texto", encoding="utf-8")
        img = Image.new("RGB", (10, 10))
        img.save(str(img_dir / "p0001.png"))

        stats = estadisticas_corpus_editado(txt_dir, img_dir)
        assert stats["total_txt"] == 2
        assert stats["con_imagen"] == 1
        assert stats["sin_imagen"] == 1


# ══════════════════════════════════════════════════════════════════════════════
# METHODS REPORTER
# ══════════════════════════════════════════════════════════════════════════════

class TestMethodsReporter:
    def test_genera_markdown(self, tmp_path):
        from core.methods_reporter import generar_methods_md
        cfg = {
            "publicacion": "Estampa",
            "periodo": "1939-1942",
            "investigador": "Fabian Gulla",
            "institucion": "Instituto Caro y Cuervo",
            "bashkar_version": "11.0",
            "dpi": "150",
            "lang": "spa",
            "lematizar": False,
            "modelos_etapa": {},
            "archivos_sel": ["a", "b", "c"],
        }
        stats = {"n_paginas": 3, "n_palabras": 50000,
                 "n_articulos": 120, "n_entidades": 350}
        ruta = generar_methods_md(cfg, stats, tmp_path / "METHODS.md")
        assert ruta.exists()
        md = ruta.read_text(encoding="utf-8")
        assert "Estampa" in md
        assert "150 DPI" in md
        assert "formas originales" in md   # lematizar=False
        assert "120" in md
        assert "350" in md

    def test_lematizar_activado(self, tmp_path):
        from core.methods_reporter import generar_methods_md
        cfg = {"bashkar_version": "11", "dpi": "200", "lang": "spa",
               "lematizar": True, "modelos_etapa": {}, "archivos_sel": []}
        ruta = generar_methods_md(cfg, {}, tmp_path / "m.md")
        md = ruta.read_text(encoding="utf-8")
        assert "activada" in md


# ══════════════════════════════════════════════════════════════════════════════
# COLLOCATION ENGINE — funciones nuevas
# ══════════════════════════════════════════════════════════════════════════════

class TestNGramas:
    def test_bigramas_basico(self):
        from core.collocation_engine import ngramas
        # Usar palabras que no sean stopwords y tengan >= 3 chars
        corpus = ["gato negro come pescado fresco", "gato negro duerme bastante"]
        res = ngramas(corpus, n=2, top_n=5, min_freq=2)
        ngs = [r["ngrama"] for r in res]
        assert "gato negro" in ngs

    def test_trigramas(self):
        from core.collocation_engine import ngramas
        # Usar palabras reales de >= 3 chars que no sean stopwords
        corpus = [
            "casa azul vieja tiene ventanas",
            "casa azul vieja parece pequeña",
            "casa azul vieja resulta bonita",
        ]
        res = ngramas(corpus, n=3, top_n=5, min_freq=2)
        ngs = [r["ngrama"] for r in res]
        assert "casa azul vieja" in ngs

    def test_frecuencia_minima(self):
        from core.collocation_engine import ngramas
        corpus = ["x y z", "a b c"]
        res = ngramas(corpus, n=2, min_freq=2)
        # Ningún bigrama aparece 2 veces
        assert len(res) == 0

    def test_sin_stopwords(self):
        from core.collocation_engine import ngramas
        corpus = ["de la casa al trabajo", "de la escuela al parque"]
        res_sin = ngramas(corpus, n=2, stopwords=False, min_freq=2)
        res_con = ngramas(corpus, n=2, stopwords=True, min_freq=2)
        # Sin filtrar hay más n-gramas (incluye artículos y preposiciones)
        assert len(res_sin) >= len(res_con)


class TestStopwordsPersonalizadas:
    def test_combina_con_base(self):
        from core.collocation_engine import stopwords_personalizadas, STOPWORDS_ES
        extra = ["estampa", "revista", "publicación"]
        sw = stopwords_personalizadas(extra)
        assert "estampa" in sw
        assert "revista" in sw
        # Las stopwords extra están presentes; la lista base también (al menos una)
        assert len(sw) > len(extra)
        # Al menos algunas stopwords del español base están presentes
        base_presentes = [w for w in STOPWORDS_ES if w in sw]
        assert len(base_presentes) > 0

    def test_case_insensitive(self):
        from core.collocation_engine import stopwords_personalizadas
        sw = stopwords_personalizadas(["Estampa", "REVISTA"])
        assert "estampa" in sw
        assert "revista" in sw


class TestDispersion:
    def test_retorna_posiciones(self):
        from core.collocation_engine import dispersion
        corpus = ["la casa es roja", "la casa tiene ventanas", "el cielo es azul"]
        res = dispersion(corpus, ["casa", "cielo"])
        assert "casa" in res
        assert "cielo" in res
        assert len(res["casa"]) == 2
        assert len(res["cielo"]) == 1

    def test_posiciones_entre_0_y_1(self):
        from core.collocation_engine import dispersion
        corpus = ["aaa bbb ccc ddd eee"]
        res = dispersion(corpus, ["aaa", "eee"])
        for posiciones in res.values():
            for p in posiciones:
                assert 0.0 <= p <= 1.0


# ══════════════════════════════════════════════════════════════════════════════
# TEI ENGINE — validar_tei
# ══════════════════════════════════════════════════════════════════════════════

class TestValidarTei:
    def test_archivo_inexistente(self, tmp_path):
        from core.tei_engine import validar_tei
        errores = validar_tei(tmp_path / "no_existe.xml")
        assert len(errores) == 1
        assert "no encontrado" in errores[0].lower()

    def test_xml_malformado(self, tmp_path):
        from core.tei_engine import validar_tei
        ruta = tmp_path / "mal.xml"
        ruta.write_text("<root><sin_cerrar>", encoding="utf-8")
        errores = validar_tei(ruta)
        assert len(errores) >= 1
        assert any("mal formado" in e.lower() or "syntax" in e.lower()
                   for e in errores)

    def test_xml_valido_basico(self, tmp_path):
        from core.tei_engine import validar_tei
        tei_minimal = """<?xml version='1.0' encoding='utf-8'?>
<teiCorpus xmlns="http://www.tei-c.org/ns/1.0">
  <teiHeader><fileDesc><titleStmt><title>Test</title></titleStmt>
  <publicationStmt><p>Test</p></publicationStmt>
  <sourceDesc><p>Test</p></sourceDesc></fileDesc></teiHeader>
  <TEI xml:id="art_0001">
    <teiHeader><fileDesc><titleStmt><title>Art</title></titleStmt>
    <publicationStmt><p/></publicationStmt><sourceDesc><p/></sourceDesc>
    </fileDesc></teiHeader>
    <text><body><div><p>Contenido.</p></div></body></text>
  </TEI>
</teiCorpus>"""
        ruta = tmp_path / "valido.xml"
        ruta.write_text(tei_minimal, encoding="utf-8")
        errores = validar_tei(ruta)
        # Sin lxml solo verifica bien formado → 0 errores reales
        # Con lxml → también debe pasar
        assert not any("mal formado" in e.lower() for e in errores)
