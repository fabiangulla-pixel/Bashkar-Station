"""
core/project_manager.py — Sistema de proyectos locales para Bashkar Station.

Cada proyecto se guarda como un archivo .bashkar (JSON) en:
  ~/Documents/BashkarStation/proyectos/  (Windows)
  ~/Documents/BashkarStation/proyectos/  (macOS/Linux)

Estructura del archivo .bashkar:
  {
    "version":     "8.8",
    "nombre":      "Revista Estampa 1939-1942",
    "publicacion": "Estampa",
    "periodo":     "1939-1942",
    "creado":      "2025-03-01T10:22:00",
    "modificado":  "2025-03-04T15:30:00",
    "config":      { ... campos de configuración ... },
    "progreso":    { "ocr": true, "seg": false, ... },
    "resultados":  { ... DataFrames como records, resúmenes ... },
    "historial_ia": [ {tab, prompt, respuesta, fecha}, ... ]
  }

Los DataFrames grandes (df_articulos, df_layout, etc.) se guardan
como archivos Parquet/CSV en una subcarpeta del proyecto para
no hinchar el JSON principal.
"""

import json
import platform
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

VERSION = "11"


# ── Directorio base de proyectos ──────────────────────────────────────────────

def _dir_proyectos() -> Path:
    """Devuelve (y crea si no existe) la carpeta de proyectos."""
    if platform.system() == "Windows":
        base = Path.home() / "Documents" / "BashkarStation" / "proyectos"
    else:
        base = Path.home() / "Documents" / "BashkarStation" / "proyectos"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _archivo_reciente() -> Path:
    """Ruta del archivo que guarda cuál fue el último proyecto abierto."""
    return _dir_proyectos().parent / "ultimo_proyecto.txt"


# ── CRUD de proyectos ─────────────────────────────────────────────────────────

def listar_proyectos() -> list[dict]:
    """
    Devuelve lista de proyectos guardados, ordenada por fecha de modificación
    descendente. Cada item: {nombre, publicacion, periodo, modificado, ruta}.
    """
    proyectos = []
    for p in _dir_proyectos().glob("*.bashkar"):
        try:
            with open(p, encoding="utf-8") as f:
                meta = json.load(f)
            proyectos.append({
                "nombre":      meta.get("nombre", p.stem),
                "publicacion": meta.get("publicacion", ""),
                "periodo":     meta.get("periodo", ""),
                "modificado":  meta.get("modificado", ""),
                "creado":      meta.get("creado", ""),
                "progreso":    meta.get("progreso", {}),
                "ruta":        str(p),
            })
        except Exception:
            continue
    proyectos.sort(key=lambda x: x.get("modificado", ""), reverse=True)
    return proyectos


def nuevo_proyecto(nombre: str, publicacion: str, periodo: str = "") -> Path:
    """Crea un archivo .bashkar vacío (+ DB SQLite hermana) y devuelve su ruta."""
    slug = _slugify(nombre)
    ruta = _dir_proyectos() / f"{slug}.bashkar"
    # Evitar sobreescribir
    base, n = ruta, 1
    while ruta.exists():
        ruta = base.with_stem(f"{base.stem}_{n}"); n += 1

    # Crear la base de datos SQLite hermana
    ruta_db = str(ruta.with_suffix(".db"))
    try:
        from datos.repositorio import Repositorio
        Repositorio(ruta_db)   # crea esquema al instanciar
    except Exception:
        ruta_db = ""

    ahora = _ahora()
    datos = {
        "version":     VERSION,
        "nombre":      nombre,
        "publicacion": publicacion,
        "periodo":     periodo,
        "creado":      ahora,
        "modificado":  ahora,
        "db":          ruta_db,
        "config":      {},
        "progreso":    {t: False for t in
                        ("ocr","seg","anal","vis","comp")},
        "resultados":  {},
        "historial_ia": [],
    }
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    return ruta


def guardar_ultimo(ruta: Path):
    """Registra cuál fue el último proyecto abierto."""
    try:
        _archivo_reciente().write_text(str(ruta), encoding="utf-8")
    except Exception:
        pass


def cargar_ultimo() -> Optional[Path]:
    """Devuelve la ruta del último proyecto abierto, o None si no existe."""
    f = _archivo_reciente()
    if not f.exists():
        return None
    ruta = Path(f.read_text(encoding="utf-8").strip())
    return ruta if ruta.exists() else None


def eliminar_proyecto(ruta: Path):
    """Elimina el archivo .bashkar y la carpeta de datos asociada."""
    ruta = Path(ruta)
    if ruta.exists():
        ruta.unlink()
    datos_dir = ruta.with_suffix("")
    if datos_dir.exists() and datos_dir.is_dir():
        shutil.rmtree(datos_dir)


def renombrar_proyecto(ruta: Path, nuevo_nombre: str) -> Path:
    """Renombra el proyecto (campo nombre) sin cambiar el archivo."""
    ruta = Path(ruta)
    with open(ruta, encoding="utf-8") as f:
        datos = json.load(f)
    datos["nombre"] = nuevo_nombre
    datos["modificado"] = _ahora()
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    return ruta


# ── Serialización del estado ST ───────────────────────────────────────────────

def guardar_proyecto(ruta: Path, st, historial_ia: list = None):
    """
    Serializa el estado del objeto ST y lo guarda en el archivo .bashkar.
    Los DataFrames grandes se guardan como CSV en subcarpeta.
    """
    ruta = Path(ruta)
    datos_dir = ruta.with_suffix("")   # carpeta hermana para datos pesados
    datos_dir.mkdir(exist_ok=True)

    # Leer el JSON existente para preservar campos como creado/nombre
    try:
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
    except Exception:
        datos = {}

    # ── Config serializable ───────────────────────────────────────────────────
    config = {
        "publicacion":    getattr(st, "publicacion", ""),
        "periodo":        getattr(st, "periodo", ""),
        "pdf_dir":        str(getattr(st, "pdf_dir", "") or ""),
        "out_dir":        str(getattr(st, "out_dir", "") or ""),
        "input_tipo":     getattr(st, "input_tipo", "pdf"),
        "archivos_sel":   [str(p) for p in getattr(st, "archivos_sel", [])],
        "api_key":        getattr(st, "api_key", ""),
        "max_ia":         getattr(st, "max_ia", 15),
        "campos_semillas": getattr(st, "campos_semillas", {}),
    }

    # ── Progreso ──────────────────────────────────────────────────────────────
    progreso = {t: getattr(st, f"{t}_done", False)
                for t in ("ocr", "seg", "anal", "vis", "comp")}

    # ── Resumen OCR ───────────────────────────────────────────────────────────
    resultados = {}
    if getattr(st, "resumen_ocr", None):
        resultados["resumen_ocr"] = st.resumen_ocr

    # ── DataFrames → CSV ──────────────────────────────────────────────────────
    df_fields = {
        "df_articulos":  "articulos.csv",
        "df_firmas":     "firmas.csv",
        "df_secciones":  "secciones.csv",
        "df_campos":     "campos.csv",
        "df_layout":     "layout.csv",
        "df_temas":      "temas.csv",
        "df_doc_temas":  "doc_temas.csv",
    }
    saved_dfs = []
    for attr, fname in df_fields.items():
        df = getattr(st, attr, None)
        if df is not None and not df.empty:
            try:
                # No guardar columna 'texto' (muy pesada)
                df_save = df.drop(columns=["texto"], errors="ignore")
                df_save.to_csv(datos_dir / fname, index=False, encoding="utf-8")
                saved_dfs.append(attr)
            except Exception:
                pass
    if saved_dfs:
        resultados["dataframes_guardados"] = saved_dfs

    # ── corpus_txt → JSON separado ────────────────────────────────────────────
    corpus_txt = getattr(st, "corpus_txt", [])
    if corpus_txt:
        try:
            import json as _json
            with open(datos_dir / "corpus_txt.json", "w", encoding="utf-8") as _f:
                _json.dump(corpus_txt, _f, ensure_ascii=False)
            resultados["corpus_txt_guardado"] = True
        except Exception:
            pass

    # ── Temas LDA ─────────────────────────────────────────────────────────────
    if getattr(st, "temas_lda", None):
        resultados["temas_lda"] = st.temas_lda

    # ── Rutas de archivos generados ───────────────────────────────────────────
    for attr in ("graph_path", "xlsx_path"):
        val = getattr(st, attr, None)
        if val:
            resultados[attr] = str(val)

    # ── Índice NER global ─────────────────────────────────────────────────────
    indice_ner = getattr(st, "indice_ner_global", None)
    if indice_ner and any(indice_ner.values()):
        resultados["indice_ner_global"] = indice_ner

    # ── Enlaces Wikidata ──────────────────────────────────────────────────────
    wikidata = getattr(st, "wikidata_enlaces", None)
    if wikidata and any(wikidata.values()):
        resultados["wikidata_enlaces"] = wikidata

    # ── Índice FAISS semántico ────────────────────────────────────────────────
    # Se guarda junto al .bashkar como <stem>.faiss + <stem>.ids.json
    ruta_faiss = str(ruta.with_suffix("")) + "_semantico"
    try:
        indice_sem = getattr(st, "_bsem_indice", None)
        if indice_sem is not None and getattr(indice_sem, "construido", False):
            indice_sem.guardar(ruta_faiss)
            resultados["faiss_ruta"] = ruta_faiss
    except Exception:
        pass

    # ── Configuración multi-proveedor ─────────────────────────────────────────
    api_keys = getattr(st, "api_keys", {})
    if api_keys:
        config["api_keys"] = api_keys
    modelos_etapa = getattr(st, "modelos_etapa", {})
    if modelos_etapa:
        config["modelos_etapa"] = modelos_etapa

    # ── Configuración lingüística del proyecto ────────────────────────────────
    config["stopwords_proyecto"] = getattr(st, "stopwords_proyecto", [])
    config["lematizar"]          = getattr(st, "lematizar", True)
    config["norm_version"]       = getattr(st, "norm_version", "manual")

    # ── Historial IA ──────────────────────────────────────────────────────────
    historial = historial_ia or []

    # ── Sincronizar con SQLite ────────────────────────────────────────────────
    ruta_db = datos.get("db", "")
    if not ruta_db:
        ruta_db = str(ruta.with_suffix(".db"))
    try:
        from datos.repositorio import Repositorio
        repo = Repositorio(ruta_db)
        # Artículos desde df_articulos
        df_arts = getattr(st, "df_articulos", None)
        if df_arts is not None and not df_arts.empty:
            for _, row in df_arts.iterrows():
                art = {
                    "id":       str(row.get("id", row.get("titulo", f"art_{_}"))),
                    "titulo":   str(row.get("titulo", "")),
                    "autor":    str(row.get("autor", "")),
                    "tipo":     str(row.get("tipo", "articulo")),
                    "palabras": int(row.get("n_palabras", row.get("palabras", 0)) or 0),
                    "estado":   str(row.get("estado", "pendiente")),
                    "numero":   str(row.get("numero", "")),
                    "seccion":  str(row.get("seccion", "")),
                }
                repo.guardar_articulo(art)
                # OCR si está disponible en la fila
                texto = str(row.get("texto", row.get("contenido", "")))
                if texto and texto != "nan":
                    repo.guardar_ocr(art["id"], texto, texto,
                                     float(row.get("confianza_ocr", 0.0) or 0.0), "legacy")
        # Entidades NER
        indice_ner = getattr(st, "indice_ner_global", None)
        if indice_ner and any(indice_ner.values()):
            for cat, entidades in indice_ner.items():
                for texto_ent, art_ids in entidades.items():
                    for aid in art_ids:
                        repo.guardar_entidades(aid, [
                            {"texto": texto_ent, "categoria": cat,
                             "confianza": 0.85, "fuente": "ner_engine"}
                        ])
        ruta_db = str(repo.ruta_db)
    except Exception:
        pass

    # ── Escribir ──────────────────────────────────────────────────────────────
    datos.update({
        "version":      VERSION,
        "publicacion":  config["publicacion"],
        "periodo":      config["periodo"],
        "modificado":   _ahora(),
        "db":           ruta_db,
        "config":       config,
        "progreso":     progreso,
        "resultados":   resultados,
        "historial_ia": historial,
    })
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)


def cargar_proyecto(ruta: Path, st):
    """
    Restaura el estado de ST desde un archivo .bashkar.
    Si el archivo es v10 (sin DB SQLite), lo migra automáticamente antes de cargar.
    Devuelve dict con {ok: bool, mensaje: str, historial_ia: list, migrado: bool}.
    """
    ruta = Path(ruta)
    if not ruta.exists():
        return {"ok": False, "mensaje": f"Archivo no encontrado: {ruta}"}

    # ── Migración automática v10 → v11 ────────────────────────────────────────
    migrado = False
    try:
        from datos.migracion import necesita_migracion, migrar
        if necesita_migracion(str(ruta)):
            resultado = migrar(str(ruta))
            migrado = resultado.get("ok", False)
    except Exception:
        pass

    with open(ruta, encoding="utf-8") as f:
        datos = json.load(f)

    config = datos.get("config", {})
    from pathlib import Path as _P

    st.publicacion  = config.get("publicacion", "Mi publicación")
    st.periodo      = config.get("periodo", "")
    pdf_dir         = config.get("pdf_dir", "")
    st.pdf_dir      = _P(pdf_dir) if pdf_dir else None
    out_dir         = config.get("out_dir", "")
    st.out_dir      = _P(out_dir) if out_dir else None
    st.input_tipo   = config.get("input_tipo", "pdf")
    st.archivos_sel = [_P(p) for p in config.get("archivos_sel", [])]
    st.api_key      = config.get("api_key", "")
    st.max_ia       = config.get("max_ia", 15)
    st.campos_semillas = config.get("campos_semillas", {})

    progreso = datos.get("progreso", {})
    for t in ("ocr", "seg", "anal", "vis", "comp"):
        setattr(st, f"{t}_done", progreso.get(t, False))

    resultados = datos.get("resultados", {})
    st.resumen_ocr = resultados.get("resumen_ocr")
    st.temas_lda   = resultados.get("temas_lda")
    st.graph_path  = _P(resultados["graph_path"]) if resultados.get("graph_path") else None
    st.xlsx_path   = _P(resultados["xlsx_path"])  if resultados.get("xlsx_path")  else None

    # ── Índice NER global ─────────────────────────────────────────────────────
    indice_ner = resultados.get("indice_ner_global")
    if indice_ner:
        st.indice_ner_global = indice_ner
        st.ner_done = True

    # ── Enlaces Wikidata ──────────────────────────────────────────────────────
    wikidata = resultados.get("wikidata_enlaces")
    if wikidata:
        st.wikidata_enlaces = wikidata

    # ── Índice FAISS semántico ────────────────────────────────────────────────
    ruta_faiss = resultados.get("faiss_ruta", "")
    if not ruta_faiss:
        ruta_faiss = str(ruta.with_suffix("")) + "_semantico"
    try:
        from core.busqueda_semantica import IndiceSemantico
        indice_sem = IndiceSemantico()
        if indice_sem.cargar(ruta_faiss):
            st._bsem_indice = indice_sem
    except Exception:
        pass

    # ── Configuración multi-proveedor ─────────────────────────────────────────
    api_keys = config.get("api_keys", {})
    if api_keys:
        st.api_keys = api_keys
        st.api_key  = next(
            (v for v in (api_keys.get("anthropic",""), api_keys.get("openai",""),
                         api_keys.get("gemini","")) if v), ""
        )
    modelos_etapa = config.get("modelos_etapa", {})
    if modelos_etapa:
        st.modelos_etapa = modelos_etapa

    # ── Configuración lingüística del proyecto ────────────────────────────────
    st.stopwords_proyecto = config.get("stopwords_proyecto", [])
    st.lematizar          = config.get("lematizar", True)
    st.norm_version       = config.get("norm_version", "manual")

    # ── Restaurar DataFrames desde CSV ────────────────────────────────────────
    datos_dir = ruta.with_suffix("")
    df_fields = {
        "df_articulos": "articulos.csv",
        "df_firmas":    "firmas.csv",
        "df_secciones": "secciones.csv",
        "df_campos":    "campos.csv",
        "df_layout":    "layout.csv",
        "df_temas":     "temas.csv",
        "df_doc_temas": "doc_temas.csv",
    }
    try:
        import pandas as pd
        for attr, fname in df_fields.items():
            csv_path = datos_dir / fname
            if csv_path.exists():
                setattr(st, attr, pd.read_csv(csv_path, low_memory=False))
    except ImportError:
        pass

    # ── Restaurar corpus_txt ──────────────────────────────────────────────────
    corpus_txt_path = datos_dir / "corpus_txt.json"
    if corpus_txt_path.exists():
        try:
            import json as _json
            with open(corpus_txt_path, encoding="utf-8") as _f:
                st.corpus_txt = _json.load(_f)
        except Exception:
            st.corpus_txt = []
    elif st.out_dir and _P(st.out_dir).exists():
        # Reconstruir desde archivos TXT en 03_ocr/
        try:
            ocr_dir = _P(st.out_dir) / "03_ocr"
            textos = []
            if ocr_dir.exists():
                for sub in sorted(ocr_dir.iterdir()):
                    if sub.is_dir():
                        txts = sorted(sub.glob("*.txt"))
                        if txts:
                            textos.append(txts[-1].read_text(encoding="utf-8",
                                                              errors="replace"))
                    elif sub.suffix == ".txt":
                        textos.append(sub.read_text(encoding="utf-8",
                                                    errors="replace"))
            st.corpus_txt = textos
        except Exception:
            st.corpus_txt = []

    # ── Conectar/crear SQLite ─────────────────────────────────────────────────
    ruta_db = datos.get("db", "")
    if not ruta_db:
        ruta_db = str(ruta.with_suffix(".db"))
    try:
        from datos.repositorio import Repositorio
        repo = Repositorio(ruta_db)
        st.repo = repo
        st.ruta_db = ruta_db
    except Exception:
        st.repo = None
        st.ruta_db = ""

    historial = datos.get("historial_ia", [])
    msg = "Proyecto cargado"
    if migrado:
        msg = "Proyecto migrado a v11 y cargado"
    return {"ok": True, "mensaje": msg, "historial_ia": historial,
            "nombre": datos.get("nombre", ruta.stem), "migrado": migrado}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _slugify(texto: str) -> str:
    import re
    s = re.sub(r"[^\w\s\-]", "", texto, flags=re.UNICODE)
    s = re.sub(r"\s+", "_", s.strip())
    return s[:60] or "proyecto"


def _ahora() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def fecha_legible(iso: str) -> str:
    """Convierte '2025-03-04T15:30:00' a '4 mar 2025, 15:30'."""
    try:
        dt = datetime.fromisoformat(iso)
        meses = ["","ene","feb","mar","abr","may","jun",
                 "jul","ago","sep","oct","nov","dic"]
        return f"{dt.day} {meses[dt.month]} {dt.year}, {dt.strftime('%H:%M')}"
    except Exception:
        return iso


def progreso_str(progreso: dict) -> str:
    """'OCR ✓  Seg ✓  Anal —  Vis —  Comp —'"""
    etiq = {"ocr":"OCR","seg":"Seg","anal":"Anal","vis":"Vis","comp":"Comp"}
    partes = [f"{v} {'✓' if progreso.get(k) else '—'}" for k, v in etiq.items()]
    return "  ".join(partes)
