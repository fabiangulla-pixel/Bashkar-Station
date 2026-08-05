"""core/estandar_oro.py — Preparar y recolectar el estándar de oro de transcripción.

Sin una transcripción de referencia hecha a mano no hay CER absoluto: solo se
puede comparar unas rutas de OCR con otras, que es lo que hicieron las primeras
mediciones de la sesión 50. Este módulo cubre ese hueco con el mínimo trabajo
manual posible.

**Por qué por zonas y no por páginas.** Transcribir una página entera de prensa
ilustrada es desalentador: columnas, pies de foto, publicidad, todo mezclado.
En cambio, el investigador ya etiquetó la tipología de cada zona, así que aquí
se exporta **un recorte por zona con texto** y un `.txt` vacío al lado. Son
bloques cortos y homogéneos: se transcriben de a poco, se puede parar y seguir,
y el avance es medible.

**Sobre prellenar con el OCR automático.** `prellenar` permite volcar la salida
de un motor en el `.txt` para corregirla en vez de escribir desde cero. Ahorra
muchísimo tiempo y es práctica habitual en la creación de *ground truth* de HTR,
pero **sesga**: quien corrige tiende a dar por buenos los errores que no salta a
la vista. Si el estándar se va a usar para comparar ese mismo motor, prellenar
con él invalida la comparación. Por eso está desactivado por defecto y, cuando
se usa, queda anotado en el manifiesto.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

__all__ = [
    "exportar_zonas",
    "recolectar",
    "estado",
    "ZonaExportada",
    "MANIFIESTO",
    "INSTRUCCIONES",
]

MANIFIESTO = "manifiesto.json"
MARGEN_PX = 6

INSTRUCCIONES = """\
# Estándar de oro — cómo transcribir

En esta carpeta hay un recorte `.png` por cada zona con texto y, al lado, un
archivo `.txt` con el mismo nombre. **Escribe en el `.txt` lo que dice el
recorte**, y nada más.

## Reglas

1. **Transcribe lo que ves, no lo que debería decir.** Si el original dice
   «Kadet» con una sola t, se escribe «Kadet». El estándar de oro mide al OCR,
   no corrige a la revista.
2. **Conserva la ortografía de la época** y las tildes tal como aparecen. Si una
   palabra va sin tilde en el original, va sin tilde aquí.
3. **Los saltos de línea del original se conservan.** Si una palabra queda
   partida al final de una línea con guion, escríbela partida igual: la métrica
   ya sabe reunirla.
4. **No añadas** encabezados, comentarios ni numeración que no estén en el
   recorte.
5. Si una zona está ilegible o vacía, **deja el `.txt` vacío**. Cuenta como tal.

## Cómo saber cuánto llevas

Desde el panel «⚖️ Benchmark OCR» de Bashkar Station, el botón de estado dice
cuántas zonas están transcritas y cuántas faltan.

## Cuando termines

Vuelve al panel de Benchmark e indica esta carpeta como estándar de oro. Las
métricas (CER, WER, similitud) se calculan contra lo que escribiste aquí.
"""


@dataclass
class ZonaExportada:
    """Una zona lista para transcribir."""

    numero: str
    pagina: str
    orden: int
    tipo: str
    zid: str
    imagen: str        # nombre del .png
    texto: str         # nombre del .txt

    def como_dict(self) -> dict:
        return {
            "numero": self.numero, "pagina": self.pagina, "orden": self.orden,
            "tipo": self.tipo, "zid": self.zid,
            "imagen": self.imagen, "texto": self.texto,
        }


def _nombre_base(pagina: str, orden: int, tipo: str) -> str:
    """Nombre estable y ordenable: la página, el orden de lectura y el tipo."""
    return f"{pagina}_z{orden:02d}_{tipo}"


def exportar_zonas(out_dir, numero: str, paginas: list[str], destino,
                   prellenar: dict[str, str] | None = None,
                   callback=None) -> list[ZonaExportada]:
    """Exporta un recorte y un .txt por cada zona con texto de las páginas dadas.

    `out_dir` es la carpeta de trabajo del proyecto (donde viven `02_imagenes/`
    y `05_etiquetas/`). `prellenar` es opcional: `{nombre_base: texto}` para
    volcar una transcripción previa — leer la advertencia del encabezado del
    módulo antes de usarlo.

    Las zonas sin texto (fotografía, publicidad, filete…) se omiten: son
    justamente las que no hay que transcribir.
    """
    from PIL import Image

    from core.zone_labeler import TIPOS_ZONA, calcular_orden_lectura, cargar_pagina

    out_dir, destino = Path(out_dir), Path(destino)
    destino.mkdir(parents=True, exist_ok=True)

    def log(m):
        if callback:
            callback(m)

    exportadas: list[ZonaExportada] = []
    for pagina in paginas:
        pag = cargar_pagina(out_dir, numero, pagina)
        if not pag or not pag.zonas:
            log(f"{pagina}: sin etiquetar, se omite")
            continue

        img_path = _buscar_imagen(out_dir, numero, pagina)
        if img_path is None:
            log(f"{pagina}: no se encontró la imagen, se omite")
            continue

        con_texto = [z for z in pag.zonas
                     if TIPOS_ZONA.get(z.tipo, {}).get("ocr", True)]
        if not con_texto:
            log(f"{pagina}: ninguna zona lleva texto")
            continue
        if all(getattr(z, "orden", 0) == 0 for z in con_texto):
            calcular_orden_lectura(pag.zonas)
        con_texto.sort(key=lambda z: (z.orden if z.orden > 0 else 9999, z.y0, z.x0))

        img = Image.open(img_path).convert("RGB")
        W, H = img.size
        for z in con_texto:
            x0, y0, x1, y1 = z.a_pixeles(W, H)
            x0 = max(0, x0 - MARGEN_PX); y0 = max(0, y0 - MARGEN_PX)
            x1 = min(W, x1 + MARGEN_PX); y1 = min(H, y1 + MARGEN_PX)
            if x1 - x0 < 8 or y1 - y0 < 8:
                continue

            base = _nombre_base(pagina, z.orden, z.tipo)
            img.crop((x0, y0, x1, y1)).save(destino / f"{base}.png")

            txt = destino / f"{base}.txt"
            if not txt.exists():          # nunca pisar trabajo ya hecho
                txt.write_text((prellenar or {}).get(base, ""), encoding="utf-8")

            exportadas.append(ZonaExportada(
                numero=numero, pagina=pagina, orden=z.orden, tipo=z.tipo,
                zid=getattr(z, "zid", ""),
                imagen=f"{base}.png", texto=f"{base}.txt"))
        log(f"{pagina}: {len(con_texto)} zona(s) exportada(s)")

    (destino / "INSTRUCCIONES.md").write_text(INSTRUCCIONES, encoding="utf-8")
    (destino / MANIFIESTO).write_text(json.dumps({
        "generado": datetime.now(UTC).isoformat(timespec="seconds"),
        "numero": numero,
        "paginas": paginas,
        "prellenado": bool(prellenar),
        "zonas": [z.como_dict() for z in exportadas],
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    log(f"Total: {len(exportadas)} zona(s) listas en {destino}")
    return exportadas


def _buscar_imagen(out_dir: Path, numero: str, pagina: str) -> Path | None:
    """Localiza la imagen de una página en `02_imagenes/<numero>/`."""
    carpeta = Path(out_dir) / "02_imagenes" / numero
    if not carpeta.is_dir():
        return None
    for ext in (".png", ".jpg", ".jpeg", ".tif", ".tiff"):
        exacta = carpeta / f"{pagina}{ext}"
        if exacta.exists():
            return exacta
    coincidencias = sorted(carpeta.glob(f"*{pagina}*"))
    return coincidencias[0] if coincidencias else None


def recolectar(carpeta, por_pagina: bool = False) -> dict[str, str]:
    """Lee los `.txt` transcritos y los devuelve listos para `benchmark_ocr`.

    Por defecto la clave es el nombre de la zona (`p0001-02_z03_articulo`), que
    es la unidad natural: cada ruta de OCR se evalúa zona a zona. Con
    `por_pagina=True` se concatenan en orden de lectura y la clave es la página,
    para comparar contra rutas que solo producen texto de página completa.

    Las zonas con `.txt` vacío se descartan: no se puede medir el error contra
    una referencia que no existe. Es distinto de una zona que el OCR no
    reconoció — eso sí cuenta como fallo.
    """
    carpeta = Path(carpeta)
    manifiesto = carpeta / MANIFIESTO
    if not manifiesto.exists():
        raise FileNotFoundError(
            f"No hay {MANIFIESTO} en {carpeta}. ¿Es una carpeta de estándar de oro?")

    datos = json.loads(manifiesto.read_text(encoding="utf-8"))
    zonas = sorted(datos.get("zonas", []),
                   key=lambda z: (z["pagina"], z["orden"]))

    resultado: dict[str, str] = {}
    for z in zonas:
        ruta = carpeta / z["texto"]
        texto = ruta.read_text(encoding="utf-8").strip() if ruta.exists() else ""
        if not texto:
            continue
        if por_pagina:
            resultado[z["pagina"]] = (resultado.get(z["pagina"], "")
                                      + ("\n\n" if z["pagina"] in resultado else "")
                                      + texto)
        else:
            resultado[Path(z["texto"]).stem] = texto
    return resultado


def estado(carpeta) -> dict:
    """Cuánto se lleva transcrito. Para mostrar avance sin abrir la carpeta."""
    carpeta = Path(carpeta)
    manifiesto = carpeta / MANIFIESTO
    if not manifiesto.exists():
        return {"total": 0, "hechas": 0, "pendientes": 0, "porcentaje": 0.0,
                "por_tipo": {}, "palabras": 0}

    datos = json.loads(manifiesto.read_text(encoding="utf-8"))
    zonas = datos.get("zonas", [])
    hechas, palabras = 0, 0
    por_tipo: dict[str, dict] = {}
    for z in zonas:
        ruta = carpeta / z["texto"]
        texto = ruta.read_text(encoding="utf-8").strip() if ruta.exists() else ""
        t = por_tipo.setdefault(z["tipo"], {"total": 0, "hechas": 0})
        t["total"] += 1
        if texto:
            hechas += 1
            palabras += len(texto.split())
            t["hechas"] += 1

    total = len(zonas)
    return {
        "total": total,
        "hechas": hechas,
        "pendientes": total - hechas,
        "porcentaje": round(100 * hechas / total, 1) if total else 0.0,
        "por_tipo": por_tipo,
        "palabras": palabras,
        "prellenado": datos.get("prellenado", False),
    }
