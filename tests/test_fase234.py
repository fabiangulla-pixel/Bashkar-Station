"""tests/test_fase234.py — Fases 2-4: vocabulario controlado y exploradores.

Vocabulario controlado (Fase 2), geocodificación + mapa + timeline (Fase 3) y
export RDF opcional con degradación con gracia (Fase 4). Todo offline.
"""
import os

import pytest


# ── Fase 2: vocabulario controlado ────────────────────────────────────────────

class TestVocabulario:
    def test_arcaismos_offline(self):
        from core import vocabulario_controlado as vc
        vocab = vc.construir_vocabulario(incluir_entidades=False)
        assert len(vocab) > 0
        # los arcaísmos morfológicos siempre están
        assert any(e["categoria"] == "arcaismo" for e in vocab)

    def test_incluye_entidades_canonicas(self, repo, tmp_db, articulo_simple):
        from datos.migracion import aplicar_grafo
        from core import vocabulario_controlado as vc
        repo.guardar_articulo(articulo_simple)
        repo.guardar_entidades("art_001", [
            {"texto": "Bogotá", "categoria": "lugares", "confianza": 0.9},
        ])
        aplicar_grafo(tmp_db, fundir=True)
        vocab = vc.construir_vocabulario(ruta_db_proyecto=tmp_db,
                                         incluir_entidades=True)
        entidades = [e for e in vocab if e["categoria"] == "entidad"]
        assert any(e["tipo_entidad"] == "lugar" for e in entidades)

    def test_consultar_filtra(self):
        from core import vocabulario_controlado as vc
        vocab = vc.construir_vocabulario(incluir_entidades=False)
        res = vc.consultar(vocab, categoria="arcaismo")
        assert all(e["categoria"] == "arcaismo" for e in res)
        assert len(res) == len([e for e in vocab if e["categoria"] == "arcaismo"])

    def test_exportar_csv_y_json(self, tmp_path):
        from core import vocabulario_controlado as vc
        vocab = vc.construir_vocabulario(incluir_entidades=False)
        csv_path = str(tmp_path / "v.csv")
        json_path = str(tmp_path / "v.json")
        n1 = vc.exportar_csv(vocab, csv_path)
        n2 = vc.exportar_json(vocab, json_path)
        assert n1 == n2 == len(vocab)
        assert os.path.exists(csv_path) and os.path.exists(json_path)


# ── Fase 3: exploradores ──────────────────────────────────────────────────────

class TestExploradores:
    def _cans(self):
        return [
            {"id": "lugar:bogota", "tipo": "lugar", "nombre": "Bogotá", "n_menciones": 5},
            {"id": "lugar:espana", "tipo": "lugar", "nombre": "España", "n_menciones": 3},
            {"id": "lugar:noexiste", "tipo": "lugar", "nombre": "Quimera", "n_menciones": 1},
            {"id": "persona:franco", "tipo": "persona", "nombre": "Franco", "n_menciones": 4},
        ]

    def test_geocodificar_solo_lugares_conocidos(self):
        from core import exploradores as ex
        lug = ex.geocodificar_lugares(self._cans())
        nombres = {l["nombre"] for l in lug}
        # Bogotá y España se georreferencian; Quimera no; Franco no es lugar
        assert "Bogotá" in nombres and "España" in nombres
        assert "Quimera" not in nombres and "Franco" not in nombres
        assert all("lat" in l and "lon" in l for l in lug)

    def test_mapa_html(self, tmp_path):
        from core import exploradores as ex
        lug = ex.geocodificar_lugares(self._cans())
        salida = str(tmp_path / "mapa.html")
        res = ex.mapa_lugares_html(lug, salida)
        assert res["ok"] and res["n"] == 2
        assert os.path.exists(salida)
        assert res["motor"] in ("folium", "leaflet_cdn")

    def test_mapa_vacio(self, tmp_path):
        from core import exploradores as ex
        res = ex.mapa_lugares_html([], str(tmp_path / "m.html"))
        assert res["ok"] is False

    def test_timeline_enlaza_transcripcion(self, tmp_path):
        from core import exploradores as ex
        salida = str(tmp_path / "tl.html")
        res = ex.timeline_numeros_html([
            {"numero": "ene 1939", "fecha": "1939-01", "n_articulos": 40,
             "ruta_transcripcion": "ene.html"},
            {"numero": "feb 1939", "fecha": "1939-02", "n_articulos": 35},
        ], salida)
        assert res["ok"] and res["n"] == 2
        html = open(salida, encoding="utf-8").read()
        assert "ene.html" in html  # enlace a transcripción
        assert "sin transcripción" in html  # el que no tiene


# ── Fase 4: export RDF opcional ───────────────────────────────────────────────

class TestRDF:
    def test_exportar_rdf(self, tmp_path):
        from core import exploradores as ex
        graf = {
            "nodos": [
                {"id": "persona:franco", "tipo": "persona", "nombre": "Franco",
                 "wikidata_id": "Q29179"},
                {"id": "lugar:espana", "tipo": "lugar", "nombre": "España"},
            ],
            "aristas": [
                {"origen_id": "persona:franco", "predicado": "ubicado_en",
                 "destino_id": "lugar:espana"},
            ],
        }
        salida = str(tmp_path / "g.ttl")
        res = ex.exportar_rdf(graf, salida)
        assert res["ok"] and res["n_tripletas"] > 0
        assert res["motor"] in ("rdflib", "turtle_manual")
        ttl = open(salida, encoding="utf-8").read()
        assert "@prefix" in ttl
        assert "Franco" in ttl
