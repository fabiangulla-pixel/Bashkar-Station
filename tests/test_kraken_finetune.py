"""
tests/test_kraken_finetune.py — Preparación del ground truth para afinar Kraken.

Lo que más importa verificar aquí no es el formato de salida sino los **filtros**:
un dataset de HTR contaminado no falla, entrena igual y produce un modelo peor
sin avisar. Los tres venenos que este módulo tiene que atajar son: páginas donde
nadie corrigió el OCR (enseñarían los errores que se quieren quitar), la misma
página contada cuatro veces bajo nombres distintos del número, y páginas sin
imagen que inflan el recuento de lo entrenable.
"""

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import kraken_finetune as kf  # noqa: E402


def _crear_db(ruta: Path, filas):
    con = sqlite3.connect(ruta)
    con.execute("""CREATE TABLE normalizaciones (
        numero TEXT, pagina TEXT, ocr_crudo TEXT, norm_usuario TEXT,
        norm_ia TEXT, ts_usuario TEXT, ts_ia TEXT)""")
    con.executemany(
        "INSERT INTO normalizaciones (numero,pagina,ocr_crudo,norm_usuario) "
        "VALUES (?,?,?,?)", filas)
    con.commit()
    con.close()
    return ruta


LARGO = "Texto corregido a mano de una página de Estampa. " * 10   # >200 chars


class TestRecolectarGroundTruth:

    def test_toma_las_paginas_corregidas(self, tmp_path):
        db = _crear_db(tmp_path / "p.db", [
            ("Estampa 17", "p0001", "txto crvdo", LARGO),
            ("Estampa 17", "p0002", "otro crvdo", LARGO + "más"),
        ])
        r = kf.recolectar_ground_truth(db)
        assert len(r.pares) == 2
        assert r.caracteres > 400

    def test_descarta_copias_sin_editar_del_ocr(self, tmp_path):
        """norm_usuario == ocr_crudo significa que nadie lo tocó.

        Es el caso mayoritario en la base real: la pantalla de normalización
        precarga el OCR y guarda aunque no se edite nada. Entrenar con eso le
        enseñaría al modelo justo los errores que se quieren corregir.
        """
        db = _crear_db(tmp_path / "p.db", [
            ("Estampa 17", "p0001", LARGO, LARGO),          # intacta
            ("Estampa 17", "p0002", "crvdo", LARGO),        # corregida
        ])
        r = kf.recolectar_ground_truth(db)
        assert [p.pagina for p in r.pares] == ["p0002"]

    def test_descarta_paginas_demasiado_cortas(self, tmp_path):
        db = _crear_db(tmp_path / "p.db", [
            ("Estampa 17", "p0001", "x", "cuatro palabras sueltas nada mas"),
            ("Estampa 17", "p0002", "x", LARGO),
        ])
        r = kf.recolectar_ground_truth(db)
        assert len(r.pares) == 1
        assert r.descartados_cortos == 1

    def test_ignora_vacias(self, tmp_path):
        db = _crear_db(tmp_path / "p.db", [
            ("Estampa 17", "p0001", "x", ""),
            ("Estampa 17", "p0002", "x", None),
            ("Estampa 17", "p0003", "x", LARGO),
        ])
        assert len(kf.recolectar_ground_truth(db).pares) == 1

    def test_base_sin_la_tabla_no_revienta(self, tmp_path):
        vacia = tmp_path / "v.db"
        sqlite3.connect(vacia).close()
        r = kf.recolectar_ground_truth(vacia)
        assert r.pares == []


class TestDeduplicacion:
    """El número real aparece con tres nombres distintos en la base."""

    VARIANTES = [
        "Estampa año 2-2(17)_18 de marzo de 1939",
        "Completo_Estampa año 2-2(17)_18 de marzo de 1939",
        "Completo_Estampa_año_2-217_18_de_marzo_de_1939",
    ]

    def test_la_misma_pagina_bajo_tres_nombres_cuenta_una_vez(self, tmp_path):
        db = _crear_db(tmp_path / "p.db",
                       [(n, "p0001", "crvdo", LARGO) for n in self.VARIANTES])
        r = kf.recolectar_ground_truth(db)
        assert len(r.pares) == 1
        assert r.duplicados_fusionados == 2

    def test_se_queda_con_la_transcripcion_mas_trabajada(self, tmp_path):
        """Corregir es sobre todo añadir lo que el OCR se comió."""
        corta, larga = LARGO, LARGO + " párrafo final que faltaba"
        db = _crear_db(tmp_path / "p.db", [
            (self.VARIANTES[0], "p0001", "crvdo", corta),
            (self.VARIANTES[1], "p0001", "crvdo", larga),
        ])
        r = kf.recolectar_ground_truth(db)
        assert r.pares[0].texto == larga

    def test_paginas_distintas_del_mismo_numero_no_se_fusionan(self, tmp_path):
        db = _crear_db(tmp_path / "p.db", [
            (self.VARIANTES[0], "p0001", "crvdo", LARGO),
            (self.VARIANTES[0], "p0002", "crvdo", LARGO),
        ])
        assert len(kf.recolectar_ground_truth(db).pares) == 2

    @pytest.mark.parametrize("a,b", [
        ("Estampa año 2-2(17)", "Completo_Estampa año 2-2(17)"),
        ("Estampa año 2-2(17)", "Estampa_ano_2-217"),
        ("ESTAMPA AÑO 2", "estampa año 2"),
    ])
    def test_normalizacion_de_nombres_equivalentes(self, a, b):
        assert kf._normalizar_numero(a) == kf._normalizar_numero(b)

    def test_numeros_realmente_distintos_no_colisionan(self):
        assert (kf._normalizar_numero("Estampa año 2-2(17)")
                != kf._normalizar_numero("Estampa año 2-3(18)"))


class TestGuardiaDeCalidad:
    """El filtro que impide entrenar contra OCR reformateado.

    Caso real que lo motivó (Proyecto_04_Mar_2026.db, medido el 2026-08-10): las
    47 páginas del número de marzo pasaban el filtro ingenuo de «difiere del
    crudo» porque la pantalla de normalización desenvuelve los renglones al
    guardar. El cambio real fuera del espaciado era del 0,035 % — el OCR de la
    BNC intacto, con «Rila» donde la página impresa dice «Rifa». Entrenar contra
    eso le enseña al modelo los errores del OCR de origen.
    """

    OCR = ("Primera Gran Rila Anual de ESTAMPA\n"
           "60 Premios 20 DE JULIO DE 1939\n"
           "1er. Premio Automovil Opel Kadet, de la Casa Leonidas Lara e Hi-\n"
           "jos. Valor $ 1.480.00. Segundo premio radio R. C. A. de la Casa\n") * 3

    def test_desenvolver_renglones_no_es_transcribir(self):
        reformateado = self.OCR.replace("-\n", "").replace("\n", " ")
        assert kf._solo_reformateo(self.OCR, reformateado) is True

    def test_corregir_un_caracter_si_cuenta_como_edicion(self):
        corregido = self.OCR.replace("Rila", "Rifa")
        assert kf._solo_reformateo(self.OCR, corregido) is False

    def test_porcentaje_ignora_el_espaciado(self):
        reformateado = self.OCR.replace("-\n", "").replace("\n", " ")
        assert kf.porcentaje_corregido(self.OCR, reformateado) == 0.0

    def test_una_correccion_minuscula_no_alcanza_el_umbral(self):
        """Tres letras en 400 caracteres es ruido, no una transcripción."""
        casi_igual = self.OCR.replace("Rila", "Rifa", 1)
        assert 0 < kf.porcentaje_corregido(self.OCR, casi_igual) < kf.CORRECCION_MINIMA_PCT

    def test_una_transcripcion_real_supera_el_umbral(self):
        real = (self.OCR.replace("Rila", "Rifa").replace("Automovil", "Automóvil")
                .replace("Kadet", "Kadett").replace("Hi-\njos", "Hijos")
                .replace("radio", "radio de alcoba").replace("60 Premios", "60 premios"))
        assert kf.porcentaje_corregido(self.OCR, real) >= kf.CORRECCION_MINIMA_PCT

    def test_recolectar_descarta_el_reformateo(self, tmp_path):
        reformateado = self.OCR.replace("-\n", "").replace("\n", " ")
        db = _crear_db(tmp_path / "p.db", [("Estampa 17", "p0002", self.OCR, reformateado)])
        r = kf.recolectar_ground_truth(db)
        assert r.pares == []
        assert r.descartados_solo_reformateo == 1

    def test_recolectar_descarta_la_correccion_trivial(self, tmp_path):
        casi = self.OCR.replace("Rila", "Rifa", 1).replace("\n", " ")
        db = _crear_db(tmp_path / "p.db", [("Estampa 17", "p0002", self.OCR, casi)])
        r = kf.recolectar_ground_truth(db)
        assert r.pares == []
        assert r.descartados_correccion_trivial == 1

    def test_el_diagnostico_explica_el_descarte(self, tmp_path):
        """No basta con descartar: hay que decir por qué, o parece que no hay datos."""
        reformateado = self.OCR.replace("-\n", "").replace("\n", " ")
        db = _crear_db(tmp_path / "p.db",
                       [("Estampa 17", f"p{i:04d}", self.OCR, reformateado)
                        for i in range(30)])
        d = kf.diagnostico(db, [tmp_path / "x"], dir_modelos=tmp_path)

        assert d["se_puede_entrenar"] is False
        assert d["descartadas_por_calidad"] == 30
        assert any("estandar_oro" in f for f in d["faltantes"])


class TestEmparejarConImagenes:

    def test_separa_las_que_tienen_imagen_de_las_que_no(self, tmp_path):
        imgs = tmp_path / "img"
        imgs.mkdir()
        (imgs / "p0001.png").write_bytes(b"\x89PNG")

        db = _crear_db(tmp_path / "p.db", [
            ("Estampa 17", "p0001", "crvdo", LARGO),
            ("Estampa 17", "p0002", "crvdo", LARGO),
        ])
        r = kf.emparejar_con_imagenes(kf.recolectar_ground_truth(db), [imgs])

        assert [p.pagina for p in r.pares] == ["p0001"]
        assert [p.pagina for p in r.sin_imagen] == ["p0002"]

    def test_busca_en_subdirectorios_y_varios_formatos(self, tmp_path):
        imgs = tmp_path / "img" / "numero_x"
        imgs.mkdir(parents=True)
        (imgs / "p0001.jpg").write_bytes(b"x")
        (imgs / "p0002.tif").write_bytes(b"x")

        db = _crear_db(tmp_path / "p.db", [
            ("Estampa 17", "p0001", "crvdo", LARGO),
            ("Estampa 17", "p0002", "crvdo", LARGO),
        ])
        r = kf.emparejar_con_imagenes(kf.recolectar_ground_truth(db),
                                      [tmp_path / "img"])
        assert len(r.pares) == 2

    def test_directorio_inexistente_no_revienta(self, tmp_path):
        db = _crear_db(tmp_path / "p.db", [("E", "p0001", "c", LARGO)])
        r = kf.emparejar_con_imagenes(kf.recolectar_ground_truth(db),
                                      [tmp_path / "no_existe"])
        assert len(r.sin_imagen) == 1


class TestExportarDataset:

    def test_escribe_imagen_y_gt_txt_por_pagina(self, tmp_path):
        imgs = tmp_path / "img"
        imgs.mkdir()
        (imgs / "p0001.png").write_bytes(b"\x89PNG")
        db = _crear_db(tmp_path / "p.db", [("Estampa 17", "p0001", "crvdo", LARGO)])

        r = kf.emparejar_con_imagenes(kf.recolectar_ground_truth(db), [imgs])
        r = kf.exportar_dataset(r, tmp_path / "dataset")

        pngs = list((tmp_path / "dataset").glob("*.png"))
        gts = list((tmp_path / "dataset").glob("*.gt.txt"))
        assert len(pngs) == 1 and len(gts) == 1
        assert gts[0].read_text(encoding="utf-8") == LARGO.strip()


class TestPlanKetos:

    def test_devuelve_las_cuatro_etapas_en_orden(self, tmp_path):
        plan = kf.plan_ketos(tmp_path / "ds", tmp_path / "base.mlmodel",
                             tmp_path / "afinado")
        assert [p["etapa"] for p in plan] == [
            "segmentar", "alinear", "entrenar", "medir"]

    def test_entrena_partiendo_del_modelo_base(self, tmp_path):
        """Sin -i entrenaría desde cero, y con 5 000 líneas saldría peor."""
        plan = kf.plan_ketos(tmp_path / "ds", tmp_path / "base.mlmodel",
                             tmp_path / "afinado")
        entrenar = next(p for p in plan if p["etapa"] == "entrenar")
        assert "-i" in entrenar["comando"]
        assert "base.mlmodel" in " ".join(entrenar["comando"])

    def test_conserva_el_alfabeto_del_modelo_base(self, tmp_path):
        """--resize union: añade caracteres nuevos sin perder los aprendidos."""
        plan = kf.plan_ketos(tmp_path / "ds", tmp_path / "b.mlmodel",
                             tmp_path / "a")
        entrenar = next(p for p in plan if p["etapa"] == "entrenar")
        cmd = entrenar["comando"]
        assert cmd[cmd.index("--resize") + 1] == "union"

    def test_cada_etapa_explica_por_que_existe(self, tmp_path):
        """El plan se archiva en la bitácora: sin el porqué no es reproducible."""
        for paso in kf.plan_ketos(tmp_path / "d", tmp_path / "b", tmp_path / "a"):
            assert len(paso["por_que"]) > 40


class TestDiagnostico:

    def test_dice_que_falta_cuando_no_hay_imagenes(self, tmp_path):
        db = _crear_db(tmp_path / "p.db",
                       [("Estampa 17", f"p{i:04d}", "crvdo", LARGO)
                        for i in range(30)])
        d = kf.diagnostico(db, [tmp_path / "vacio"], dir_modelos=tmp_path)

        assert d["se_puede_entrenar"] is False
        assert d["paginas_entrenables"] == 0
        assert d["paginas_sin_imagen"] == 30
        assert any("rerenderizar" in f for f in d["faltantes"])

    def test_avisa_si_falta_ground_truth(self, tmp_path):
        imgs = tmp_path / "img"; imgs.mkdir()
        (imgs / "p0001.png").write_bytes(b"x")
        db = _crear_db(tmp_path / "p.db", [("E", "p0001", "crvdo", LARGO)])

        d = kf.diagnostico(db, [imgs], dir_modelos=tmp_path)
        assert d["se_puede_entrenar"] is False
        assert any("round truth" in f for f in d["faltantes"])

    def test_estima_las_lineas_del_corpus(self, tmp_path):
        """El número que decide si vale la pena entrenar."""
        db = _crear_db(tmp_path / "p.db",
                       [("E", f"p{i:04d}", "crvdo", LARGO) for i in range(10)])
        d = kf.diagnostico(db, [tmp_path / "x"], dir_modelos=tmp_path)
        assert d["lineas_estimadas"] == d["caracteres"] // 45

    def test_reporta_la_ausencia_de_ketos(self, tmp_path):
        db = _crear_db(tmp_path / "p.db", [("E", "p0001", "c", LARGO)])
        d = kf.diagnostico(db, [tmp_path], dir_modelos=tmp_path)
        if not d["ketos_disponible"]:
            assert any("Kraken" in f for f in d["faltantes"])
