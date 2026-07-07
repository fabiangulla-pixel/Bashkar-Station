# -*- coding: utf-8 -*-
"""
Tests del backend PyTorch de Word2Vec (necesario en Python 3.14, donde gensim
no compila). Verifican la interfaz común `.wv` y el flujo entrenar→expandir→guardar.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.word_vectors import (
    _KeyedVectors,
    _ModeloVectores,
    entrenar_word2vec,
    cargar_word2vec,
    expandir_campo_semantico,
    similaridad_coseno,
)


# Corpus sintético con dos campos semánticos claros (gato/perro vs lluvia/sol),
# repetido para que skip-gram aprenda las co-ocurrencias.
_CORPUS = [
    "el gato y el perro juegan en el jardín con la pelota cada tarde. "
    "el perro corre y el gato salta mientras el animal descansa al sol.",
    "la lluvia cae sobre el campo y el sol aparece después de la tormenta. "
    "el cielo nublado deja paso al sol radiante tras la lluvia intensa.",
] * 30


# ── _KeyedVectors: interfaz mínima ───────────────────────────────────────────

class TestKeyedVectors:
    def _kv(self):
        palabras = ["rey", "reina", "hombre", "mujer"]
        # vectores donde rey~reina y hombre~mujer
        m = np.array([
            [1.0, 0.0, 0.0],
            [0.9, 0.1, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.9, 0.1],
        ], dtype=np.float32)
        return _KeyedVectors(palabras, m)

    def test_contains_y_getitem(self):
        kv = self._kv()
        assert "rey" in kv
        assert "inexistente" not in kv
        assert kv["rey"].shape == (3,)

    def test_most_similar_devuelve_vecino_correcto(self):
        kv = self._kv()
        sim = kv.most_similar(positive=["rey"], topn=1)
        assert sim[0][0] == "reina"
        assert 0.0 <= sim[0][1] <= 1.0

    def test_most_similar_excluye_la_semilla(self):
        kv = self._kv()
        vecinos = [p for p, _ in kv.most_similar(positive=["rey"], topn=3)]
        assert "rey" not in vecinos

    def test_most_similar_sin_semillas_validas(self):
        kv = self._kv()
        assert kv.most_similar(positive=["xyz"], topn=5) == []

    def test_guardar_cargar_roundtrip(self, tmp_path):
        kv = self._kv()
        ruta = tmp_path / "kv.npz"
        kv.guardar(ruta)
        kv2 = _KeyedVectors.cargar(ruta)
        assert "rey" in kv2
        assert np.allclose(kv2["rey"], kv["rey"])


# ── Entrenamiento end-to-end (backend torch en 3.14) ─────────────────────────

class TestEntrenamiento:
    def test_entrena_y_expande(self, tmp_path):
        modelo = entrenar_word2vec(_CORPUS, tmp_path / "m",
                                   vector_size=40, epochs=20, min_count=2)
        assert modelo is not None
        assert hasattr(modelo, "wv")
        assert len(modelo.wv.index_to_key) > 5

        # la expansión devuelve la estructura esperada
        res = expandir_campo_semantico(["gato"], modelo, topn=5, umbral_sim=0.0)
        assert "gato" in res["semillas_encontradas"]
        assert isinstance(res["expansiones"], list)
        assert "campo_expandido" in res

    def test_corpus_insuficiente_devuelve_none(self, tmp_path):
        modelo = entrenar_word2vec(["dos palabras"], tmp_path / "m")
        assert modelo is None

    def test_similaridad_documentos(self, tmp_path):
        modelo = entrenar_word2vec(_CORPUS, tmp_path / "m",
                                   vector_size=40, epochs=15, min_count=2)
        s = similaridad_coseno(_CORPUS[0], _CORPUS[1], modelo)
        assert -1.0 <= s <= 1.0

    def test_persistencia_recarga(self, tmp_path):
        modelo = entrenar_word2vec(_CORPUS, tmp_path / "m",
                                   vector_size=40, epochs=10, min_count=2)
        assert modelo is not None
        recargado = cargar_word2vec(tmp_path / "m")
        assert recargado is not None
        assert len(recargado.wv.index_to_key) == len(modelo.wv.index_to_key)


# ── Compatibilidad: expandir acepta tanto modelo como wv directo ─────────────

class TestCompatibilidadInterfaz:
    def test_expandir_acepta_modelo_y_wv(self, tmp_path):
        modelo = entrenar_word2vec(_CORPUS, tmp_path / "m",
                                   vector_size=40, epochs=10, min_count=2)
        # con el modelo (tiene .wv)
        r1 = expandir_campo_semantico(["perro"], modelo, topn=3, umbral_sim=0.0)
        # con el wv directo (getattr(modelo, "wv", modelo) lo resuelve igual)
        r2 = expandir_campo_semantico(["perro"], modelo.wv, topn=3, umbral_sim=0.0)
        assert r1["semillas_encontradas"] == r2["semillas_encontradas"]
