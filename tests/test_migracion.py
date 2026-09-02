"""tests/test_migracion.py — Tests del migrador .bashkar v10 → v11."""
import json
from pathlib import Path


class TestNecesitaMigracion:
    def test_v10_necesita_migracion(self, bashkar_v10):
        from datos.migracion import necesita_migracion
        assert necesita_migracion(str(bashkar_v10))

    def test_v11_no_necesita(self, tmp_path):
        from datos.migracion import necesita_migracion
        ruta = tmp_path / "nuevo.bashkar"
        with open(ruta, "w") as f:
            json.dump({"version": "11", "nombre": "test"}, f)
        assert not necesita_migracion(str(ruta))

    def test_archivo_inexistente(self):
        from datos.migracion import necesita_migracion
        assert not necesita_migracion("ruta_que_no_existe.bashkar")


class TestMigrar:
    def test_migrar_basico(self, bashkar_v10):
        from datos.migracion import migrar
        resultado = migrar(str(bashkar_v10))
        assert resultado["ok"] is True
        assert resultado["articulos"] == 2
        assert resultado["entidades"] == 5  # 2 personas + 2 lugares + 1 org

    def test_crea_backup(self, bashkar_v10):
        from datos.migracion import migrar
        migrar(str(bashkar_v10))
        backups = list(bashkar_v10.parent.glob("*_v10_backup_*.bashkar"))
        assert len(backups) == 1

    def test_actualiza_version(self, bashkar_v10):
        from datos.migracion import migrar
        migrar(str(bashkar_v10))
        with open(bashkar_v10, encoding="utf-8") as f:
            datos = json.load(f)
        assert datos["version"] == "11"

    def test_crea_db(self, bashkar_v10):
        from datos.migracion import migrar
        resultado = migrar(str(bashkar_v10))
        ruta_db = Path(resultado["ruta_db"])
        assert ruta_db.exists()

    def test_campo_db_en_json(self, bashkar_v10):
        from datos.migracion import migrar
        migrar(str(bashkar_v10))
        with open(bashkar_v10, encoding="utf-8") as f:
            datos = json.load(f)
        assert "db" in datos

    def test_articulos_en_db(self, bashkar_v10):
        from datos.migracion import migrar
        from datos.repositorio import Repositorio
        resultado = migrar(str(bashkar_v10))
        repo = Repositorio(resultado["ruta_db"])
        arts = repo.listar_articulos()
        assert len(arts) == 2

    def test_ocr_migrado(self, bashkar_v10):
        from datos.migracion import migrar
        from datos.repositorio import Repositorio
        resultado = migrar(str(bashkar_v10))
        repo = Repositorio(resultado["ruta_db"])
        texto = repo.obtener_texto("art_001", limpio=True)
        assert texto is not None
        assert len(texto) > 0

    def test_entidades_migradas(self, bashkar_v10):
        from datos.migracion import migrar
        from datos.repositorio import Repositorio
        resultado = migrar(str(bashkar_v10))
        repo = Repositorio(resultado["ruta_db"])
        personas = repo.buscar_entidades(categoria="personas")
        assert len(personas) == 2
        textos = [p["texto"] for p in personas]
        assert "German Arciniegas" in textos
        assert "Lopez de Mesa" in textos

    def test_ya_no_necesita_migracion(self, bashkar_v10):
        from datos.migracion import migrar, necesita_migracion
        migrar(str(bashkar_v10))
        assert not necesita_migracion(str(bashkar_v10))

    def test_migracion_idempotente_estructura(self, bashkar_v10):
        """Segunda migración no debe romper nada (aunque no debería ocurrir)."""
        from datos.migracion import migrar, necesita_migracion
        migrar(str(bashkar_v10))
        assert not necesita_migracion(str(bashkar_v10))


class TestNormalizarAutor:
    """Regresión: .bashkar v10 reales (pipeline basado en pandas) dejaban en
    "autor" basura de la conversión DataFrame→JSON ("nan", "", "None") en vez
    de vacío real, y el resto del código compara contra el valor canónico
    "Anónimo / Sin atribuir" — confirmado sobre
    proyectos/Proyecto_04_Mar_2026.db: 142/349 artículos con autor=="nan" y
    28/349 con autor=="" no se contaban como anónimos aguas abajo."""

    def test_none_a_anonimo(self):
        from datos.migracion import _normalizar_autor, AUTOR_ANONIMO
        assert _normalizar_autor(None) == AUTOR_ANONIMO

    def test_string_nan_a_anonimo(self):
        from datos.migracion import _normalizar_autor, AUTOR_ANONIMO
        assert _normalizar_autor("nan") == AUTOR_ANONIMO
        assert _normalizar_autor("NaN") == AUTOR_ANONIMO

    def test_vacio_a_anonimo(self):
        from datos.migracion import _normalizar_autor, AUTOR_ANONIMO
        assert _normalizar_autor("") == AUTOR_ANONIMO
        assert _normalizar_autor("   ") == AUTOR_ANONIMO

    def test_string_none_a_anonimo(self):
        from datos.migracion import _normalizar_autor, AUTOR_ANONIMO
        assert _normalizar_autor("None") == AUTOR_ANONIMO

    def test_nombre_real_se_conserva(self):
        from datos.migracion import _normalizar_autor
        assert _normalizar_autor("German Arciniegas") == "German Arciniegas"

    def test_migrar_normaliza_autor_basura(self, tmp_path):
        """Un .bashkar v10 con basura de OCR/pandas en "autor" queda con el
        valor canónico tras migrar, no con la basura original."""
        import json
        from datos.migracion import migrar, AUTOR_ANONIMO
        from datos.repositorio import Repositorio

        ruta = tmp_path / "sucio.bashkar"
        data = {
            "version": "10",
            "nombre": "Sucio Test",
            "articulos": [
                {"id": "a1", "titulo": "T1", "autor": "nan", "n_palabras": 10},
                {"id": "a2", "titulo": "T2", "autor": "", "n_palabras": 10},
                {"id": "a3", "titulo": "T3", "autor": None, "n_palabras": 10},
                {"id": "a4", "titulo": "T4", "autor": "Alfonso Fuenmayor", "n_palabras": 10},
            ],
        }
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        resultado = migrar(str(ruta))
        repo = Repositorio(resultado["ruta_db"])
        arts = {a["id"]: a for a in repo.listar_articulos()}

        assert arts["a1"]["autor"] == AUTOR_ANONIMO
        assert arts["a2"]["autor"] == AUTOR_ANONIMO
        assert arts["a3"]["autor"] == AUTOR_ANONIMO
        assert arts["a4"]["autor"] == "Alfonso Fuenmayor"
