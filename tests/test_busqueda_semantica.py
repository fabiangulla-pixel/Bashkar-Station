"""tests/test_busqueda_semantica.py — Tests de embeddings y búsqueda FAISS."""
import os
import pytest
import numpy as np


def faiss_y_st_disponibles():
    try:
        import faiss
        from sentence_transformers import SentenceTransformer  # noqa
        return True
    except ImportError:
        return False


@pytest.fixture
def indice_con_datos():
    """Índice FAISS con datos sintéticos para tests sin modelos reales."""
    if not pytest.importorskip("faiss", reason="faiss no disponible"):
        pytest.skip("faiss no disponible")
    import faiss as _faiss
    from core.busqueda_semantica import IndiceSemantico
    np.random.seed(42)
    N, D = 15, 384
    embs = np.random.randn(N, D).astype(np.float32)
    _faiss.normalize_L2(embs)
    ids = [f"art_{i:03d}" for i in range(N)]
    indice = IndiceSemantico(dimension=D)
    indice.construir(embs, ids)
    return indice, embs, ids


class TestIndiceSemantico:
    def test_disponibilidad(self):
        from core.busqueda_semantica import faiss_disponible
        assert isinstance(faiss_disponible(), bool)

    def test_construir(self):
        faiss = pytest.importorskip("faiss")
        from core.busqueda_semantica import IndiceSemantico
        embs = np.random.randn(10, 384).astype(np.float32)
        faiss.normalize_L2(embs)
        indice = IndiceSemantico(384)
        indice.construir(embs, [f"art_{i}" for i in range(10)])
        assert indice.construido
        assert indice.n_articulos == 10

    def test_buscar_retorna_mismo(self, indice_con_datos):
        indice, embs, ids = indice_con_datos
        resultados = indice.buscar(embs[0], k=1)
        assert len(resultados) == 1
        assert resultados[0]["articulo_id"] == "art_000"
        assert resultados[0]["similitud"] > 0.99

    def test_buscar_k_resultados(self, indice_con_datos):
        indice, embs, ids = indice_con_datos
        for k in [1, 3, 5, 10]:
            resultados = indice.buscar(embs[0], k=k)
            assert len(resultados) == k

    def test_buscar_ordenado(self, indice_con_datos):
        indice, embs, ids = indice_con_datos
        resultados = indice.buscar(embs[0], k=5)
        for i in range(len(resultados) - 1):
            assert resultados[i]["similitud"] >= resultados[i+1]["similitud"]

    def test_rank_secuencial(self, indice_con_datos):
        indice, embs, ids = indice_con_datos
        resultados = indice.buscar(embs[0], k=5)
        for i, r in enumerate(resultados, start=1):
            assert r["rank"] == i

    def test_buscar_sin_construir_lanza_error(self):
        from core.busqueda_semantica import IndiceSemantico
        indice = IndiceSemantico()
        with pytest.raises(RuntimeError):
            indice.buscar(np.zeros(384, dtype=np.float32), k=5)

    def test_construir_mismatch_lanza_error(self):
        pytest.importorskip("faiss")
        from core.busqueda_semantica import IndiceSemantico
        embs = np.random.randn(5, 384).astype(np.float32)
        with pytest.raises(ValueError):
            IndiceSemantico(384).construir(embs, ["a", "b"])  # 5 embs, 2 ids

    def test_construir_vacio_lanza_error(self):
        pytest.importorskip("faiss")
        from core.busqueda_semantica import IndiceSemantico
        embs = np.zeros((0, 384), dtype=np.float32)
        with pytest.raises(ValueError):
            IndiceSemantico(384).construir(embs, [])

    def test_guardar_cargar(self, tmp_path, indice_con_datos):
        import tempfile
        indice, embs, ids = indice_con_datos
        # FAISS C++ writer fails on Windows paths with non-ASCII characters.
        # Use a guaranteed ASCII temp dir to avoid this Windows limitation.
        base_tmp = str(tmp_path)
        try:
            base_tmp.encode("ascii")
            ascii_tmp = base_tmp
        except UnicodeEncodeError:
            # Fall back to Windows system temp which is always ASCII
            sysroot = os.environ.get("SYSTEMROOT", "C:/Windows")
            ascii_tmp = tempfile.mkdtemp(dir=sysroot + "/Temp")
        ruta = os.path.join(ascii_tmp, "indice_test")
        indice.guardar(ruta)
        assert os.path.exists(ruta + ".faiss")
        assert os.path.exists(ruta + ".ids.json")
        indice2 = __import__("core.busqueda_semantica", fromlist=["IndiceSemantico"]).IndiceSemantico(384)
        ok = indice2.cargar(ruta)
        assert ok
        assert indice2.n_articulos == indice.n_articulos
        r1 = indice.buscar(embs[0], k=1)[0]["articulo_id"]
        r2 = indice2.buscar(embs[0], k=1)[0]["articulo_id"]
        assert r1 == r2

    def test_cargar_inexistente(self, tmp_path):
        from core.busqueda_semantica import IndiceSemantico
        indice = IndiceSemantico()
        ok = indice.cargar(str(tmp_path / "no_existe"))
        assert ok is False
        assert not indice.construido


class TestSimilitudCoseno:
    def test_identicos(self):
        from core.embeddings_local import similitud_coseno
        v = np.array([1.0, 0.0, 0.0])
        assert abs(similitud_coseno(v, v) - 1.0) < 1e-6

    def test_ortogonales(self):
        from core.embeddings_local import similitud_coseno
        v1 = np.array([1.0, 0.0])
        v2 = np.array([0.0, 1.0])
        assert abs(similitud_coseno(v1, v2)) < 1e-6

    def test_opuestos(self):
        from core.embeddings_local import similitud_coseno
        v1 = np.array([1.0, 0.0])
        v2 = np.array([-1.0, 0.0])
        assert abs(similitud_coseno(v1, v2) + 1.0) < 1e-6

    def test_vector_cero(self):
        from core.embeddings_local import similitud_coseno
        v_cero = np.array([0.0, 0.0, 0.0])
        v_normal = np.array([1.0, 0.0, 0.0])
        assert similitud_coseno(v_cero, v_normal) == 0.0


@pytest.mark.skipif(not faiss_y_st_disponibles(),
                    reason="faiss o sentence-transformers no disponibles")
class TestEmbeddingsReales:
    def test_shape_correcto(self):
        from core.embeddings_local import generar_embeddings, DIMENSIONES
        textos = ["hola mundo", "adios mundo", "Colombia 1939"]
        embs = generar_embeddings(textos)
        assert embs.shape == (3, DIMENSIONES)

    def test_tipo_float32(self):
        from core.embeddings_local import generar_embeddings
        embs = generar_embeddings(["texto"])
        assert embs.dtype == np.float32

    def test_textos_similares_mayor_similitud(self):
        from core.embeddings_local import generar_embeddings, similitud_coseno
        textos = [
            "La educacion en las escuelas rurales de Colombia",
            "Las escuelas y la educacion rural colombiana",
            "La fotografia y el cine en los anos treinta",
        ]
        embs = generar_embeddings(textos)
        sim_educacion = similitud_coseno(embs[0], embs[1])
        sim_diferente = similitud_coseno(embs[0], embs[2])
        assert sim_educacion > sim_diferente, \
            f"Educacion-Educacion ({sim_educacion:.3f}) debe > Educacion-Foto ({sim_diferente:.3f})"
