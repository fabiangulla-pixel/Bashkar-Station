"""
datos/migracion.py — Migrador de archivos .bashkar v10 → v11.

Convierte el formato JSON-puro de v10 a la nueva arquitectura:
  - JSON liviano (.bashkar)  → metadatos del proyecto
  - SQLite (.db)             → datos pesados (artículos, OCR, entidades)

Siempre hace backup antes de modificar.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path

from datos.repositorio import Repositorio

VERSION_NUEVA = "11"

# Valor canónico de "sin autor" que usa el segmentador actual
# (core/article_segmenter.py::_extraer_autor) y que el resto del código
# compara con `==` (p.ej. app.py al contar autores únicos). Los .bashkar v10
# reales vienen de un pipeline basado en pandas que dejaba en el campo
# "autor" basura de la conversión DataFrame → JSON en vez de vacío real:
# NaN se volvía el string literal "nan" (str(float('nan')) == "nan") y
# celdas vacías quedaban como "" o "None". Comparado sobre un .bashkar de
# marzo de 2026 con proyectos/Proyecto_04_Mar_2026.db (351 artículos): 179
# "Anónimo / Sin atribuir", 142 "nan", 28 "" — solo 179/349 se contaban bien
# como anónimos aguas abajo, el resto quedaba como "autor" fantasma no vacío
# y no comparaba igual a nada. Normalizar aquí, en la migración, es más
# seguro que tocar el criterio de "anónimo" en cada consumidor.
AUTOR_ANONIMO = "Anónimo / Sin atribuir"
_AUTOR_BASURA = {"", "nan", "none", "null", "na", "n/a", "-"}


def _normalizar_autor(valor) -> str:
    """Convierte basura de OCR/pandas del v10 (None, "", "nan", "None"...) al
    mismo valor canónico que usa el segmentador actual para "sin autor"."""
    if valor is None:
        return AUTOR_ANONIMO
    texto = str(valor).strip()
    if texto.lower() in _AUTOR_BASURA:
        return AUTOR_ANONIMO
    return texto


def _articulos_v10(ruta: Path, datos_v10: dict) -> list[dict]:
    """Artículos de un proyecto v10, buscándolos donde de verdad están.

    Los .bashkar v10 reales NO llevan una lista "articulos" en la raíz: el
    guardado de esa época ya escribía los DataFrames como CSV en la carpeta
    hermana ``<stem>/`` y solo dejaba en el JSON la lista de nombres en
    ``resultados.dataframes_guardados``. Leer la raíz sin más hacía que la
    migración fuese un no-op silencioso: sobre el proyecto real
    Proyecto_04_Mar_2026 (138 filas en articulos.csv, 138 textos en
    corpus_txt.json) registró "articulos_migrados: 0".
    """
    arts = datos_v10.get("articulos")
    if isinstance(arts, dict):
        arts = list(arts.values())
    if isinstance(arts, list) and arts:
        return [a for a in arts if isinstance(a, dict)]

    carpeta = Path(ruta).with_suffix("")
    csv_arts = carpeta / "articulos.csv"
    if not csv_arts.exists():
        return []

    import csv as _csv
    try:
        with open(csv_arts, encoding="utf-8") as f:
            filas = list(_csv.DictReader(f))
    except Exception:
        return []

    textos: list[str] = []
    corpus = carpeta / "corpus_txt.json"
    if corpus.exists():
        try:
            cargado = json.loads(corpus.read_text(encoding="utf-8"))
            if isinstance(cargado, list):
                textos = [str(t) for t in cargado]
        except Exception:
            textos = []

    salida = []
    for i, fila in enumerate(filas):
        art = {
            "id":         fila.get("id") or f"{fila.get('numero', 'art')}_{i:04d}",
            "numero":     fila.get("numero", ""),
            "titulo":     fila.get("titulo", ""),
            "autor":      fila.get("autor", ""),
            "tipo":       fila.get("tipo", "articulo"),
            "seccion":    fila.get("seccion", ""),
            "n_palabras": int(float(fila.get("palabras") or 0)),
        }
        if i < len(textos) and textos[i]:
            art["texto_ocr"] = textos[i]
        salida.append(art)
    return salida


def necesita_migracion(ruta: str) -> bool:
    """True si el .bashkar es de versión anterior a 11."""
    ruta = Path(ruta)
    if not ruta.exists():
        return False
    try:
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        version = str(datos.get("version", "0"))
        return int(version.split(".")[0]) < 11
    except Exception:
        return False


def migrar(ruta: str) -> dict:
    """
    Migra un archivo .bashkar de v10 a v11.

    Returns:
        {"ok": bool, "mensaje": str, "ruta_db": str, "ruta_backup": str}
    """
    ruta = Path(ruta)

    # 1. Backup
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta_backup = ruta.with_name(f"{ruta.stem}_v10_backup_{ts}.bashkar")
    shutil.copy2(ruta, ruta_backup)

    try:
        with open(ruta, encoding="utf-8") as f:
            datos_v10 = json.load(f)
    except Exception as e:
        return {"ok": False, "mensaje": f"No se pudo leer el archivo: {e}",
                "ruta_db": "", "ruta_backup": str(ruta_backup)}

    # 2. Crear SQLite en la misma carpeta que el .bashkar
    nombre_db = ruta.stem + ".db"
    ruta_db = ruta.parent / nombre_db
    repo = Repositorio(str(ruta_db))

    # 3. Migrar artículos a la DB
    articulos_json = _articulos_v10(ruta, datos_v10)
    n_arts = 0
    n_ents = 0

    for art in articulos_json:
        art_id = art.get("id", f"art_{n_arts:04d}")

        # Guardar artículo
        repo.guardar_articulo({
            "id":               art_id,
            "archivo_origen":   art.get("archivo", ""),
            "numero":           art.get("numero", ""),
            "tipo":             art.get("tipo", "articulo"),
            "titulo":           art.get("titulo"),
            "autor":            _normalizar_autor(art.get("autor")),
            "fecha_publicacion":art.get("fecha"),
            "seccion":          art.get("seccion"),
            "palabras":         art.get("n_palabras", 0),
            "estado":           "pendiente",
        })

        # Migrar OCR si existe
        ocr_data = art.get("ocr") or art.get("texto_ocr")
        if isinstance(ocr_data, dict):
            repo.guardar_ocr(
                art_id,
                texto_crudo=ocr_data.get("texto_crudo", ""),
                texto_limpio=ocr_data.get("texto_limpio", ""),
                confianza=ocr_data.get("confianza", 0.0),
                motor=ocr_data.get("motor", "tesseract_v10"),
            )
        elif isinstance(ocr_data, str) and ocr_data:
            repo.guardar_ocr(art_id, ocr_data, ocr_data, 0.0, "tesseract_v10")

        # Migrar entidades NER si existen
        ner_data = art.get("ner", {})
        entidades = []
        if isinstance(ner_data, dict):
            # Formato v10: {categoria: [texto, ...]}
            for cat, textos in ner_data.items():
                if isinstance(textos, list):
                    for t in textos:
                        if isinstance(t, str) and t.strip():
                            entidades.append({
                                "texto":     t,
                                "categoria": cat,
                                "confianza": 0.7,
                                "fuente":    "v10_legacy",
                            })
                        elif isinstance(t, dict):
                            entidades.append({
                                "texto":     t.get("texto", str(t)),
                                "categoria": cat,
                                "confianza": t.get("confianza", 0.7),
                                "fuente":    t.get("fuente", "v10_legacy"),
                            })
        if entidades:
            repo.guardar_entidades(art_id, entidades)
            n_ents += len(entidades)

        n_arts += 1

    # 4. Actualizar JSON con nueva versión y referencia a DB
    config_v10 = datos_v10.get("config", {})
    datos_nuevo = {
        "version":     VERSION_NUEVA,
        "nombre":      datos_v10.get("nombre", ruta.stem),
        "publicacion": datos_v10.get("publicacion", config_v10.get("publicacion", "")),
        "periodo":     datos_v10.get("periodo", config_v10.get("periodo", "")),
        "creado":      datos_v10.get("creado", datetime.now().isoformat()),
        "modificado":  datetime.now().isoformat(),
        # Ruta ABSOLUTA. Con el nombre pelado, project_manager la resolvía
        # contra el directorio de trabajo: al abrir Proyecto_04_Mar_2026 desde
        # otra carpeta se creaba un .db nuevo y vacío ahí, y todo lo que el
        # investigador anotara (351 artículos, 505 OCR, 115 entidades, 183
        # revisiones en el caso real) quedaba fuera del proyecto.
        "db":          str(ruta_db),
        "config":      config_v10,
        "progreso":    datos_v10.get("progreso", {}),
        # `resultados` se perdía al migrar: con él se iban el índice NER, los
        # nombres de los CSV guardados y las rutas del grafo y del Excel.
        "resultados":  datos_v10.get("resultados", {}),
        "historial_ia":datos_v10.get("historial_ia", []),
        "migracion": {
            "origen_version": str(datos_v10.get("version", "?")),
            "destino_version": VERSION_NUEVA,
            "fecha":           datetime.now().isoformat(),
            "articulos_migrados": n_arts,
            "entidades_migradas": n_ents,
        }
    }

    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos_nuevo, f, ensure_ascii=False, indent=2)

    return {
        "ok":           True,
        "mensaje":      f"Migración completada: {n_arts} artículos, {n_ents} entidades",
        "ruta_db":      str(ruta_db),
        "ruta_backup":  str(ruta_backup),
        "articulos":    n_arts,
        "entidades":    n_ents,
    }


# ── Migración de la capa de grafo (entidades canónicas + relaciones) ──────────
#
# Incremental y REVERSIBLE. No toca el .bashkar JSON ni los datos existentes:
# solo añade tres tablas nuevas (entidades_canonicas, menciones_canonicas,
# relaciones) y, opcionalmente, funde las menciones NER ya guardadas en
# entidades canónicas. revertir_grafo() las elimina sin pérdida de datos
# originales (las menciones siguen en la tabla `entidades`).

_TABLAS_GRAFO = ("relaciones", "menciones_canonicas", "entidades_canonicas")


def grafo_aplicado(ruta_db: str) -> bool:
    """True si la capa de grafo ya existe en la DB del proyecto."""
    import sqlite3
    if not Path(ruta_db).exists():
        return False
    with sqlite3.connect(str(ruta_db)) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master "
            "WHERE type='table' AND name='entidades_canonicas'"
        ).fetchone()
    return bool(row and row[0])


def aplicar_grafo(ruta_db: str, fundir: bool = True) -> dict:
    """
    Crea la capa de grafo en una DB de proyecto existente y, si fundir=True,
    funde las menciones NER ya guardadas en entidades canónicas.

    No modifica el .bashkar ni borra nada. Idempotente.
    """
    repo = Repositorio(str(ruta_db))  # executescript crea las tablas IF NOT EXISTS
    resultado = {"ok": True, "ruta_db": str(ruta_db),
                 "canonicas": 0, "menciones_vinculadas": 0, "fundido": False}
    if fundir:
        r = repo.fundir_menciones_en_canonicas(fuente="ner")
        resultado.update(r)
        resultado["fundido"] = True
    return resultado


def revertir_grafo(ruta_db: str) -> dict:
    """
    Elimina la capa de grafo (las tres tablas nuevas). Los datos originales
    (artículos, OCR, menciones en `entidades`) quedan intactos. Reversible:
    re-ejecutar aplicar_grafo() reconstruye todo desde las menciones.
    """
    import sqlite3
    if not Path(ruta_db).exists():
        return {"ok": False, "mensaje": "La DB no existe", "ruta_db": str(ruta_db)}
    with sqlite3.connect(str(ruta_db)) as conn:
        conn.execute("PRAGMA foreign_keys = OFF")
        for tabla in _TABLAS_GRAFO:
            conn.execute(f"DROP TABLE IF EXISTS {tabla}")
        conn.commit()
    return {"ok": True, "mensaje": "Capa de grafo eliminada (datos originales intactos)",
            "ruta_db": str(ruta_db)}


def migrar_carpeta(carpeta: str) -> list[dict]:
    """Migra todos los .bashkar en una carpeta que necesiten migración."""
    resultados = []
    for ruta in Path(carpeta).glob("*.bashkar"):
        if "_v10_backup_" in ruta.name:
            continue
        if necesita_migracion(str(ruta)):
            res = migrar(str(ruta))
            res["archivo"] = ruta.name
            resultados.append(res)
    return resultados
