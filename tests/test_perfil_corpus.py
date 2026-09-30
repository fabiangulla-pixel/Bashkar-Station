"""Perfil de corpus: el enlazador deja de suponer Colombia y 1945."""

from core import entity_linker as EL
from core.perfil_corpus import POR_DEFECTO, PerfilCorpus

ARGENTINA = PerfilCorpus(id="caras-y-caretas", terminos_pais=("argentina", "argentino"),
                         anio_fin=1940)


def _cand(desc):
    return {"id": "Q1", "label": "Alfonso López", "description": desc,
            "url": "", "rango": 0}


def test_perfil_por_defecto_reproduce_el_comportamiento_de_estampa():
    assert POR_DEFECTO.terminos_pais == ("colombia", "colombiano", "colombiana")
    assert POR_DEFECTO.anio_fin == EL._ANIO_CORPUS_FIN == 1945
    assert PerfilCorpus.desde_dict(None) == POR_DEFECTO
    assert PerfilCorpus.desde_dict({}) .es_por_defecto()


def test_desde_dict_completa_y_normaliza():
    p = PerfilCorpus.desde_dict({"id": "x", "terminos_pais": ["Argentina"], "anio_fin": "1939",
                                 "clave_desconocida": 1})
    assert p.terminos_pais == ("argentina",) and p.anio_fin == 1939
    assert not p.es_por_defecto()
    assert p.firma() == PerfilCorpus.desde_dict(p.como_dict()).firma()


def test_bonus_de_pais_sigue_al_perfil():
    col = _cand("político colombiano")
    arg = _cand("político argentino")
    d_col = EL._puntuar_candidato(col, "Alfonso López", "personas") - \
        EL._puntuar_candidato(arg, "Alfonso López", "personas")
    assert d_col > 0  # Estampa: gana el colombiano
    d_arg = EL._puntuar_candidato(arg, "Alfonso López", "personas", perfil=ARGENTINA) - \
        EL._puntuar_candidato(col, "Alfonso López", "personas", perfil=ARGENTINA)
    assert d_arg > 0  # Caras y Caretas: gana el argentino


def test_cache_separada_por_perfil(tmp_path, monkeypatch):
    llamadas = []

    def falso_wikidata(texto, categoria, lang="es"):
        llamadas.append(lang)
        return []
    monkeypatch.setattr(EL, "_llamar_wikidata", falso_wikidata)
    monkeypatch.setattr(EL, "_PAUSA_ENTRE_LLAMADAS", 0)
    cache = str(tmp_path / "c.db")
    EL.enlazar_entidad("Bogotá", "lugares", cache)
    n = len(llamadas)
    EL.enlazar_entidad("Bogotá", "lugares", cache)                    # sale de caché
    assert len(llamadas) == n
    EL.enlazar_entidad("Bogotá", "lugares", cache, perfil=ARGENTINA)  # otra clave
    assert len(llamadas) > n


def test_el_proyecto_guarda_y_recupera_el_perfil(tmp_path, monkeypatch):
    from core import project_manager as PM
    from core.estado import Estado
    monkeypatch.setattr(PM, "_dir_proyectos", lambda: tmp_path)
    monkeypatch.setattr(PM, "_archivo_reciente", lambda: tmp_path / "reciente.txt")
    ruta = PM.nuevo_proyecto("prueba", "Caras y Caretas", "1898-1939")
    assert tmp_path in ruta.parents
    st = Estado()
    PM.cargar_proyecto(ruta, st)
    assert PerfilCorpus.desde_dict(st.perfil_corpus).es_por_defecto()
    st.perfil_corpus = ARGENTINA.como_dict()
    PM.guardar_proyecto(ruta, st)
    st2 = Estado()
    PM.cargar_proyecto(ruta, st2)
    assert PerfilCorpus.desde_dict(st2.perfil_corpus) == ARGENTINA
