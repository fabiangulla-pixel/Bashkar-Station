"""api/app.py — API de Bashkar Station (FastAPI), en paridad con el escritorio.

    uvicorn api.app:app --port 8422          # o: python -m api
    http://localhost:8422/docs               # documentación interactiva

Toda la lógica vive en ``core/``: esta capa solo traduce HTTP. El estado por
sesión y los trabajos en hilo se reutilizan de ``servidor_web.py`` (no se
duplican). ``core/operaciones.py`` registra qué operación del escritorio
corresponde a qué ruta, y ``tests/test_paridad.py`` lo hace cumplir.

Modos (los mismos que la web):
- **Local** (sin ``BASHKAR_PASSWORD``): una sola sesión, acceso a rutas del disco,
  como el escritorio.
- **Público** (con ``BASHKAR_PASSWORD``): ``POST /api/v1/sesiones`` con la
  contraseña devuelve un token; cada petición lleva ``Authorization: Bearer <token>``.
  Cada sesión trabaja en su carpeta temporal, sin ver el disco del servidor.
"""

from __future__ import annotations

import secrets
import tempfile
import threading
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

import servidor_web as W
from core import operaciones

VERSION_API = "1.0"

app = FastAPI(title="Bashkar Station API", version=VERSION_API,
              description="Análisis de prensa histórica: OCR con enrutador GPU, "
                          "segmentación, NER, análisis y exportación.")


# ══════════════════════════════════════════════════════════════════════════════
# SESIÓN
# ══════════════════════════════════════════════════════════════════════════════
def sesion(authorization: str | None = Header(default=None)) -> W.EstadoServidor:
    W._barrer_sesiones()
    if not W.MODO_PUBLICO:
        ses = W.ESTADO_LOCAL
    else:
        token = (authorization or "").removeprefix("Bearer ").strip()
        with W._SESIONES_LOCK:
            ses = W.SESIONES.get(token)
        if ses is None:
            raise HTTPException(401, "Sesión requerida: POST /api/v1/sesiones")
    ses.tocar()
    return ses


def _error(e: Exception) -> HTTPException:
    return HTTPException(400, str(e))


class Login(BaseModel):
    password: str = ""


@app.post("/api/v1/sesiones", tags=["sesión"])
def crear_sesion(datos: Login):
    if not W.MODO_PUBLICO:
        return {"token": None, "modo_publico": False}
    if not secrets.compare_digest(datos.password.encode(), W.PASSWORD.encode()):
        raise HTTPException(401, "Contraseña incorrecta")
    token = secrets.token_urlsafe(32)
    with W._SESIONES_LOCK:
        W.SESIONES[token] = W.EstadoServidor()
    return {"token": token, "modo_publico": True}


# ══════════════════════════════════════════════════════════════════════════════
# SISTEMA
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/v1/salud", tags=["sistema"])
def salud():
    return {"ok": True, "version": VERSION_API, "modo_publico": W.MODO_PUBLICO}


@app.get("/api/v1/sistema", tags=["sistema"])
def sistema():
    """GPU, capacidades del host y paridad con el escritorio."""
    gpu = {"disponible": False}
    try:
        import torch
        if torch.cuda.is_available():
            p = torch.cuda.get_device_properties(0)
            gpu = {"disponible": True, "nombre": p.name,
                   "vram_gb": round(p.total_memory / 1e9, 1), "cuda": torch.version.cuda}
    except Exception:
        pass
    from core.recursos import dispositivo_torch
    return {"gpu": gpu, "dispositivo": dispositivo_torch(),
            "capacidades": W.detectar_capacidades(), "paridad": operaciones.resumen()}


@app.get("/api/v1/paridad", tags=["sistema"])
def paridad():
    return [{"clave": op.clave, "escritorio": list(op.escritorio), "api": op.api,
             "nota": op.nota} for op in operaciones.OPERACIONES]


# ══════════════════════════════════════════════════════════════════════════════
# PROYECTOS
# ══════════════════════════════════════════════════════════════════════════════
class NuevoProyecto(BaseModel):
    nombre: str
    publicacion: str = ""
    periodo: str = ""


class RutaProyecto(BaseModel):
    ruta: str


@app.get("/api/v1/estado", tags=["proyecto"])
def estado(ses=Depends(sesion)):
    return W._snapshot_estado(ses)


@app.get("/api/v1/proyectos", tags=["proyecto"])
def proyectos(ses=Depends(sesion)):
    return W._listar_proyectos(ses)


@app.post("/api/v1/proyectos", tags=["proyecto"])
def nuevo_proyecto(datos: NuevoProyecto, ses=Depends(sesion)):
    if not datos.nombre.strip():
        raise HTTPException(400, "Falta el nombre del proyecto")
    W._crear_proyecto(ses, datos.nombre.strip(), datos.publicacion, datos.periodo)
    return W._snapshot_estado(ses)


@app.post("/api/v1/proyectos/cargar", tags=["proyecto"])
def cargar_proyecto(datos: RutaProyecto, ses=Depends(sesion)):
    try:
        W._cargar_proyecto(ses, datos.ruta)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    return W._snapshot_estado(ses)


@app.post("/api/v1/proyectos/guardar", tags=["proyecto"])
def guardar_proyecto(ses=Depends(sesion)):
    try:
        W._guardar_proyecto_seguro(ses)
    except ValueError as e:
        raise _error(e) from e
    return {"ok": True}


@app.post("/api/v1/subir", tags=["proyecto"])
async def subir(archivo: UploadFile = File(...), ses=Depends(sesion)):
    nombre = W._sanear_nombre(archivo.filename or "archivo.pdf")
    destino = ses.dir_trabajo / "subidas" / nombre
    with open(destino, "wb") as f:
        while bloque := await archivo.read(1 << 20):
            f.write(bloque)
    if destino.stat().st_size == 0:
        destino.unlink()
        raise HTTPException(400, "Archivo vacío")
    return {"nombre": nombre, "bytes": destino.stat().st_size}


# ══════════════════════════════════════════════════════════════════════════════
# OCR
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/v1/ocr/motores", tags=["ocr"])
def motores_ocr():
    from core.ocr import crear, nombres
    salida = []
    for n in nombres():
        try:
            m = crear(n)
            motivo = m.motivo_no_disponible()
            etiqueta = m.etiqueta
        except Exception as e:
            motivo, etiqueta = str(e), n
        salida.append({"nombre": n, "etiqueta": etiqueta, "disponible": motivo is None,
                       "motivo": motivo})
    return salida


@app.get("/api/v1/ocr/plan", tags=["ocr"])
def plan_ocr():
    """Qué motores usaría el enrutador ahora (según config/ocr.toml y lo instalado)."""
    from core.ocr.enrutador import Enrutador
    try:
        return Enrutador().plan()
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from e


# Una página suelta: reutiliza un enrutador por proceso para no recargar modelos.
_ENRUTADOR = None
_ENRUTADOR_LOCK = threading.Lock()


def _enrutador():
    global _ENRUTADOR
    from core.ocr.enrutador import Enrutador
    if _ENRUTADOR is None:
        _ENRUTADOR = Enrutador()
    return _ENRUTADOR


@app.post("/api/v1/ocr/pagina", tags=["ocr"])
async def ocr_pagina(imagen: UploadFile = File(...), motor: str = Form("auto"),
                     ses=Depends(sesion)):
    """OCR síncrono de UNA imagen. ``motor="auto"`` usa el enrutador; si no,
    el motor indicado. Devuelve texto, bloques con bbox y la fila de procedencia."""
    nombre = W._sanear_nombre(imagen.filename or "pagina.png")
    tmp = Path(tempfile.mkdtemp(dir=ses.dir_trabajo))
    ruta = tmp / nombre
    ruta.write_bytes(await imagen.read())
    txt = tmp / (ruta.stem + ".txt")
    with _ENRUTADOR_LOCK:
        if motor == "auto":
            r, fila = _enrutador().procesar(ruta, txt, "suelta")
        else:
            from core.ocr import crear
            from core.ocr.servicio import ocr_pagina as servicio
            try:
                m = crear(motor)
            except ValueError as e:
                raise HTTPException(404, str(e)) from e
            motivo = m.motivo_no_disponible()
            if motivo:
                raise HTTPException(503, f"{motor}: {motivo}")
            try:
                r, fila = servicio(m, ruta, txt, "suelta")
            finally:
                m.liberar()
    return {"texto": txt.read_text("utf-8"),
            "bloques": [b.a_dict() for b in (r.bloques if r else [])],
            "procedencia": {k: v for k, v in fila.items() if k != "txt_path"}}


class IniciarOCR(BaseModel):
    archivos: list[str] | None = None     # nombres en subidas/; None = todos
    dpi: int = 300


@app.post("/api/v1/ocr/iniciar", tags=["ocr"])
def iniciar_ocr(datos: IniciarOCR, ses=Depends(sesion)):
    """OCR de los PDF/imágenes subidos con el enrutador (equivale a la Ruta 0
    del escritorio). Escribe 03_ocr/ y 04_analisis/ocr_metadatos.csv."""
    od = ses.out_dir()
    if not od:
        raise HTTPException(400, "Crea o carga un proyecto primero")
    subidas = ses.dir_trabajo / "subidas"
    candidatos = sorted(p for p in subidas.iterdir()
                        if p.suffix.lower() in {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"})
    if datos.archivos is not None:
        pedidos = {W._sanear_nombre(n) for n in datos.archivos}
        candidatos = [p for p in candidatos if p.name in pedidos]
    if not candidatos:
        raise HTTPException(400, "No hay archivos subidos para OCR")

    def _fn(trabajo):
        from core.ocr.enrutador import Enrutador
        from core.ocr.servicio import guardar_metadatos, ocr_documento
        filas: list[dict] = []
        with Enrutador(log=lambda m: trabajo.avanzar(None, m)) as enr:
            for i, origen in enumerate(candidatos):
                base = int(i / len(candidatos) * 100)
                filas += ocr_documento(
                    origen, od, enr, dpi=datos.dpi, log=lambda m: trabajo.avanzar(None, m),
                    progreso=lambda k, n, b=base: trabajo.avanzar(
                        b + int(k / max(1, n) * 100 / len(candidatos)), f"{origen.name} {k}/{n}"))
        guardar_metadatos(filas, od)
        ses.st.marcar_etapa("ocr", "ready")
        ses.st.ocr_done = True
        return {"paginas": len(filas), "revision": sum(1 for f in filas if f.get("revision"))}

    return {"trabajo": W._lanzar_trabajo(ses, "ocr", _fn).id}


@app.get("/api/v1/ocr/bloques", tags=["ocr"])
def bloques(numero: str, pagina: str, ses=Depends(sesion)):
    from core.ocr.servicio import cargar_bloques
    od = ses.out_dir()
    if not od:
        raise HTTPException(400, "No hay proyecto")
    txt = (od / "03_ocr" / W._sanear_nombre(numero) / (W._sanear_nombre(pagina) + ".txt")).resolve()
    if not txt.is_relative_to((od / "03_ocr").resolve()) or not txt.exists():
        raise HTTPException(404, "Página no encontrada")
    return {"texto": txt.read_text("utf-8", errors="replace"),
            "bloques": [b.a_dict() for b in cargar_bloques(txt)]}


# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE
# ══════════════════════════════════════════════════════════════════════════════
class Normalizar(BaseModel):
    numero: str | None = None


def _trabajo(fn, *args):
    try:
        return {"trabajo": fn(*args).id}
    except ValueError as e:
        raise _error(e) from e


@app.post("/api/v1/normalizar", tags=["pipeline"])
def normalizar(datos: Normalizar, ses=Depends(sesion)):
    return _trabajo(W._trabajo_normalizar, ses, datos.numero)


@app.post("/api/v1/segmentar", tags=["pipeline"])
def segmentar(ses=Depends(sesion)):
    return _trabajo(W._trabajo_segmentar, ses)


@app.post("/api/v1/ner", tags=["pipeline"])
def ner(ses=Depends(sesion)):
    return _trabajo(W._trabajo_ner, ses)


@app.post("/api/v1/analisis", tags=["pipeline"])
def analisis(ses=Depends(sesion)):
    return _trabajo(W._trabajo_analizar, ses)


class Layout(BaseModel):
    numero: str
    pagina: str
    motor: str = "yolo"


@app.post("/api/v1/layout", tags=["pipeline"])
def layout(datos: Layout, ses=Depends(sesion)):
    """Zonas de layout de una página ya convertida en imagen (02_imagenes/)."""
    od = ses.out_dir()
    if not od:
        raise HTTPException(400, "No hay proyecto")
    carpeta = od / "02_imagenes" / W._sanear_nombre(datos.numero)
    imgs = [p for p in carpeta.glob(W._sanear_nombre(datos.pagina) + ".*")]
    if not imgs:
        raise HTTPException(404, "Imagen de página no encontrada")
    from core.layout_neural import detectar_layout

    def _fn(trabajo):
        zonas = detectar_layout(imgs[0], motor=datos.motor,
                                callback=lambda m: trabajo.avanzar(None, str(m)))
        return {"zonas": zonas}
    return {"trabajo": W._lanzar_trabajo(ses, "layout", _fn).id}


class Benchmark(BaseModel):
    carpeta: str = "benchmark/estampa-1939"


@app.post("/api/v1/benchmark", tags=["pipeline"])
def benchmark(datos: Benchmark, ses=Depends(sesion)):
    """Evalúa las salidas del benchmark contra la referencia humana (CER/WER).
    Falla con mensaje claro si la referencia no está transcrita."""
    if W.MODO_PUBLICO:
        raise HTTPException(403, "El benchmark lee carpetas del servidor: solo en modo local")
    from core import benchmark_regresion as BR

    def _fn(trabajo):
        trabajo.avanzar(5, "Evaluando contra la referencia humana…")
        return BR.evaluar(Path(datos.carpeta))
    return {"trabajo": W._lanzar_trabajo(ses, "bench", _fn).id}


@app.get("/api/v1/trabajos/{trabajo_id}", tags=["pipeline"])
def trabajo(trabajo_id: str, ses=Depends(sesion)):
    with ses.lock:
        t = ses.trabajos.get(trabajo_id)
    if t is None:
        raise HTTPException(404, "Trabajo no encontrado")
    return t.snapshot()


# ══════════════════════════════════════════════════════════════════════════════
# RESULTADOS
# ══════════════════════════════════════════════════════════════════════════════
@app.get("/api/v1/articulos", tags=["resultados"])
def articulos(ses=Depends(sesion)):
    return [{"i": i, "id": a.get("id"), "numero": a.get("numero", ""),
             "titulo": a.get("titulo", ""), "seccion": a.get("seccion", ""),
             "palabras": a.get("palabras", len((a.get("texto") or "").split()))}
            for i, a in enumerate(ses.articulos)]


@app.get("/api/v1/articulos/{i}", tags=["resultados"])
def articulo(i: int, ses=Depends(sesion)):
    try:
        return ses.articulos[i]
    except IndexError as e:
        raise HTTPException(404, "Artículo no encontrado") from e


@app.get("/api/v1/entidades", tags=["resultados"])
def entidades(ses=Depends(sesion)):
    return ses.st.indice_ner_global


@app.get("/api/v1/resultados/analisis", tags=["resultados"])
def resultado_analisis(ses=Depends(sesion)):
    return ses.analisis


class Exportar(BaseModel):
    formato: str   # tei | bibtex | csv_ner | csv_articulos


@app.post("/api/v1/exportar", tags=["resultados"])
def exportar(datos: Exportar, ses=Depends(sesion)):
    try:
        ruta = W._exportar(ses, datos.formato)
    except ValueError as e:
        raise _error(e) from e
    return {"archivo": ruta.name, "descarga": f"/api/v1/descargas/{ruta.name}"}


@app.get("/api/v1/descargas/{nombre}", tags=["resultados"])
def descargar(nombre: str, ses=Depends(sesion)):
    ruta = (ses.dir_trabajo / "exportes" / W._sanear_nombre(nombre)).resolve()
    if not ruta.is_relative_to(ses.dir_trabajo.resolve()) or not ruta.exists():
        raise HTTPException(404, "Archivo no encontrado")
    return FileResponse(ruta, filename=ruta.name)


# ══════════════════════════════════════════════════════════════════════════════
# LECTURA DISTANTE Y PUBLICACIÓN (sesión 73 — cierre de paridad, core/operaciones.py)
# ══════════════════════════════════════════════════════════════════════════════
def _textos(ses) -> list[str]:
    from core.servicios_ner import textos_de_articulos
    textos = [t for _, t in textos_de_articulos(ses.articulos)]
    if not textos:
        raise ValueError("No hay artículos: corre Segmentar primero")
    return textos


def _textos_dict(ses) -> dict:
    from core.servicios_ner import textos_de_articulos
    d = dict(textos_de_articulos(ses.articulos))
    if not d:
        raise ValueError("No hay artículos: corre Segmentar primero")
    return d


class Topicos(BaseModel):
    n: int = 10
    usar_bertopic: bool = True
    usar_llm: bool = False
    min_df: int = 2
    max_df: float = 0.95
    n_words: int = 10


@app.post("/api/v1/topicos", tags=["lectura_distante"])
def topicos(datos: Topicos, ses=Depends(sesion)):
    def _fn(trabajo):
        from core.topic_engine import estadisticas_topicos, modelar_topicos
        textos = _textos(ses)
        api_key = ses.st.api_key if datos.usar_llm else None
        resultado = modelar_topicos(
            textos, n_topicos=datos.n, api_key=api_key, usar_bertopic=datos.usar_bertopic,
            min_df=datos.min_df, max_df=datos.max_df, n_palabras=datos.n_words,
            callback=lambda m: trabajo.avanzar(None, str(m)))
        return {"backend": resultado.get("backend"), "estadisticas": estadisticas_topicos(resultado)}
    return _trabajo(lambda: W._lanzar_trabajo(ses, "topicos", _fn))


class Nube(BaseModel):
    max_palabras: int = 150


@app.post("/api/v1/nube", tags=["lectura_distante"])
def nube(datos: Nube, ses=Depends(sesion)):
    def _fn(trabajo):
        from core.viz_engine import nube_palabras
        ruta = ses.dir_trabajo / "exportes" / "nube_palabras.png"
        nube_palabras(_textos(ses), ruta, titulo=ses.st.publicacion or "Corpus",
                      max_palabras=datos.max_palabras)
        return {"descarga": f"/api/v1/descargas/{ruta.name}"}
    return _trabajo(lambda: W._lanzar_trabajo(ses, "nube", _fn))


@app.post("/api/v1/lexico", tags=["lectura_distante"])
def lexico(ses=Depends(sesion)):
    def _fn(trabajo):
        from core.lexicon_engine import construir_glosario
        glosario = construir_glosario(
            _textos_dict(ses), ses.st.api_key,
            callback=lambda i, t, a: trabajo.avanzar(int(i / max(t, 1) * 100), f"{i}/{t} {a}"))
        return {"glosario": glosario, "n_entradas": sum(len(v) for v in glosario.values())}
    return _trabajo(lambda: W._lanzar_trabajo(ses, "lexico", _fn))


class Estilo(BaseModel):
    n_clusters: int = 5


@app.post("/api/v1/estilo", tags=["lectura_distante"])
def estilo(datos: Estilo, ses=Depends(sesion)):
    def _fn(trabajo):
        from core.stylometry_engine import cluster_tematico
        return {"clusters": cluster_tematico(_textos_dict(ses), n_clusters=datos.n_clusters)}
    return _trabajo(lambda: W._lanzar_trabajo(ses, "estilo", _fn))


class Tono(BaseModel):
    usar_ia: bool = False
    workers: int = 4


@app.post("/api/v1/tono", tags=["lectura_distante"])
def tono(datos: Tono, ses=Depends(sesion)):
    def _fn(trabajo):
        from core.sentiment_engine import analizar_corpus_tono, estadisticas_tono
        api_key = ses.st.api_key if datos.usar_ia else None
        resultados = analizar_corpus_tono(
            _textos_dict(ses), api_key, workers=datos.workers,
            callback=lambda n, t, a: trabajo.avanzar(int(n / max(t, 1) * 100), f"{n}/{t} {a}"))
        return {"resultados": resultados, "estadisticas": estadisticas_tono(resultados)}
    return _trabajo(lambda: W._lanzar_trabajo(ses, "tono", _fn))


@app.post("/api/v1/narrativas", tags=["lectura_distante"])
def narrativas(ses=Depends(sesion)):
    def _fn(trabajo):
        from core.storytelling_engine import generar_narrativa
        api_key = ses.st.api_keys.get("anthropic", "") or ses.st.api_key
        if not api_key:
            raise ValueError("Falta la clave de Anthropic (POST /api/v1/estado con api_keys)")
        stats_corpus = {
            "n_articulos": len(ses.articulos),
            "n_palabras_total": sum(len((a.get("texto") or "").split()) for a in ses.articulos),
            "proyecto": ses.st.publicacion or "Corpus",
        }
        salida = {"corpus": generar_narrativa(stats_corpus, api_key, seccion="corpus")}
        if ses.st.metricas_red:
            salida["red"] = generar_narrativa(ses.st.metricas_red, api_key, seccion="red")
        return {"narrativas": salida}
    return _trabajo(lambda: W._lanzar_trabajo(ses, "narrativas", _fn))


class LineaTiempo(BaseModel):
    agrupar_por: str = "seccion"


@app.post("/api/v1/linea_tiempo", tags=["lectura_distante"])
def linea_tiempo(datos: LineaTiempo, ses=Depends(sesion)):
    def _fn(trabajo):
        from core.timeline_engine import generar_timeline_html
        articulos = [{"art_id": a.get("id", f"art_{i:04d}"), "titulo": a.get("titulo", ""),
                      "autor": a.get("autor", ""), "seccion": a.get("seccion", ""),
                      "fecha": a.get("fecha", ""), "numero": a.get("numero", ""),
                      "tono": a.get("tono", "")} for i, a in enumerate(ses.articulos)]
        if not articulos:
            raise ValueError("No hay artículos: corre Segmentar primero")
        ruta = ses.dir_trabajo / "exportes" / "timeline_editorial.html"
        generar_timeline_html(articulos, ruta, titulo_corpus=ses.st.publicacion or "Corpus editorial",
                              agrupar_por=datos.agrupar_por,
                              callback=lambda n, t, m: trabajo.avanzar(int(n / max(t, 1) * 100), m))
        return {"descarga": f"/api/v1/descargas/{ruta.name}", "n_articulos": len(articulos)}
    return _trabajo(lambda: W._lanzar_trabajo(ses, "linea_tiempo", _fn))


@app.post("/api/v1/mapa", tags=["lectura_distante"])
def mapa(ses=Depends(sesion)):
    def _fn(trabajo):
        from core.viz_engine import mapa_lugares
        if not ses.st.indice_ner_global:
            raise ValueError("No hay entidades: corre NER primero")
        ruta = ses.dir_trabajo / "exportes" / "mapa_lugares.html"
        mapa_lugares(ses.st.indice_ner_global, ruta)
        return {"descarga": f"/api/v1/descargas/{ruta.name}"}
    return _trabajo(lambda: W._lanzar_trabajo(ses, "mapa", _fn))


class MapaCalor(BaseModel):
    terminos: list[str]


@app.post("/api/v1/mapa_calor", tags=["lectura_distante"])
def mapa_calor(datos: MapaCalor, ses=Depends(sesion)):
    def _fn(trabajo):
        import pandas as pd

        from core.viz_engine import heatmap_temporal
        if not datos.terminos:
            raise ValueError("Falta al menos un término")
        textos = _textos(ses)
        df = pd.DataFrame({"texto": textos,
                           "fecha": [f"1935-{(i % 12) + 1:02d}-01" for i in range(len(textos))]})
        ruta = ses.dir_trabajo / "exportes" / "heatmap_temporal.png"
        heatmap_temporal(df, datos.terminos, ruta=ruta)
        return {"descarga": f"/api/v1/descargas/{ruta.name}"}
    return _trabajo(lambda: W._lanzar_trabajo(ses, "mapa_calor", _fn))


class Red(BaseModel):
    categorias: list[str] | None = None
    peso_min: float = 2


@app.post("/api/v1/red", tags=["lectura_distante"])
def red(datos: Red, ses=Depends(sesion)):
    def _fn(trabajo):
        import networkx as nx

        from core.network_engine import construir_grafo, metricas_red
        if not ses.st.indice_ner_global:
            raise ValueError("No hay entidades: corre NER primero")
        G = construir_grafo(ses.st.indice_ner_global, categorias=datos.categorias,
                            peso_minimo=datos.peso_min,
                            callback=lambda m: trabajo.avanzar(None, str(m)))
        met = metricas_red(G)
        ses.st.metricas_red = met
        return {"metricas": met, "grafo": nx.node_link_data(G)}
    return _trabajo(lambda: W._lanzar_trabajo(ses, "red", _fn))


class Coref(BaseModel):
    entidad: str | None = None
    limite_docs: int = 30


@app.post("/api/v1/coref", tags=["lectura_distante"])
def coref(datos: Coref, ses=Depends(sesion)):
    def _fn(trabajo):
        from core.coref_engine import estadisticas_coref, resolver_correferencias
        textos = _textos(ses)[:datos.limite_docs]
        cadenas = []
        for i, texto in enumerate(textos):
            trabajo.avanzar(int(i / max(len(textos), 1) * 50), f"Correferencia {i + 1}/{len(textos)}")
            for c in resolver_correferencias(texto):
                c["doc_idx"] = i
                cadenas.append(c)
        if datos.entidad:
            cadenas = [c for c in cadenas
                      if datos.entidad.lower() in c["entidad_principal"].lower()]
        cadenas.sort(key=lambda x: -x.get("n_menciones", 0))
        stats = estadisticas_coref(textos, callback=lambda i, t: trabajo.avanzar(
            50 + int(i / max(t, 1) * 50)))
        return {"cadenas": cadenas[:200], "estadisticas": stats}
    return _trabajo(lambda: W._lanzar_trabajo(ses, "coref", _fn))


class Linguistica(BaseModel):
    tipo: str   # sint | svo | morf | dep | emo | frames | pol
    patron: str = ""
    max_resultados: int = 200
    solo_entidades: bool = False
    min_confianza: float = 0.5
    normalizar: bool = True
    articulo_idx: int = 0
    max_oraciones: int = 10


@app.post("/api/v1/linguistica", tags=["lectura_distante"])
def linguistica(datos: Linguistica, ses=Depends(sesion)):
    def _fn(trabajo):
        corpus = _textos(ses)
        cb = lambda *a: trabajo.avanzar(None, " ".join(str(x) for x in a))  # noqa: E731
        if datos.tipo == "sint":
            from core.sintaxis_engine import concordancias_sintaticas
            resultado = concordancias_sintaticas(corpus, patron=datos.patron,
                                                  max_resultados=datos.max_resultados, callback=cb)
        elif datos.tipo == "svo":
            from core.sintaxis_engine import extraer_relaciones
            resultado = extraer_relaciones(corpus, solo_entidades=datos.solo_entidades,
                                           min_confianza=datos.min_confianza, callback=cb)
        elif datos.tipo == "morf":
            from core.morfologia_historica import (
                enriquecer_corpus_con_lemas,
                normalizar_formas_historicas,
            )
            corpus_proc = ([normalizar_formas_historicas(t) for t in corpus]
                          if datos.normalizar else corpus)
            resultado = enriquecer_corpus_con_lemas(corpus_proc, callback=cb)
        elif datos.tipo == "dep":
            if datos.articulo_idx >= len(corpus):
                raise ValueError(f"El corpus tiene {len(corpus)} artículos (0–{len(corpus) - 1})")
            from core.sintaxis_engine import analizar_dependencias
            resultado = analizar_dependencias(corpus[datos.articulo_idx],
                                              max_oraciones=datos.max_oraciones)
        elif datos.tipo == "emo":
            from core.sentiment_engine import analisis_completo_emocion
            resultado = [{**analisis_completo_emocion(t), "doc_idx": i}
                        for i, t in enumerate(corpus)]
        elif datos.tipo == "frames":
            from core import frame_engine
            corpus_dict = {f"doc_{i + 1:04d}": t for i, t in enumerate(corpus)}
            resultado = frame_engine.analizar_corpus_frames(corpus_dict)
        elif datos.tipo == "pol":
            from core import sentimiento_discriminante as sd
            resultado = [{**sd.analizar_polaridad(t), "art_id": f"doc_{i + 1:04d}"}
                        for i, t in enumerate(corpus)]
        else:
            raise ValueError(f"tipo desconocido: {datos.tipo!r} "
                             "(usa sint|svo|morf|dep|emo|frames|pol)")
        return {"tipo": datos.tipo, "resultado": resultado}
    return _trabajo(lambda: W._lanzar_trabajo(ses, "linguistica", _fn))


class Canonico(BaseModel):
    accion: str   # fundir | menciones | okf
    nombre: str | None = None


@app.post("/api/v1/canonico", tags=["publicacion"])
def canonico(datos: Canonico, ses=Depends(sesion)):
    def _fn(trabajo):
        if not ses.st.ruta_db:
            raise ValueError("El proyecto no tiene base de datos (.db): guárdalo con DB "
                             "para usar el grafo canónico")
        from datos.repositorio import Repositorio
        repo = Repositorio(ses.st.ruta_db)
        if datos.accion == "fundir":
            res = repo.fundir_menciones_en_canonicas(fuente="ner")
            return {"accion": "fundir", "resultado": res,
                   "canonicas": repo.listar_entidades_canonicas()}
        if datos.accion == "menciones":
            filas = repo.menciones_canonicas_por_articulo()
            if not filas:
                raise ValueError("Funde primero las menciones en entidades canónicas")
            n = 0
            for cid, art in filas:
                repo.guardar_relacion(cid, "mencionado_en", destino_pagina=art,
                                      evidencia=art, fuente="ner")
                n += 1
            return {"accion": "menciones", "n_tripletas": n}
        if datos.accion == "okf":
            from core.okf_export_engine import exportar_proyecto_okf
            dest = ses.dir_trabajo / "exportes" / "okf"
            dest.mkdir(exist_ok=True)
            nombre = datos.nombre or ses.st.publicacion or "Corpus"
            res = exportar_proyecto_okf(repo, str(dest), nombre_proyecto=nombre)
            return {"accion": "okf", "resultado": res}
        raise ValueError(f"acción desconocida: {datos.accion!r} (usa fundir|menciones|okf)")
    return _trabajo(lambda: W._lanzar_trabajo(ses, "canonico", _fn))


class Reportes(BaseModel):
    tipo: str = "html"   # html | word


@app.post("/api/v1/reportes", tags=["publicacion"])
def reportes(datos: Reportes, ses=Depends(sesion)):
    def _fn(trabajo):
        stats_corpus = {
            "n_articulos": len(ses.articulos),
            "n_palabras_total": sum(len((a.get("texto") or "").split()) for a in ses.articulos),
            "proyecto": ses.st.publicacion or "Corpus",
        }
        if datos.tipo == "html":
            from core.storytelling_engine import generar_reporte_html
            ruta = ses.dir_trabajo / "exportes" / "reporte_bashkar.html"
            generar_reporte_html(proyecto_nombre=stats_corpus["proyecto"], stats_corpus=stats_corpus,
                                 indice_ner=ses.st.indice_ner_global or {}, stats_tono=None,
                                 metricas_red=ses.st.metricas_red or None, narrativas=None, ruta=ruta,
                                 callback=lambda m: trabajo.avanzar(None, str(m)))
        elif datos.tipo == "word":
            from core.storytelling_engine import exportar_word
            ruta = ses.dir_trabajo / "exportes" / "reporte_estampa.docx"
            exportar_word(proyecto_nombre=stats_corpus["proyecto"], stats_corpus=stats_corpus,
                         indice_ner=ses.st.indice_ner_global or {}, narrativas=None, ruta=ruta)
        else:
            raise ValueError(f"tipo desconocido: {datos.tipo!r} (usa html|word)")
        return {"descarga": f"/api/v1/descargas/{ruta.name}"}
    return _trabajo(lambda: W._lanzar_trabajo(ses, "reportes", _fn))


@app.post("/api/v1/paquete_publicacion", tags=["publicacion"])
def paquete_publicacion(ses=Depends(sesion)):
    def _fn(trabajo):
        import json as _json
        import tempfile
        import zipfile

        tmp = Path(tempfile.mkdtemp(dir=ses.dir_trabajo, prefix="pub_"))
        errores: list[str] = []
        contenido: list[str] = []
        corpus_txt = [a.get("texto", "") for a in ses.articulos]
        ner = ses.st.indice_ner_global or {}

        trabajo.avanzar(10, "Exportando TEI…")
        try:
            from core.servicios_exportacion import articulos_para_tei
            from core.tei_engine import exportar_corpus_tei
            arts_tei = articulos_para_tei(corpus_txt, ner)
            if arts_tei:
                exportar_corpus_tei(arts_tei, tmp / "corpus.xml",
                                    proyecto_nombre=ses.st.publicacion or "Corpus",
                                    investigador="Investigador", institucion="")
        except Exception as e:
            errores.append(f"TEI: {e}")

        trabajo.avanzar(30, "Exportando BibTeX…")
        try:
            from core.tei_engine import exportar_bibtex
            arts_bib = [{"id": f"art_{i:04d}", "texto": t} for i, t in enumerate(corpus_txt)]
            if arts_bib:
                exportar_bibtex(arts_bib, tmp / "corpus.bib")
        except Exception as e:
            errores.append(f"BibTeX: {e}")

        trabajo.avanzar(50, "Exportando entidades CSV…")
        try:
            from core.ner_engine import exportar_csv as _ner_csv
            if ner:
                _ner_csv(ner, tmp / "entidades.csv")
        except Exception as e:
            errores.append(f"CSV NER: {e}")

        trabajo.avanzar(70, "Escribiendo metadatos…")
        meta = {"publicacion": ses.st.publicacion or "", "periodo": ses.st.periodo or "",
               "bashkar_version": VERSION_API, "n_articulos": len(ses.articulos)}
        (tmp / "metadatos.json").write_text(_json.dumps(meta, ensure_ascii=False, indent=2),
                                            encoding="utf-8")

        trabajo.avanzar(85, "Generando METHODS.md…")
        try:
            from core.methods_reporter import generar_methods_md
            from core.servicios_exportacion import config_methods, estadisticas_methods
            generar_methods_md(config_methods(ses.st, VERSION_API), estadisticas_methods(ses.st),
                               tmp / "METHODS.md")
        except Exception as e:
            errores.append(f"METHODS.md: {e}")

        trabajo.avanzar(95, "Comprimiendo…")
        ruta_zip = ses.dir_trabajo / "exportes" / "paquete_publicacion.zip"
        with zipfile.ZipFile(ruta_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in tmp.rglob("*"):
                if f.is_file():
                    zf.write(f, f.relative_to(tmp))
                    contenido.append(f.relative_to(tmp).as_posix())
        esperados = {"corpus.xml", "corpus.bib", "entidades.csv", "metadatos.json", "METHODS.md"}
        faltan = sorted(esperados - set(contenido))
        if faltan and not errores:
            errores.append("Sin datos para: " + ", ".join(faltan))
        return {"descarga": f"/api/v1/descargas/{ruta_zip.name}", "contenido": sorted(contenido),
               "advertencias": errores}
    return _trabajo(lambda: W._lanzar_trabajo(ses, "paquete_publicacion", _fn))


class MejorarOCR(BaseModel):
    umbral: float = 0.7
    proveedor: str = "claude"
    modelo_ollama: str = "latamgpt"


@app.post("/api/v1/mejorar_ocr", tags=["ocr"])
def mejorar_ocr(datos: MejorarOCR, ses=Depends(sesion)):
    def _fn(trabajo):
        from core.ocr_llm import mejorar_lote
        od = ses.out_dir()
        if not od or ses.st.corpus_meta is None:
            raise ValueError("Crea o carga un proyecto con OCR ya hecho primero")
        if datos.proveedor == "ollama":
            api_key = ses.st.api_keys.get("ollama", "http://localhost:11434")
        elif datos.proveedor == "lmstudio":
            api_key = ses.st.api_keys.get("lmstudio", "http://localhost:1234")
        else:
            api_key = ses.st.api_key
        stats = mejorar_lote(
            corpus_meta=ses.st.corpus_meta, api_key=api_key, umbral_confianza=datos.umbral,
            img_dir_raiz=od / "02_imagenes", modo="auto", proveedor=datos.proveedor,
            modelo_ollama=datos.modelo_ollama,
            callback=lambda n, t, d: trabajo.avanzar(int(n / max(t, 1) * 100), f"{n}/{t} {d}"))
        return stats
    return _trabajo(lambda: W._lanzar_trabajo(ses, "mejorar_ocr", _fn))


@app.post("/api/v1/gutter", tags=["ocr"])
def gutter(ses=Depends(sesion)):
    def _fn(trabajo):
        from core.gutter_completion import estadisticas, reconstruir_texto
        od = ses.out_dir()
        if not od:
            raise ValueError("No hay proyecto")
        ocr_dir = od / "03_ocr"
        if not ocr_dir.exists():
            raise ValueError("No hay 03_ocr/: corre OCR primero")
        api_key = ses.st.api_keys.get("anthropic", "") or ses.st.api_key
        if not api_key:
            raise ValueError("Falta la clave de Anthropic")
        modelo = "claude-haiku-4-5-20251001"
        total_fragmentos = total_reconstruidos = 0
        txt_dirs = [d for d in ocr_dir.iterdir() if d.is_dir()]
        for txt_dir in txt_dirs:
            for txt_path in sorted(txt_dir.glob("*.txt")):
                texto = txt_path.read_text("utf-8", errors="replace")
                texto_rec, frags = reconstruir_texto(texto, api_key, modelo)
                stats = estadisticas(frags)
                if stats["reconstruidos"] > 0:
                    backup = txt_path.with_suffix(".txt.orig")
                    if not backup.exists():
                        backup.write_text(texto, encoding="utf-8")
                    txt_path.write_text(texto_rec, encoding="utf-8")
                    total_fragmentos += stats["total_fragmentos"]
                    total_reconstruidos += stats["reconstruidos"]
                    trabajo.avanzar(None, f"{txt_path.stem}: "
                                    f"{stats['reconstruidos']}/{stats['total_fragmentos']}")
        return {"fragmentos": total_fragmentos, "reconstruidos": total_reconstruidos}
    return _trabajo(lambda: W._lanzar_trabajo(ses, "gutter", _fn))


@app.post("/api/v1/vision", tags=["ocr"])
def vision(ses=Depends(sesion)):
    def _fn(trabajo):
        from core.image_analyzer import analizar_numero_imagenes
        od = ses.out_dir()
        if not od or ses.st.corpus_meta is None:
            raise ValueError("No hay imágenes de páginas: corre OCR primero")
        img_dir, ocr_dir = od / "02_imagenes", od / "03_ocr"
        numeros = sorted(ses.st.corpus_meta["numero"].unique())
        api_key = ses.st.api_keys.get("anthropic", "") or ses.st.api_key
        datos_num: dict = {}
        for k, nombre in enumerate(numeros):
            trabajo.avanzar(int(k / max(len(numeros), 1) * 100), f"{nombre} ({k + 1}/{len(numeros)})")
            imgd = img_dir / nombre
            if not imgd.exists():
                continue
            r = analizar_numero_imagenes(imgd, ocr_dir, nombre, dpi=300, api_key=api_key,
                                         max_ia=15 if api_key else 0,
                                         callback=lambda m: trabajo.avanzar(None, str(m)))
            if r:
                datos_num[nombre] = r
        ses.st.datos_visual = {"visual_elementos": datos_num}
        return {"numeros_con_imagenes": list(datos_num.keys()), "datos": datos_num}
    return _trabajo(lambda: W._lanzar_trabajo(ses, "vision", _fn))


@app.post("/api/v1/comparar", tags=["publicacion"])
def comparar(ses=Depends(sesion)):
    """Compara el corpus con publicaciones de referencia en disco: solo tiene
    sentido en modo local (lee una carpeta del servidor, no de la sesión)."""
    if W.MODO_PUBLICO:
        raise HTTPException(403, "Compara carpetas del servidor: solo en modo local")
    ref = ses.st.api_keys.get("comparar_ref_dir", "")
    if not ref:
        raise HTTPException(400, "Configura la carpeta de referencia (ref_dir) primero")

    def _fn(trabajo):
        from core.comparative_analyzer import cargar_corpora, generar_reporte_comparativo
        from gui_comun import CAMPOS_DEFAULT
        nombre_foco = ses.st.publicacion or "Corpus"
        corpus_principal = {nombre_foco: "\n".join(_textos(ses))}
        trabajo.avanzar(10, "Cargando corpora de referencia…")
        corpora = cargar_corpora(Path(ref), corpus_principal)
        if len(corpora) < 2:
            raise ValueError("Se necesitan al menos 2 publicaciones para comparar")
        trabajo.avanzar(50, "Calculando similaridad y palabras distintivas…")
        campos = getattr(ses.st, "campos_expandidos", None) or \
            getattr(ses.st, "campos_semillas", None) or CAMPOS_DEFAULT
        reporte = generar_reporte_comparativo(nombre_foco, corpora, campos)
        return {"publicaciones": list(corpora.keys()), "reporte": reporte}
    return _trabajo(lambda: W._lanzar_trabajo(ses, "comparar", _fn))
