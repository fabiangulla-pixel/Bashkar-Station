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
