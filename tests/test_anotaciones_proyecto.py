"""Las anotaciones van a la base del proyecto abierto, no a la del primero."""

from pathlib import Path
from types import SimpleNamespace

from core.annotation_engine import Anotacion, GestorAnotaciones, ruta_anotaciones


def test_ruta_anotaciones_junto_al_proyecto(tmp_path):
    assert ruta_anotaciones(tmp_path / "x.dbdir" / "P.db") == tmp_path / "x.dbdir" / "P_anotaciones.db"
    assert ruta_anotaciones("") == Path.home() / ".bashkar" / "anotaciones.db"


def test_listar_filtra_y_ordena(tmp_path):
    g = GestorAnotaciones(tmp_path / "a.db")
    for i, (cat, est) in enumerate([("PER", "auto"), ("LOC", "confirmada"), ("PER", "confirmada")]):
        g.insertar(Anotacion(art_id=f"a{i}", texto_orig="x", texto_norm=f"t{i}",
                             categoria=cat, estado=est))
    assert [r["texto_norm"] for r in g.listar()] == ["t2", "t1", "t0"]
    assert [r["texto_norm"] for r in g.listar(categoria="PER", estado="confirmada")] == ["t2"]
    assert len(g.listar(limite=1)) == 1


def test_cambiar_de_proyecto_cambia_la_base(tmp_path, monkeypatch):
    import app
    falso = SimpleNamespace(_anot_gestor=None, _anot_db_ruta=None)
    monkeypatch.setattr(app.ST, "ruta_db", str(tmp_path / "A.db"))
    g1 = app.BashkarApp._anot_gestor_activo(falso)
    monkeypatch.setattr(app.ST, "ruta_db", str(tmp_path / "B.db"))
    g2 = app.BashkarApp._anot_gestor_activo(falso)
    assert Path(g1.ruta_db).name == "A_anotaciones.db"
    assert Path(g2.ruta_db).name == "B_anotaciones.db"
    assert app.BashkarApp._anot_gestor_activo(falso) is g2  # sin cambio, se reutiliza


def test_menciones_canonicas_por_articulo(tmp_path):
    import sqlite3

    from datos.repositorio import Repositorio
    repo = Repositorio(tmp_path / "p.db")
    con = sqlite3.connect(tmp_path / "p.db")
    con.execute("PRAGMA foreign_keys = OFF")
    con.execute("INSERT INTO entidades (id, articulo_id, texto, categoria) "
                "VALUES (1, 'art_0001', 'Gaitán', 'personas')")
    con.execute("INSERT INTO menciones_canonicas (mencion_id, canonica_id) VALUES (1, 'c1')")
    con.commit()
    con.close()
    assert repo.menciones_canonicas_por_articulo() == [("c1", "art_0001")]
