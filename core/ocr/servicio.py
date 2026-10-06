"""core/ocr/servicio.py — OCR de una página, igual para la GUI, la CLI y la API.

Hasta la sesión 72 cada ruta del worker de la GUI (``paneles/ocr.py``)
repetía lo mismo a mano: llamar al motor, caer a Tesseract si fallaba,
escribir el ``.txt`` y armar la fila de procedencia. La API web no tenía OCR.
``ocr_pagina`` es esa secuencia una sola vez, para que el escritorio y la nube
produzcan exactamente los mismos archivos.

Archivos por página, junto a ``txt_path``:

- ``<pagina>.txt``            — el texto (como siempre).
- ``<pagina>.bloques.json``   — los bloques con bbox, si el motor dio geometría.
  Si no la dio, el archivo NO se escribe (y se borra uno viejo): un bloques.json
  de otra corrida no debe quedar pegado a un texto nuevo.
"""

from __future__ import annotations

import json
from pathlib import Path

from core.ocr.interfaces import Bloque, ResultadoOCR
from core.ocr.procedencia import fila_meta


def ruta_bloques(txt_path) -> Path:
    p = Path(txt_path)
    return p.with_name(p.stem + ".bloques.json")


def guardar_bloques(txt_path, resultado: ResultadoOCR) -> Path | None:
    destino = ruta_bloques(txt_path)
    if not resultado.bloques:
        destino.unlink(missing_ok=True)
        return None
    datos = {"motor": resultado.motor, "version": resultado.version,
             "bloques": [b.a_dict() for b in resultado.bloques]}
    destino.write_text(json.dumps(datos, ensure_ascii=False, indent=1), "utf-8")
    return destino


def cargar_bloques(txt_path) -> list[Bloque]:
    p = ruta_bloques(txt_path)
    if not p.exists():
        return []
    return [Bloque.de_dict(d) for d in json.loads(p.read_text("utf-8"))["bloques"]]


def ocr_pagina(motor, imagen, txt_path, numero: str, *, respaldo=None,
               reusar: bool = False, alias: str | None = None,
               log=lambda m: None) -> tuple[ResultadoOCR | None, dict]:
    """Reconoce ``imagen`` con ``motor`` y deja ``txt_path`` escrito.

    - ``respaldo``: otro motor si el primero lanza excepción. La fila dice
      quién produjo el texto y de quién fue respaldo.
    - ``reusar``: si ``txt_path`` existe, no se vuelve a reconocer (la
      confianza queda None: no se midió en esta corrida).
    - ``alias``: nombre del motor en ``ocr_metadatos.csv`` cuando difiere del
      del registro (la GUI anota ``vision_claude``, no ``vision_llm``).
    - Si fallan el motor y el respaldo, el texto queda vacío y la fila marcada
      para revisión: un fallo no se disfraza de página en blanco.

    Devuelve ``(resultado o None, fila_meta)``.
    """
    imagen, txt_path = Path(imagen), Path(txt_path)
    pagina = imagen.stem
    nombre = alias or motor.nombre
    if reusar and txt_path.exists():
        texto = txt_path.read_text("utf-8", errors="replace")
        return None, fila_meta(numero, pagina, txt_path, texto, motor=nombre,
                               version=motor.version(), confianza=None, reusado=True)
    try:
        r = motor.reconocer(imagen)
        respaldo_de = None
    except Exception as e:
        log(f"    ⚠ {motor.nombre} falló en {pagina}: {e}")
        if respaldo is None:
            txt_path.write_text("", "utf-8")
            ruta_bloques(txt_path).unlink(missing_ok=True)
            return None, fila_meta(numero, pagina, txt_path, "", motor="ninguno",
                                   respaldo_de=nombre, error=str(e)[:200])
        try:
            r = respaldo.reconocer(imagen)
            respaldo_de = nombre
            log(f"      → {respaldo.nombre} usado como respaldo")
        except Exception as e2:
            log(f"      → el respaldo {respaldo.nombre} también falló: {e2}")
            txt_path.write_text("", "utf-8")
            ruta_bloques(txt_path).unlink(missing_ok=True)
            return None, fila_meta(numero, pagina, txt_path, "", motor="ninguno",
                                   respaldo_de=nombre, error=str(e2)[:200])
    txt_path.write_text(r.texto, "utf-8")
    guardar_bloques(txt_path, r)
    fila = fila_meta(numero, pagina, txt_path, r.texto,
                     motor=nombre if r.motor == motor.nombre else r.motor, version=r.version,
                     confianza=r.confianza, respaldo_de=respaldo_de,
                     segundos=r.segundos, bloques=len(r.bloques))
    if any(b.revisar for b in r.bloques):
        fila["revision"] = True
    return r, fila


COLUMNAS_META = ["numero", "pagina", "txt_path", "palabras", "confianza", "revision"]
UMBRAL_CONFIANZA_REVISION = 60


def tabla_metadatos(filas: list[dict]):
    """``ocr_metadatos.csv`` como DataFrame, con las mismas reglas en GUI y API.

    ``revision`` = confianza medida < 60 O marca previa (respaldo, discrepancia
    entre motores, bloque dudoso): la marca previa no se pierde al recalcular.
    """
    import pandas as pd
    df = pd.DataFrame(filas)
    for c in COLUMNAS_META:
        if c not in df.columns:
            df[c] = None
    df["palabras"] = pd.to_numeric(df["palabras"], errors="coerce").fillna(0).astype(int)
    df["confianza"] = pd.to_numeric(df["confianza"], errors="coerce")
    previa = df["revision"].fillna(False).astype(bool)
    df["revision"] = df["confianza"].apply(
        lambda c: bool(pd.notna(c) and c < UMBRAL_CONFIANZA_REVISION)) | previa
    return df


def guardar_metadatos(filas: list[dict], out_dir) -> Path:
    destino = Path(out_dir) / "04_analisis"
    destino.mkdir(parents=True, exist_ok=True)
    ruta = destino / "ocr_metadatos.csv"
    tabla_metadatos(filas).to_csv(ruta, index=False)
    return ruta


EXTS_IMAGEN = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


def ocr_documento(origen, out_dir, enrutador, *, dpi: int = 300, log=lambda m: None,
                  progreso=lambda i, total: None) -> list[dict]:
    """OCR de un PDF (o de una carpeta de imágenes) con el enrutador.

    Escribe ``02_imagenes/<numero>/`` (solo PDF) y ``03_ocr/<numero>/``; el
    número es el nombre del archivo o de la carpeta. Devuelve las filas de
    metadatos (quien llama las junta y las guarda con ``guardar_metadatos``).
    """
    origen, out_dir = Path(origen), Path(out_dir)
    numero = origen.stem if origen.is_file() else origen.name
    nativos: list[str] = []
    if origen.is_file() and origen.suffix.lower() == ".pdf":
        from core.ocr_engine import pdf_a_imagenes
        imgs = pdf_a_imagenes(origen, out_dir / "02_imagenes" / numero, dpi)
        try:
            import fitz
            with fitz.open(str(origen)) as doc:
                nativos = [pg.get_text("text") for pg in doc]
        except Exception:
            nativos = []
    elif origen.is_dir():
        imgs = sorted(p for p in origen.iterdir() if p.suffix.lower() in EXTS_IMAGEN)
    elif origen.suffix.lower() in EXTS_IMAGEN:
        imgs = [origen]
    else:
        raise ValueError(f"no sé leer {origen.name}: se esperaba PDF, imagen o carpeta")
    txt_dir = out_dir / "03_ocr" / numero
    txt_dir.mkdir(parents=True, exist_ok=True)
    filas = []
    for i, img in enumerate(imgs):
        _r, fila = enrutador.procesar(img, txt_dir / (Path(img).stem + ".txt"), numero,
                                      texto_nativo=nativos[i] if i < len(nativos) else None)
        filas.append(fila)
        progreso(i + 1, len(imgs))
    log(f"  ✅ {numero}: {len(imgs)} pág, {sum(1 for f in filas if f.get('revision'))} "
        "para revisión")
    return filas
