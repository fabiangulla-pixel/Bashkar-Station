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
