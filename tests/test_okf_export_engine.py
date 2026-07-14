"""tests/test_okf_export_engine.py — Exportador de bundle OKF.

Cubre: estructura del bundle, fusión de una entidad repetida entre varios
artículos en un solo archivo, escape de frontmatter YAML (comillas/tildes/
saltos de línea) y filtrado de artículos sin OCR ("inválidos" para OKF).
Usa una DB SQLite real de prueba (fixture `repo`/`tmp_db` de conftest.py),
sin mocks — mismo estilo que tests/test_grafo_entidades.py.
"""

from pathlib import Path

from core.okf_export_engine import (
    _articulo_slug,
    _frontmatter,
    _slug,
    exportar_proyecto_okf,
)


# ── Helpers de slug / frontmatter ───────────────────────────────────────────

class TestSlug:
    def test_determinista_y_ascii(self):
        assert _slug("España, ¡Colombia!") == _slug("España, ¡Colombia!")
        assert _slug("España") == "espana"

    def test_vacio_da_fallback(self):
        assert _slug("") == "sin-titulo"
        assert _slug(None) == "sin-titulo"

    def test_articulo_slug_sufijo_id_evita_colision(self):
        a = {"id": "art_001", "titulo": "La educación"}
        b = {"id": "art_002", "titulo": "La educación"}
        assert _articulo_slug(a) != _articulo_slug(b)


class TestFrontmatter:
    def test_escapa_comillas_y_backslash(self):
        fm = _frontmatter({"type": "Articulo",
                           "title": 'Un "titular" con \\barra'})
        linea = [l for l in fm.splitlines() if l.startswith("title:")][0]
        assert linea == r'title: "Un \"titular\" con \\barra"'

    def test_colapsa_saltos_de_linea(self):
        fm = _frontmatter({"type": "Articulo", "description": "linea1\nlinea2"})
        linea = [l for l in fm.splitlines() if l.startswith("description:")][0]
        assert "\n" not in linea.split(": ", 1)[1].strip('"')
        assert linea == 'description: "linea1 linea2"'

    def test_preserva_tildes(self):
        fm = _frontmatter({"type": "Entidad", "title": "Bogotá"})
        assert 'title: "Bogotá"' in fm

    def test_omite_campos_vacios_salvo_type(self):
        fm = _frontmatter({"type": "Documento", "title": "", "resource": None})
        assert "title:" not in fm
        assert "resource:" not in fm
        assert "type: " in fm

    def test_frontmatter_parseable_con_yaml(self):
        import pytest
        yaml = pytest.importorskip("yaml")
        fm = _frontmatter({
            "type": "Articulo",
            "title": 'Título: "reportaje" con dos puntos, comillas y \\backslash',
            "tags": ["articulo", "numero:1939-01"],
        })
        # el bloque completo trae los delimitadores --- de frontmatter;
        # para parsear como YAML de un solo documento se aísla el cuerpo.
        cuerpo_yaml = "\n".join(fm.splitlines()[1:-1])
        data = yaml.safe_load(cuerpo_yaml)
        assert data["type"] == "Articulo"
        assert data["tags"] == ["articulo", "numero:1939-01"]
        assert '"reportaje"' in data["title"]


# ── Bundle completo sobre DB real ───────────────────────────────────────────

def _sembrar_corpus(repo, articulo_simple, articulo_segundo):
    """Dos artículos del mismo número, ambos con OCR, con una entidad
    ('Colombia') mencionada en ambos y otra ('Bogotá') solo en el primero."""
    articulo_segundo = dict(articulo_segundo)
    articulo_segundo["numero"] = articulo_simple["numero"]
    repo.guardar_articulo(articulo_simple)
    repo.guardar_articulo(articulo_segundo)
    repo.guardar_ocr("art_001", "texto crudo 1",
                     "La educación en Colombia avanza cerca de Bogotá.",
                     0.8, "tesseract")
    repo.guardar_ocr("art_002", "texto crudo 2",
                     "Colombia moderniza su fotografía.", 0.75, "tesseract")
    repo.guardar_entidades("art_001", [
        {"texto": "Colombia", "categoria": "lugares", "confianza": 0.9},
        {"texto": "Bogotá", "categoria": "lugares", "confianza": 0.9},
    ])
    repo.guardar_entidades("art_002", [
        {"texto": "Colombia", "categoria": "lugares", "confianza": 0.8},
    ])
    repo.fundir_menciones_en_canonicas()


class TestEstructuraBundle:
    def test_escribe_index_documentos_articulos_entidades(
            self, repo, tmp_path, articulo_simple, articulo_segundo):
        _sembrar_corpus(repo, articulo_simple, articulo_segundo)
        destino = tmp_path / "bundle"
        res = exportar_proyecto_okf(repo, destino, nombre_proyecto="Estampa")

        assert res["ok"] is True
        assert res["n_articulos"] == 2
        assert res["n_documentos"] == 1
        assert res["n_entidades"] == 2  # Colombia + Bogotá

        assert (destino / "index.md").exists()
        assert (destino / "documentos" / "estampa-1939-01.md").exists()
        assert (destino / "articulos").is_dir()
        assert len(list((destino / "articulos").glob("*.md"))) == 2
        assert (destino / "entidades" / "lugar-colombia.md").exists()
        assert (destino / "entidades" / "lugar-bogota.md").exists()

    def test_index_tiene_type_bundle_y_enlaces(
            self, repo, tmp_path, articulo_simple, articulo_segundo):
        _sembrar_corpus(repo, articulo_simple, articulo_segundo)
        destino = tmp_path / "bundle"
        exportar_proyecto_okf(repo, destino, nombre_proyecto="Estampa")

        contenido = (destino / "index.md").read_text(encoding="utf-8")
        assert contenido.startswith("---\ntype: \"Bundle\"")
        assert "documentos/estampa-1939-01.md" in contenido
        assert "entidades/lugar-colombia.md" in contenido

    def test_documento_enlaza_sus_articulos(
            self, repo, tmp_path, articulo_simple, articulo_segundo):
        _sembrar_corpus(repo, articulo_simple, articulo_segundo)
        destino = tmp_path / "bundle"
        exportar_proyecto_okf(repo, destino)

        doc = (destino / "documentos" / "estampa-1939-01.md").read_text(encoding="utf-8")
        assert "type: \"Documento\"" in doc
        assert "../articulos/" in doc
        assert doc.count("../articulos/") == 2


class TestFusionEntidad:
    def test_entidad_repetida_en_dos_articulos_es_un_solo_archivo(
            self, repo, tmp_path, articulo_simple, articulo_segundo):
        _sembrar_corpus(repo, articulo_simple, articulo_segundo)
        destino = tmp_path / "bundle"
        exportar_proyecto_okf(repo, destino)

        archivos_colombia = list(destino.glob("entidades/*colombia*.md"))
        assert len(archivos_colombia) == 1

        contenido = archivos_colombia[0].read_text(encoding="utf-8")
        assert "## Apariciones" in contenido
        # ambos artículos aparecen enlazados en el mismo archivo
        assert contenido.count("../articulos/") == 2

    def test_entidad_mencionada_una_vez_no_muestra_dos_apariciones(
            self, repo, tmp_path, articulo_simple, articulo_segundo):
        _sembrar_corpus(repo, articulo_simple, articulo_segundo)
        destino = tmp_path / "bundle"
        exportar_proyecto_okf(repo, destino)

        contenido = (destino / "entidades" / "lugar-bogota.md").read_text(encoding="utf-8")
        assert contenido.count("../articulos/") == 1


class TestFiltradoArticulosInvalidos:
    def test_articulo_sin_ocr_se_omite(self, repo, tmp_path, articulo_simple):
        # articulo_simple no tiene texto OCR asociado (no se llamó guardar_ocr)
        repo.guardar_articulo(articulo_simple)
        destino = tmp_path / "bundle"
        res = exportar_proyecto_okf(repo, destino)

        assert res["n_articulos"] == 0
        assert res["n_documentos"] == 0  # sin artículos válidos, no hay documento
        assert not (destino / "articulos").exists() or \
            not list((destino / "articulos").glob("*.md"))

    def test_articulo_anonimo_se_exporta_con_autor_generico(
            self, repo, tmp_path, articulo_segundo):
        # articulo_segundo no trae "autor" -> corpus históricamente anónimo,
        # debe exportarse igual (no es "inválido"), solo con autor genérico.
        repo.guardar_articulo(articulo_segundo)
        repo.guardar_ocr("art_002", "crudo", "Texto de una nota anónima.",
                         0.7, "tesseract")
        destino = tmp_path / "bundle"
        res = exportar_proyecto_okf(repo, destino)

        assert res["n_articulos"] == 1
        archivo = next((destino / "articulos").glob("*.md"))
        contenido = archivo.read_text(encoding="utf-8")
        assert "**Autor:** Anónimo" in contenido

    def test_bundle_vacio_no_falla(self, repo, tmp_path):
        destino = tmp_path / "bundle"
        res = exportar_proyecto_okf(repo, destino)
        assert res == {"ok": True, "carpeta": str(destino),
                       "n_documentos": 0, "n_articulos": 0, "n_entidades": 0}
        assert (destino / "index.md").exists()


class TestRelacionesEnEntidad:
    def test_relacion_entidad_entidad_se_enlaza(
            self, repo, tmp_path, articulo_simple, articulo_segundo):
        _sembrar_corpus(repo, articulo_simple, articulo_segundo)
        a = repo.id_canonico("lugar", "Colombia")
        b = repo.id_canonico("lugar", "Bogotá")
        repo.guardar_relacion(a, "ubicado_en", destino_id=b, fuente="manual")

        destino = tmp_path / "bundle"
        exportar_proyecto_okf(repo, destino)

        contenido = (destino / "entidades" / "lugar-colombia.md").read_text(encoding="utf-8")
        assert "## Relaciones" in contenido
        assert "ubicado_en" in contenido
        assert "entidades/lugar-bogota.md" in contenido
