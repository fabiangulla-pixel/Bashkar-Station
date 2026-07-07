"""tests/test_grafo_entidades.py — Capa de grafo: entidades canónicas + relaciones.

Cubre la Fase 1 del módulo de entidades/grafo: id estable e idempotente,
fusión de menciones NER en entidades canónicas, tripletas (relaciones) y
la migración reversible (aplicar_grafo / revertir_grafo).
"""


# ── id canónico estable / normalización ──────────────────────────────────────

class TestIdCanonico:
    def test_id_determinista(self):
        from datos.repositorio import Repositorio
        a = Repositorio.id_canonico("persona", "Francisco Franco")
        b = Repositorio.id_canonico("persona", "Francisco Franco")
        assert a == b == "persona:francisco-franco"

    def test_normaliza_tildes_y_mayusculas(self):
        from datos.repositorio import Repositorio
        # "España" y "ESPAÑA" deben colapsar al mismo id
        assert (Repositorio.id_canonico("lugar", "España")
                == Repositorio.id_canonico("lugar", "ESPAÑA")
                == "lugar:espana")

    def test_tipo_separa_homonimos(self):
        from datos.repositorio import Repositorio
        # mismo nombre, distinto tipo → ids distintos
        assert (Repositorio.id_canonico("persona", "Colombia")
                != Repositorio.id_canonico("lugar", "Colombia"))


# ── Entidades canónicas ───────────────────────────────────────────────────────

class TestEntidadesCanonicas:
    def test_guardar_y_obtener(self, repo):
        eid = repo.guardar_entidad_canonica(
            "persona", "Alfonso López",
            atributos={"cargo": "presidente"}, confianza=0.9, fuente="ner")
        assert eid == "persona:alfonso-lopez"
        ent = repo.obtener_entidad_canonica(eid)
        assert ent["nombre"] == "Alfonso López"
        assert ent["tipo"] == "persona"
        assert ent["atributos"]["cargo"] == "presidente"

    def test_upsert_idempotente(self, repo):
        eid1 = repo.guardar_entidad_canonica("lugar", "Bogotá")
        eid2 = repo.guardar_entidad_canonica("lugar", "Bogotá",
                                             atributos={"lat": 4.6})
        assert eid1 == eid2
        cans = repo.listar_entidades_canonicas(tipo="lugar")
        assert len(cans) == 1  # no duplica
        assert cans[0]["atributos"]["lat"] == 4.6  # sí actualiza

    def test_wikidata_no_se_pisa_con_none(self, repo):
        eid = repo.guardar_entidad_canonica("persona", "Mussolini",
                                            wikidata_id="Q23559")
        # un upsert posterior sin wikidata NO debe borrar el qid
        repo.guardar_entidad_canonica("persona", "Mussolini")
        assert repo.obtener_entidad_canonica(eid)["wikidata_id"] == "Q23559"


# ── Fusión de menciones ───────────────────────────────────────────────────────

class TestFusion:
    def test_funde_duplicados(self, repo, articulo_simple, articulo_segundo):
        repo.guardar_articulo(articulo_simple)
        repo.guardar_articulo(articulo_segundo)
        # "Colombia" mencionada en dos artículos distintos
        repo.guardar_entidades("art_001", [
            {"texto": "Colombia", "categoria": "lugares", "confianza": 0.9},
            {"texto": "Bogotá",   "categoria": "lugares", "confianza": 0.9},
        ])
        repo.guardar_entidades("art_002", [
            {"texto": "Colombia", "categoria": "lugares", "confianza": 0.8},
        ])
        res = repo.fundir_menciones_en_canonicas()
        assert res["menciones_vinculadas"] == 3
        cans = repo.listar_entidades_canonicas()
        # 3 menciones → 2 canónicas (Colombia fusionada)
        assert len(cans) == 2
        colombia = repo.obtener_entidad_canonica("lugar:colombia")
        assert colombia["n_menciones"] == 2

    def test_fusion_idempotente(self, repo, articulo_simple):
        repo.guardar_articulo(articulo_simple)
        repo.guardar_entidades("art_001", [
            {"texto": "Franco", "categoria": "personas", "confianza": 0.9},
        ])
        repo.fundir_menciones_en_canonicas()
        repo.fundir_menciones_en_canonicas()  # segunda pasada
        assert len(repo.listar_entidades_canonicas()) == 1
        assert repo.obtener_entidad_canonica("persona:franco")["n_menciones"] == 1


# ── Relaciones (tripletas) ────────────────────────────────────────────────────

class TestRelaciones:
    def test_tripleta_entidad_entidad(self, repo):
        a = repo.guardar_entidad_canonica("persona", "Franco")
        b = repo.guardar_entidad_canonica("lugar", "España")
        rid = repo.guardar_relacion(a, "ubicado_en", destino_id=b,
                                    confianza=0.7, fuente="heuristica")
        assert rid > 0
        rels = repo.listar_relaciones(origen_id=a)
        assert len(rels) == 1
        assert rels[0]["predicado"] == "ubicado_en"
        assert rels[0]["destino_id"] == b

    def test_tripleta_entidad_pagina(self, repo):
        a = repo.guardar_entidad_canonica("persona", "López")
        repo.guardar_relacion(a, "mencionado_en", destino_pagina="art_005",
                              evidencia="art_005", fuente="ner")
        rels = repo.listar_relaciones(predicado="mencionado_en")
        assert len(rels) == 1
        assert rels[0]["destino_pagina"] == "art_005"

    def test_relacion_no_duplica(self, repo):
        a = repo.guardar_entidad_canonica("persona", "A")
        b = repo.guardar_entidad_canonica("persona", "B")
        repo.guardar_relacion(a, "colaboro_con", destino_id=b)
        repo.guardar_relacion(a, "colaboro_con", destino_id=b, confianza=0.5)
        rels = repo.listar_relaciones(origen_id=a)
        assert len(rels) == 1  # upsert, no duplica

    def test_grafo_entidades(self, repo):
        a = repo.guardar_entidad_canonica("persona", "A")
        b = repo.guardar_entidad_canonica("persona", "B")
        repo.guardar_relacion(a, "colaboro_con", destino_id=b)
        repo.guardar_relacion(a, "mencionado_en", destino_pagina="art_001")
        graf = repo.grafo_entidades()
        assert len(graf["nodos"]) == 2
        # solo la arista entidad→entidad cuenta (mencionado_en va a página)
        assert len(graf["aristas"]) == 1


# ── Migración reversible ──────────────────────────────────────────────────────

class TestMigracionGrafo:
    def test_aplicar_y_revertir(self, repo, tmp_db, articulo_simple):
        from datos.migracion import aplicar_grafo, grafo_aplicado, revertir_grafo
        # sembrar menciones
        repo.guardar_articulo(articulo_simple)
        repo.guardar_entidades("art_001", [
            {"texto": "Colombia", "categoria": "lugares", "confianza": 0.9},
        ])
        assert grafo_aplicado(tmp_db) is True  # repo ya creó las tablas via schema

        res = aplicar_grafo(tmp_db, fundir=True)
        assert res["ok"] and res["fundido"]
        assert res["menciones_vinculadas"] == 1

        rev = revertir_grafo(tmp_db)
        assert rev["ok"]
        assert grafo_aplicado(tmp_db) is False

    def test_revertir_preserva_menciones_originales(self, repo, tmp_db, articulo_simple):
        import sqlite3

        from datos.migracion import aplicar_grafo, revertir_grafo
        repo.guardar_articulo(articulo_simple)
        repo.guardar_entidades("art_001", [
            {"texto": "Bogotá",   "categoria": "lugares", "confianza": 0.9},
            {"texto": "Colombia", "categoria": "lugares", "confianza": 0.9},
        ])
        aplicar_grafo(tmp_db, fundir=True)
        revertir_grafo(tmp_db)
        # las menciones originales en `entidades` siguen intactas
        con = sqlite3.connect(tmp_db)
        n = con.execute("SELECT COUNT(*) FROM entidades").fetchone()[0]
        con.close()
        assert n == 2
