"""
tests/test_tei_engine.py — Tests para core/tei_engine.py

Cubre: articulo_a_tei (estructura XML, campos, entidades),
       exportar_corpus_tei (archivo generado, parseable, múltiples artículos),
       exportar_bibtex (sintaxis BibTeX, campos obligatorios).
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.tei_engine import (
    TEI_NS,
    articulo_a_tei,
    exportar_bibtex,
    exportar_corpus_tei,
)


def _tag(nombre):
    return f"{{{TEI_NS}}}{nombre}"


# ══════════════════════════════════════════════════════════════════════════════
# articulo_a_tei — estructura básica
# ══════════════════════════════════════════════════════════════════════════════

class TestArticuloATei:
    def _art_base(self):
        return articulo_a_tei(
            art_id="art_0001",
            texto="El texto del artículo de prueba.\n\nSegundo párrafo.",
            titulo="Título de Prueba",
            autor="Jorge García",
            fuente="Revista Estampa",
            fecha="1939-01",
            ner=None,
        )

    def test_retorna_elemento_et(self):
        el = self._art_base()
        assert isinstance(el, ET.Element)

    def test_tag_raiz_es_tei(self):
        el = self._art_base()
        assert el.tag == _tag("TEI")

    def test_tiene_tei_header(self):
        el = self._art_base()
        header = el.find(_tag("teiHeader"))
        assert header is not None

    def test_tiene_text_body(self):
        el = self._art_base()
        text = el.find(_tag("text"))
        assert text is not None
        body = text.find(_tag("body"))
        assert body is not None

    def test_titulo_en_head(self):
        el = self._art_base()
        heads = el.iter(_tag("head"))
        textos = [h.text for h in heads if h.text]
        assert any("Prueba" in t for t in textos)

    def test_parrafos_generados(self):
        el = self._art_base()
        parrafos = list(el.iter(_tag("p")))
        assert len(parrafos) >= 2

    def test_sin_ner_no_genera_standoff(self):
        el = self._art_base()
        standoff = el.find(_tag("standOff"))
        assert standoff is None

    def test_con_ner_genera_standoff(self):
        el = articulo_a_tei(
            art_id="art_0002",
            texto="Texto con entidades.",
            titulo="Prueba NER",
            autor=None,
            fuente="Estampa",
            fecha=None,
            ner={"personas": ["Simón Bolívar", "Jorge García"],
                 "lugares": ["Bogotá"]},
        )
        standoff = el.find(_tag("standOff"))
        assert standoff is not None

    def test_entidades_en_standoff(self):
        el = articulo_a_tei(
            art_id="art_0003",
            texto="Texto.",
            titulo="T",
            autor=None,
            fuente="E",
            fecha=None,
            ner={"personas": ["Bolívar"], "lugares": ["Bogotá"]},
        )
        anotaciones = list(el.iter(_tag("annotation")))
        textos = [a.text for a in anotaciones if a.text]
        assert "Bolívar" in textos
        assert "Bogotá" in textos

    def test_sin_titulo_usa_id_como_fallback(self):
        el = articulo_a_tei(
            art_id="art_fallback",
            texto="Texto de prueba.",
            titulo=None,
            autor=None,
            fuente="E",
            fecha=None,
            ner=None,
        )
        # teiHeader debe tener título que incluya el id
        title_els = list(el.iter(_tag("title")))
        textos = [t.text for t in title_els if t.text]
        assert any("art_fallback" in t for t in textos)

    def test_autor_en_header(self):
        el = self._art_base()
        pers_names = list(el.iter(_tag("persName")))
        textos = [p.text for p in pers_names if p.text]
        assert any("García" in t for t in textos)

    def test_ner_con_lista_vacia_no_genera_standoff(self):
        el = articulo_a_tei(
            art_id="art_0004",
            texto="Texto.",
            titulo="T",
            autor=None,
            fuente="E",
            fecha=None,
            ner={"personas": [], "lugares": []},
        )
        standoff = el.find(_tag("standOff"))
        assert standoff is None

    def test_texto_multi_parrafo_divide_correctamente(self):
        el = articulo_a_tei(
            art_id="art_multi",
            texto="Primer párrafo.\n\nSegundo párrafo.\n\nTercer párrafo.",
            titulo="Multi",
            autor=None,
            fuente="E",
            fecha=None,
            ner=None,
        )
        div = list(el.iter(_tag("div")))[0]
        parrafos = [c for c in div if c.tag == _tag("p")]
        assert len(parrafos) == 3


# ══════════════════════════════════════════════════════════════════════════════
# exportar_corpus_tei
# ══════════════════════════════════════════════════════════════════════════════

class TestExportarCorpusTei:
    def _articulos(self, n=3):
        return [
            {
                "id": f"art_{i:04d}",
                "texto": f"Texto del artículo número {i}. " * 5,
                "titulo": f"Artículo {i}",
                "autor": "Autor Prueba",
                "fecha": "1939-01",
                "ner": {"personas": [f"Persona{i}"], "lugares": ["Bogotá"]},
            }
            for i in range(n)
        ]

    def test_genera_archivo(self, tmp_path):
        ruta = tmp_path / "corpus.xml"
        exportar_corpus_tei(self._articulos(), ruta=ruta)
        assert ruta.exists()

    def test_archivo_es_xml_valido(self, tmp_path):
        ruta = tmp_path / "corpus.xml"
        exportar_corpus_tei(self._articulos(), ruta=ruta)
        tree = ET.parse(str(ruta))
        assert tree.getroot() is not None

    def test_raiz_es_tei_corpus(self, tmp_path):
        ruta = tmp_path / "corpus.xml"
        exportar_corpus_tei(self._articulos(), ruta=ruta)
        tree = ET.parse(str(ruta))
        raiz = tree.getroot()
        assert "teiCorpus" in raiz.tag

    def test_n_articulos_tei_dentro(self, tmp_path):
        ruta = tmp_path / "corpus.xml"
        arts = self._articulos(4)
        exportar_corpus_tei(arts, ruta=ruta)
        tree = ET.parse(str(ruta))
        tei_elements = [e for e in tree.getroot() if "TEI" in e.tag]
        assert len(tei_elements) == 4

    def test_crea_directorio_si_no_existe(self, tmp_path):
        ruta = tmp_path / "subdir" / "corpus.xml"
        exportar_corpus_tei(self._articulos(1), ruta=ruta)
        assert ruta.exists()

    def test_lista_vacia_genera_corpus_sin_articulos(self, tmp_path):
        ruta = tmp_path / "vacio.xml"
        exportar_corpus_tei([], ruta=ruta)
        assert ruta.exists()
        tree = ET.parse(str(ruta))
        assert tree.getroot() is not None

    def test_callback_llamado(self, tmp_path):
        ruta = tmp_path / "corpus.xml"
        mensajes = []
        exportar_corpus_tei(self._articulos(2), ruta=ruta,
                            callback=mensajes.append)
        assert len(mensajes) > 0


# ══════════════════════════════════════════════════════════════════════════════
# exportar_bibtex
# ══════════════════════════════════════════════════════════════════════════════

class TestExportarBibtex:
    def _articulos(self, n=3):
        return [
            {
                "id": f"art_{i:04d}",
                "titulo": f"Artículo de prueba número {i}",
                "autor": "García, Jorge",
                "fecha": "1939-01",
                "numero": "enero_1939",
                "pagina": f"p00{i:02d}",
            }
            for i in range(n)
        ]

    def test_genera_archivo(self, tmp_path):
        ruta = tmp_path / "biblio.bib"
        exportar_bibtex(self._articulos(), ruta)
        assert ruta.exists()

    def test_contiene_entradas_bibtex(self, tmp_path):
        ruta = tmp_path / "biblio.bib"
        exportar_bibtex(self._articulos(3), ruta)
        contenido = ruta.read_text("utf-8")
        assert "@article" in contenido.lower() or "@misc" in contenido.lower()

    def test_n_entradas_igual_n_articulos(self, tmp_path):
        ruta = tmp_path / "biblio.bib"
        exportar_bibtex(self._articulos(4), ruta)
        contenido = ruta.read_text("utf-8")
        # Contar entradas @article o @misc
        import re
        entradas = re.findall(r"@\w+\{", contenido, re.IGNORECASE)
        assert len(entradas) == 4

    def test_lista_vacia_genera_archivo_vacio_o_cabecera(self, tmp_path):
        ruta = tmp_path / "vacio.bib"
        exportar_bibtex([], ruta)
        assert ruta.exists()

    def test_titulo_presente_en_bib(self, tmp_path):
        ruta = tmp_path / "biblio.bib"
        exportar_bibtex(self._articulos(1), ruta)
        contenido = ruta.read_text("utf-8")
        assert "Artículo de prueba número 0" in contenido or "prueba" in contenido.lower()
