"""tests/test_cli.py — regresión de la etapa de segmentación del CLI."""

from pathlib import Path

from cli import _etapa_seg


def test_etapa_seg_segmenta_sin_typeerror(tmp_path: Path):
    """segmentar_numero() exige (ocr_dir, nombre); una llamada con un solo
    argumento posicional revienta con TypeError, silenciada por el except
    genérico de _etapa_seg (0 artículos sin ningún aviso claro). Ver s.59/60
    de [[project_bashkar_station]]."""
    out_dir = tmp_path / "salida"
    num_dir = out_dir / "03_ocr" / "rev_estampa_ene_1939"
    num_dir.mkdir(parents=True)
    texto = ("Un artículo de prueba con suficientes palabras para superar "
              "el umbral mínimo de quince palabras que exige el segmentador "
              "antes de descartar la página como vacía.")
    (num_dir / "p0001.txt").write_text(texto, encoding="utf-8")

    articulos = _etapa_seg({"out_dir": str(out_dir)}, verbose=False)

    assert articulos, "la segmentación debería producir al menos un artículo"
    assert (out_dir / "segmentacion.csv").exists()
