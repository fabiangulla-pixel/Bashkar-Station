"""tests/test_importar_vision_ocr.py — importar_vision_ocr_a_proyecto.py."""
import importlib.util
import json
import sys
from pathlib import Path

pytest_plugins = []

_SCRIPT_PATH = (Path(__file__).resolve().parents[1] / "scripts"
                / "importar_vision_ocr_a_proyecto.py")
_spec = importlib.util.spec_from_file_location("importar_vision_ocr", _SCRIPT_PATH)
importador = importlib.util.module_from_spec(_spec)
sys.modules["importar_vision_ocr"] = importador
_spec.loader.exec_module(importador)


class TestCopiarOcr:
    def test_copia_txt_a_estructura_03_ocr(self, tmp_path):
        salida_vision = tmp_path / "vision_ocr_salida"
        numero = importador.NUMEROS[0]
        (salida_vision / numero).mkdir(parents=True)
        (salida_vision / numero / "p0001.txt").write_text("texto uno", encoding="utf-8")
        (salida_vision / numero / "p0002.txt").write_text("texto dos", encoding="utf-8")

        datos_dir = tmp_path / "proyecto"
        resumen = importador._copiar_ocr(salida_vision, datos_dir, forzar=False)

        assert resumen[numero] == 2
        copiado = datos_dir / "03_ocr" / numero / "p0001.txt"
        assert copiado.read_text(encoding="utf-8") == "texto uno"

    def test_numero_sin_carpeta_da_cero(self, tmp_path):
        salida_vision = tmp_path / "vacio"
        salida_vision.mkdir()
        datos_dir = tmp_path / "proyecto"
        resumen = importador._copiar_ocr(salida_vision, datos_dir, forzar=False)
        assert all(n == 0 for n in resumen.values())

    def test_no_forzar_no_sobrescribe(self, tmp_path):
        salida_vision = tmp_path / "vision_ocr_salida"
        numero = importador.NUMEROS[0]
        (salida_vision / numero).mkdir(parents=True)
        (salida_vision / numero / "p0001.txt").write_text("version nueva", encoding="utf-8")

        datos_dir = tmp_path / "proyecto"
        destino = datos_dir / "03_ocr" / numero
        destino.mkdir(parents=True)
        (destino / "p0001.txt").write_text("version vieja", encoding="utf-8")

        resumen = importador._copiar_ocr(salida_vision, datos_dir, forzar=False)

        assert resumen[numero] == 0
        assert (destino / "p0001.txt").read_text(encoding="utf-8") == "version vieja"

    def test_forzar_si_sobrescribe(self, tmp_path):
        salida_vision = tmp_path / "vision_ocr_salida"
        numero = importador.NUMEROS[0]
        (salida_vision / numero).mkdir(parents=True)
        (salida_vision / numero / "p0001.txt").write_text("version nueva", encoding="utf-8")

        datos_dir = tmp_path / "proyecto"
        destino = datos_dir / "03_ocr" / numero
        destino.mkdir(parents=True)
        (destino / "p0001.txt").write_text("version vieja", encoding="utf-8")

        resumen = importador._copiar_ocr(salida_vision, datos_dir, forzar=True)

        assert resumen[numero] == 1
        assert (destino / "p0001.txt").read_text(encoding="utf-8") == "version nueva"


class TestEscribirBashkar:
    def test_bashkar_es_json_valido_con_esquema_esperado(self, tmp_path):
        datos_dir = tmp_path / "datos"
        ruta = tmp_path / "proyecto.bashkar"

        importador.escribir_bashkar(ruta, datos_dir, "Mi proyecto")

        datos = json.loads(ruta.read_text(encoding="utf-8"))
        assert datos["version"] == "11"
        assert datos["nombre"] == "Mi proyecto"
        assert datos["config"]["out_dir"] == str(datos_dir)
        assert datos["config"]["input_tipo"] == "pdf"
        assert datos["progreso"]["ocr"] is True
        assert datos["progreso"]["seg"] is False
        assert "resultados" in datos
        assert "historial_ia" in datos

    def test_bashkar_cargable_por_project_manager(self, tmp_path, monkeypatch):
        """El .bashkar que escribimos debe poder cargarse de verdad con
        core.project_manager.cargar_proyecto -- no solo parecer válido."""
        datos_dir = tmp_path / "datos"
        ruta = tmp_path / "proyecto.bashkar"
        importador.escribir_bashkar(ruta, datos_dir, "Mi proyecto")

        from core.project_manager import cargar_proyecto

        class _EstadoFalso:
            pass

        st = _EstadoFalso()
        resultado = cargar_proyecto(ruta, st)

        assert resultado["ok"] is not False
        assert st.publicacion == "Estampa"
        assert st.ocr_done is True
        assert st.seg_done is False
        assert str(st.out_dir) == str(datos_dir)
