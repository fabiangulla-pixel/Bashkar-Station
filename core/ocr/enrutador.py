"""core/ocr/enrutador.py — Decide, página por página, cómo leerla.

1. Si la página trae texto embebido y ``calidad_ocr`` lo da por utilizable,
   se usa tal cual: no se OCR-iza lo que ya se puede leer.
2. Si no, el motor primario (el primero disponible de ``primarios``).
3. Si el resultado es dudoso (confianza medida baja o calidad dudosa), una
   segunda opinión con otro motor. Se comparan (``desacuerdo``) y, si
   discrepan más del umbral, la página y los bloques en disputa quedan
   marcados para revisión con las dos lecturas guardadas. El enrutador NO
   decide cuál de los dos tiene razón.

La política vive en ``config/ocr.toml``, no en el código. Cada decisión queda
en la fila de procedencia (``ruta``, ``segunda_opinion``, ``discrepancia``).
"""

from __future__ import annotations

import copy
import tomllib
from pathlib import Path

from core.ocr.interfaces import ResultadoOCR

RUTA_POLITICA = Path(__file__).resolve().parents[2] / "config" / "ocr.toml"

POLITICA_POR_DEFECTO = {
    "enrutador": {"primarios": ["surya", "zonas", "tesseract"],
                  "segundos": ["churro", "zonas", "tesseract"],
                  "respaldo": "tesseract", "usar_texto_nativo": True},
    "segunda_opinion": {"confianza_min": 80.0, "si_calidad_dudosa": True, "siempre": False},
    "revision": {"discrepancia_pagina": 0.15, "discrepancia_bloque": 0.15},
}


def cargar_politica(ruta: Path | None = None) -> dict:
    """La política por defecto, con lo que diga ``config/ocr.toml`` encima."""
    politica = copy.deepcopy(POLITICA_POR_DEFECTO)
    ruta = Path(ruta) if ruta else RUTA_POLITICA
    if ruta.exists():
        with open(ruta, "rb") as f:
            leida = tomllib.load(f)
        for seccion, valores in leida.items():
            politica.setdefault(seccion, {}).update(valores)
    return politica


def necesita_segunda_opinion(r: ResultadoOCR, politica: dict) -> tuple[bool, str]:
    so = politica["segunda_opinion"]
    if so.get("siempre"):
        return True, "política: siempre"
    if r.confianza is not None and r.confianza < so["confianza_min"]:
        return True, f"confianza {r.confianza:.0f} < {so['confianza_min']:.0f}"
    if so.get("si_calidad_dudosa"):
        from core.calidad_ocr import evaluar_texto
        v = evaluar_texto(r.texto, min_tokens=50)
        if v.se_abstiene:
            return True, f"calidad: {v.veredicto}"
    if any(b.revisar for b in r.bloques):
        return True, "el motor marcó bloques con error"
    return False, ""


class Enrutador:
    """Uso:

        with Enrutador(opciones={"tesseract": {"lang": "spa"}}) as enr:
            r, fila = enr.procesar(imagen, txt_path, "E1939-03")
    """

    def __init__(self, politica: dict | None = None, opciones: dict | None = None,
                 log=lambda m: None, crear=None):
        from core.ocr import crear as crear_registro
        self.politica = politica or cargar_politica()
        self.opciones = opciones or {}
        self.log = log
        self._crear = crear or crear_registro
        self._motores: dict = {}
        self._disponible: dict[str, bool] = {}

    # ── motores ──────────────────────────────────────────────────────────────
    def _motor(self, nombre: str):
        if nombre not in self._motores:
            self._motores[nombre] = self._crear(nombre, **self.opciones.get(nombre, {}))
        return self._motores[nombre]

    def disponible(self, nombre: str) -> bool:
        if nombre not in self._disponible:
            try:
                motivo = self._motor(nombre).motivo_no_disponible()
            except Exception as e:
                motivo = str(e)
            self._disponible[nombre] = motivo is None
            if motivo:
                self.log(f"  · {nombre} no disponible: {motivo}")
        return self._disponible[nombre]

    def primario(self) -> str:
        for n in self.politica["enrutador"]["primarios"]:
            if self.disponible(n):
                return n
        raise RuntimeError("ningún motor primario de OCR está disponible")

    def segundo(self, excepto: str) -> str | None:
        for n in self.politica["enrutador"]["segundos"]:
            if n != excepto and self.disponible(n):
                return n
        return None

    def plan(self) -> dict:
        """Qué haría con una página escaneada, sin leer nada (para la API/GUI)."""
        p = self.primario()
        return {"primario": p, "segunda_opinion": self.segundo(p),
                "respaldo": self.politica["enrutador"].get("respaldo"),
                "politica": self.politica}

    # ── una página ───────────────────────────────────────────────────────────
    def procesar(self, imagen, txt_path, numero: str, *, texto_nativo: str | None = None):
        """Lee una página y deja ``txt_path`` (y ``.bloques.json``) escritos.

        Devuelve ``(ResultadoOCR | None, fila_meta)``.
        """
        from core.ocr.procedencia import fila_meta
        from core.ocr.servicio import guardar_bloques, ocr_pagina

        imagen, txt_path = Path(imagen), Path(txt_path)
        if texto_nativo is not None and self.politica["enrutador"].get("usar_texto_nativo"):
            from core.calidad_ocr import evaluar_texto
            v = evaluar_texto(texto_nativo, min_tokens=20)
            if not v.se_abstiene:
                txt_path.write_text(texto_nativo, "utf-8")
                from core.ocr.servicio import ruta_bloques
                ruta_bloques(txt_path).unlink(missing_ok=True)
                fila = fila_meta(numero, imagen.stem, txt_path, texto_nativo, motor="nativo",
                                 version="texto embebido del PDF")
                fila["ruta"] = "nativo"
                return None, fila
            self.log(f"    {imagen.stem}: texto embebido descartado ({v.veredicto})")

        nombre_p = self.primario()
        respaldo = self.politica["enrutador"].get("respaldo")
        motor_resp = (self._motor(respaldo)
                      if respaldo and respaldo != nombre_p and self.disponible(respaldo) else None)
        r, fila = ocr_pagina(self._motor(nombre_p), imagen, txt_path, numero,
                             respaldo=motor_resp, log=self.log)
        fila["ruta"] = nombre_p
        if r is None:
            return r, fila

        hace_falta, motivo = necesita_segunda_opinion(r, self.politica)
        nombre_s = self.segundo(r.motor) if hace_falta else None
        if not nombre_s:
            return r, fila

        self.log(f"    {imagen.stem}: segunda opinión con {nombre_s} ({motivo})")
        try:
            r2 = self._motor(nombre_s).reconocer(imagen)
        except Exception as e:
            self.log(f"    ⚠ segunda opinión {nombre_s} falló: {e}")
            fila["segunda_opinion"] = f"{nombre_s} (falló)"
            return r, fila

        from core.ocr.desacuerdo import comparar
        rev = self.politica["revision"]
        c = comparar(r, r2, umbral_bloque=rev["discrepancia_bloque"])
        guardar_bloques(txt_path, r)           # con alternativas y marcas
        # En JSON, no en .txt: 03_ocr/**/*.txt ES el corpus para varios módulos,
        # y un .txt de más duplicaría la página en NER y frecuencias.
        import json
        txt_path.with_name(txt_path.stem + ".alternativas.json").write_text(json.dumps(
            {"principal": r.motor, "alternativas": [
                {"motor": r2.motor, "version": r2.version, "texto": r2.texto,
                 "confianza": r2.confianza, **c.a_dict()}]},
            ensure_ascii=False, indent=1), "utf-8")
        fila.update(segunda_opinion=nombre_s, motivo_segunda=motivo,
                    discrepancia=round(c.caracteres, 4), bloques_en_duda=c.bloques_en_duda)
        if c.caracteres > rev["discrepancia_pagina"] or c.bloques_en_duda:
            fila["revision"] = True
        return r, fila

    # ── recursos ─────────────────────────────────────────────────────────────
    def liberar(self):
        for m in self._motores.values():
            try:
                m.liberar()
            except Exception:
                pass
        self._motores.clear()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.liberar()
