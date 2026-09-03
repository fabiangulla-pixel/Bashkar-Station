"""tests/test_sentimiento_discriminante.py — Regresión del léxico de polaridad.

Auditoría de sesión (frente 1, 2026-09-02): core/sentimiento_discriminante.py
usa coincidencia EXACTA de palabra tokenizada contra un set de léxico
(``p in _NEG`` / ``p in _POS``, línea ~136-137 de la versión auditada), no
coincidencia por prefijo/stem. Varias entradas del léxico eran raíces
truncadas ("trágic", "sangrient", "violent", "muert") que NUNCA calzan con
ninguna palabra real del español (siempre llevan terminación: trágico,
sangriento, violento, muerto) — bug real de cobertura, no un defecto de
diseño intencional: esas entradas eran ruido muerto en el set. Verificado
contra corpus.xml real de Estampa 1939 (texto sobre la Segunda Guerra
Mundial con "trágico"/"violento" en contexto). Se agregaron las formas
flexionadas más comunes (o/a/os/as) para las raíces afectadas.
"""
from core.sentimiento_discriminante import analizar_polaridad, _POS, _NEG


class TestFormasFlexionadasFaltantes:
    """Antes de la corrección, estas palabras exactas no calzaban con ningún
    elemento del set pese a que su raíz truncada sí estaba en el léxico."""

    def test_tragico_y_variantes_en_negativo(self):
        for w in ("trágico", "trágica", "trágicos", "trágicas"):
            assert w in _NEG, f"'{w}' debería estar en el léxico negativo"

    def test_violento_y_variantes_en_negativo(self):
        for w in ("violento", "violenta", "violentos", "violentas"):
            assert w in _NEG, f"'{w}' debería estar en el léxico negativo"

    def test_sangriento_y_variantes_en_negativo(self):
        for w in ("sangriento", "sangrienta"):
            assert w in _NEG

    def test_muerto_en_negativo(self):
        assert "muerto" in _NEG
        assert "muertos" in _NEG

    def test_magnifica_en_positivo(self):
        assert "magnifica" in _POS


class TestAnalizarPolaridadConTextoReal:
    """analizar_polaridad debe detectar polaridad negativa en una frase real
    de prensa histórica sobre la guerra (patrón del corpus Estampa 1939)."""

    def test_frase_con_palabras_antes_invisibles_al_lexico(self):
        texto = "El violento ataque dejó un saldo trágico de soldados muertos."
        r = analizar_polaridad(texto)
        assert r["polaridad"] == "negativo"
        assert r["n_neg"] >= 3  # violento, ataque, trágico (muertos no exacto: "muertos" sí está)

    def test_texto_vacio_no_lanza(self):
        r = analizar_polaridad("")
        assert r["polaridad"] == "neutro"
