"""
servidor_web.py — Bashkar Station Web

Segundo frontend de Bashkar Station: una interfaz web que comparte el 100%
de la lógica de negocio con la app de escritorio (app.py, Tkinter). No es
una reescritura — ambos frontends consumen los mismos módulos core/ y la
misma clase Estado (core/estado.py).

Backend HTTP de stdlib pura (http.server), sin frameworks. Frontend vanilla
en web/ (sin npm, sin build).

Modos:
  Local (defecto)   python servidor_web.py            → un solo usuario,
                    estado global, acceso a rutas del disco local.
  Público           BASHKAR_PASSWORD=xxx python servidor_web.py
                    → multi-sesión con login, una sesión aislada por visitante,
                    sin acceso a rutas del servidor ni escritura compartida.

El puerto lo define la variable PORT (Render la inyecta); defecto 8421.
"""

import json
import os
import re
import secrets
import shutil
import sys
import tempfile
import threading
import time
import traceback
import uuid
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from core.estado import Estado

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════════════════════
VERSION_WEB = "1.0"
BASE_DIR = Path(__file__).parent
WEB_DIR = BASE_DIR / "web"
PUERTO = int(os.environ.get("PORT", 8421))
PASSWORD = os.environ.get("BASHKAR_PASSWORD", "")
MODO_PUBLICO = bool(PASSWORD)
SESION_TTL_S = 6 * 3600  # barrer sesiones sin actividad tras 6 h
_BARRIDO_CADA = 600  # chequeo perezoso de barrido cada 10 min

_MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


# ══════════════════════════════════════════════════════════════════════════════
# CAPACIDADES DEL HOST
# ══════════════════════════════════════════════════════════════════════════════
_CAPACIDADES: dict | None = None


def detectar_capacidades() -> dict:
    """Detecta qué motores están disponibles en ESTE host.

    El frontend deshabilita (con razón visible) lo que no esté: en un
    despliegue Render no hay Tesseract ni Poppler, pero el pipeline de
    texto embebido (PyMuPDF) y los análisis funcionan completos.
    """
    global _CAPACIDADES
    if _CAPACIDADES is not None:
        return _CAPACIDADES

    caps: dict[str, dict] = {}

    def _probar(nombre, fn, detalle_ok="disponible"):
        try:
            res = fn()
            caps[nombre] = {
                "disponible": bool(res),
                "detalle": detalle_ok if res else "no disponible",
            }
        except Exception as e:
            caps[nombre] = {"disponible": False, "detalle": str(e)[:120]}

    def _hay_tesseract():
        if shutil.which("tesseract"):
            return True
        from core.ocr_engine import _get_tesseract_cmd

        return bool(_get_tesseract_cmd())

    _probar("tesseract", _hay_tesseract)

    def _hay_poppler():
        # Se pregunta por lo mismo que usará el OCR, no solo por el PATH: en
        # macOS, un proceso lanzado desde Finder no ve Homebrew, y el
        # diagnóstico diría "falta poppler" cuando en realidad sí se encuentra.
        if shutil.which("pdftoppm"):
            return True
        if (BASE_DIR / "poppler_path.txt").exists():
            return True
        from core.plataforma import buscar_poppler

        return bool(buscar_poppler())

    _probar("poppler", _hay_poppler)
    _probar("pymupdf", lambda: __import__("fitz") and True)
    _probar("python_docx", lambda: __import__("docx") and True)

    def _hay_spacy_es():
        import spacy.util

        return any(
            spacy.util.is_package(m)
            for m in ("es_core_news_sm", "es_core_news_md", "es_core_news_lg")
        )

    _probar("spacy_es", _hay_spacy_es)
    _probar("pandas", lambda: __import__("pandas") and True)

    # Los proveedores locales de IA no existen en un servidor remoto
    caps["proveedores_locales"] = {
        "disponible": not MODO_PUBLICO,
        "detalle": "ollama/lmstudio solo en modo local" if MODO_PUBLICO else "disponible",
    }
    _CAPACIDADES = caps
    return caps


# ══════════════════════════════════════════════════════════════════════════════
# TRABAJOS (workers en hilo + polling de progreso)
# ══════════════════════════════════════════════════════════════════════════════
class Trabajo:
    def __init__(self, tipo: str):
        self.id = uuid.uuid4().hex[:12]
        self.tipo = tipo
        self.estado = "corriendo"  # corriendo | ok | error
        self.progreso = 0  # 0-100
        self.mensaje = ""
        self.log: list[str] = []
        self.resultado: dict = {}
        self.error = ""
        self._lock = threading.Lock()

    def avanzar(self, progreso: int | None = None, mensaje: str = ""):
        with self._lock:
            if progreso is not None:
                self.progreso = max(0, min(100, int(progreso)))
            if mensaje:
                self.mensaje = mensaje
                self.log.append(mensaje)
                if len(self.log) > 400:
                    del self.log[:100]

    def terminar(self, resultado: dict | None = None):
        with self._lock:
            self.estado = "ok"
            self.progreso = 100
            self.resultado = resultado or {}

    def fallar(self, error: str):
        with self._lock:
            self.estado = "error"
            self.error = error
            self.log.append(f"ERROR: {error}")

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "id": self.id,
                "tipo": self.tipo,
                "estado": self.estado,
                "progreso": self.progreso,
                "mensaje": self.mensaje,
                "log": self.log[-30:],
                "resultado": self.resultado,
                "error": self.error,
            }


# ══════════════════════════════════════════════════════════════════════════════
# ESTADO POR SESIÓN
# ══════════════════════════════════════════════════════════════════════════════
class EstadoServidor:
    """Envuelve todo lo que en la app de escritorio vive como atributos de la
    ventana Tkinter: el Estado del proyecto + artículos segmentados + trabajos
    en curso + carpeta de trabajo propia."""

    def __init__(self):
        self.st = Estado()
        self.ruta_proyecto: Path | None = None
        self.articulos: list[dict] = []
        self.analisis: dict = {}
        self.trabajos: dict[str, Trabajo] = {}
        self.lock = threading.Lock()
        self.ultimo_uso = time.time()
        self.dir_trabajo = Path(tempfile.mkdtemp(prefix="bashkar_web_"))
        (self.dir_trabajo / "subidas").mkdir(exist_ok=True)
        (self.dir_trabajo / "exportes").mkdir(exist_ok=True)
        (self.dir_trabajo / "proyectos").mkdir(exist_ok=True)

    def tocar(self):
        self.ultimo_uso = time.time()

    def out_dir(self) -> Path | None:
        od = self.st.out_dir
        return Path(od) if od else None

    def limpiar(self):
        try:
            shutil.rmtree(self.dir_trabajo, ignore_errors=True)
        except Exception:
            pass


# Modo local: una única instancia global (mismo comportamiento que el escritorio)
ESTADO_LOCAL = EstadoServidor() if not MODO_PUBLICO else None

# Modo público: sesiones por cookie
SESIONES: dict[str, EstadoServidor] = {}
_SESIONES_LOCK = threading.Lock()
_ultimo_barrido = time.time()


def _barrer_sesiones():
    """Barrido perezoso: libera memoria y archivos de sesiones inactivas."""
    global _ultimo_barrido
    ahora = time.time()
    if ahora - _ultimo_barrido < _BARRIDO_CADA:
        return
    _ultimo_barrido = ahora
    with _SESIONES_LOCK:
        muertas = [sid for sid, s in SESIONES.items() if ahora - s.ultimo_uso > SESION_TTL_S]
        for sid in muertas:
            SESIONES.pop(sid).limpiar()


# ══════════════════════════════════════════════════════════════════════════════
# LÓGICA DE NEGOCIO (puentes a core/, sin HTTP)
# ══════════════════════════════════════════════════════════════════════════════
def _sanear_nombre(nombre: str) -> str:
    nombre = Path(nombre.replace("\\", "/")).name
    return re.sub(r"[^\w.\- ]", "_", nombre).strip() or "archivo"


def _snapshot_estado(ses: EstadoServidor) -> dict:
    st = ses.st
    od = ses.out_dir()
    numeros = []
    if od and (od / "03_ocr").is_dir():
        for d in sorted((od / "03_ocr").iterdir()):
            if d.is_dir():
                numeros.append({"nombre": d.name, "paginas": len(list(d.glob("*.txt")))})
    n_ents = sum(len(v) for v in st.indice_ner_global.values() if isinstance(v, dict))
    return {
        "proyecto": ses.ruta_proyecto.stem if ses.ruta_proyecto else None,
        "ruta_proyecto": str(ses.ruta_proyecto)
        if (ses.ruta_proyecto and not MODO_PUBLICO)
        else None,
        "publicacion": st.publicacion,
        "periodo": st.periodo,
        "out_dir": str(od) if (od and not MODO_PUBLICO) else None,
        "estado_etapas": st.estado_etapas,
        "numeros": numeros,
        "n_articulos": len(ses.articulos),
        "n_entidades": n_ents,
        "ner_done": st.ner_done,
        "ia_habilitada": st.ia_habilitada,
    }


def _listar_proyectos(ses: EstadoServidor) -> list[dict]:
    if MODO_PUBLICO:
        res = []
        for p in sorted((ses.dir_trabajo / "proyectos").glob("*.bashkar")):
            try:
                datos = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                datos = {}
            res.append(
                {
                    "nombre": datos.get("nombre", p.stem),
                    "ruta": p.name,
                    "modificado": datos.get("modificado", ""),
                }
            )
        return res
    from core import project_manager as pm

    proys = pm.listar_proyectos()
    for p in proys:
        p["ruta"] = str(p.get("ruta", ""))
    return proys


def _crear_proyecto(ses: EstadoServidor, nombre: str, publicacion: str, periodo: str) -> Path:
    from core import project_manager as pm

    if MODO_PUBLICO:
        slug = re.sub(r"[^\w\-]", "_", nombre.strip().lower()) or "proyecto"
        ruta = ses.dir_trabajo / "proyectos" / f"{slug}.bashkar"
        ses.st.reset()
        ses.st.publicacion = publicacion or nombre
        ses.st.periodo = periodo
        ses.st.out_dir = str(ses.dir_trabajo / "salida" / slug)
        Path(ses.st.out_dir).mkdir(parents=True, exist_ok=True)
        _guardar_proyecto_seguro(ses, ruta)
        ses.ruta_proyecto = ruta
        ses.articulos, ses.analisis = [], {}
        return ruta
    ruta = pm.nuevo_proyecto(nombre, publicacion or nombre, periodo)
    ses.st.reset()
    pm.cargar_proyecto(ruta, ses.st)
    # nuevo_proyecto guarda publicacion/periodo en el nivel superior del
    # .bashkar, pero cargar_proyecto los lee de config (vacío en un proyecto
    # recién creado) — igual que el escritorio, la UI aporta los valores.
    ses.st.publicacion = publicacion or nombre
    ses.st.periodo = periodo
    if not ses.st.out_dir:
        salida = ruta.parent / f"{ruta.stem}_salida"
        salida.mkdir(parents=True, exist_ok=True)
        ses.st.out_dir = str(salida)
    _guardar_proyecto_seguro(ses, ruta)
    ses.ruta_proyecto = ruta
    ses.articulos, ses.analisis = [], {}
    return ruta


def _cargar_proyecto(ses: EstadoServidor, ruta_txt: str):
    from core import project_manager as pm

    if MODO_PUBLICO:
        # Solo proyectos de la propia sesión, nunca rutas arbitrarias del servidor
        ruta = (ses.dir_trabajo / "proyectos" / _sanear_nombre(ruta_txt)).resolve()
        if not ruta.is_relative_to(ses.dir_trabajo.resolve()) or not ruta.exists():
            raise FileNotFoundError("Proyecto no encontrado en esta sesión")
    else:
        ruta = Path(ruta_txt)
        if not ruta.exists():
            raise FileNotFoundError(f"No existe: {ruta_txt}")
    ses.st.reset()
    pm.cargar_proyecto(ruta, ses.st)
    ses.ruta_proyecto = ruta
    ses.articulos, ses.analisis = [], {}


def _guardar_proyecto_seguro(ses: EstadoServidor, ruta: Path | None = None):
    """Guarda el .bashkar. En modo público NUNCA persiste claves de API."""
    from core import project_manager as pm

    ruta = ruta or ses.ruta_proyecto
    if not ruta:
        raise ValueError("No hay proyecto activo")
    st = ses.st
    if MODO_PUBLICO:
        claves, clave1 = st.api_keys, st.api_key
        st.api_keys = {k: "" for k in claves}
        st.api_key = ""
        try:
            pm.guardar_proyecto(ruta, st)
        finally:
            st.api_keys, st.api_key = claves, clave1
    else:
        pm.guardar_proyecto(ruta, st)


def _lanzar_trabajo(ses: EstadoServidor, tipo: str, fn) -> Trabajo:
    """Arranca `fn(trabajo)` en un hilo daemon y registra el trabajo."""
    trabajo = Trabajo(tipo)
    with ses.lock:
        ses.trabajos[trabajo.id] = trabajo

    def _correr():
        try:
            resultado = fn(trabajo)
            trabajo.terminar(resultado if isinstance(resultado, dict) else {})
        except Exception as e:
            traceback.print_exc()
            trabajo.fallar(f"{type(e).__name__}: {e}")

    threading.Thread(target=_correr, daemon=True).start()
    return trabajo


def _trabajo_convertir(ses: EstadoServidor, carpeta_entrada: Path):
    """Conversor PDF→TXT (texto embebido, PyMuPDF) alimentando 03_ocr/."""
    from core.conversor_pdf_a_word import ConfiguracionConversor, ConversorPDFaWord

    od = ses.out_dir()
    if not od:
        raise ValueError("El proyecto no tiene carpeta de salida")
    od.mkdir(parents=True, exist_ok=True)

    def _fn(trabajo: Trabajo):
        cfg = ConfiguracionConversor(
            carpeta_entrada=carpeta_entrada,
            carpeta_salida=ses.dir_trabajo / "conv",
            fragmentar_pdf=False,
            word_consolidado=False,
            word_por_pagina=False,
            txt_consolidado=True,
            txt_por_pagina=False,
            copiar_original=False,
            limpiar_texto=True,
            exportar_para_normalizar=True,
            carpeta_out_dir=od,
        )

        def _cb(evento: dict):
            trabajo.avanzar(evento.get("porcentaje"), evento.get("mensaje", ""))

        conv = ConversorPDFaWord(cfg, callback_progreso=_cb)
        resumen = conv.procesar_todo()
        ses.st.marcar_etapa("ocr", "ready")
        ses.st.ocr_done = True
        return {
            "resumen": {
                k: v for k, v in (resumen or {}).items() if isinstance(v, (int, str, float))
            }
        }

    return _lanzar_trabajo(ses, "conv", _fn)


def _trabajo_normalizar(ses: EstadoServidor, numero: str | None):
    from core.ocr_normalizer import normalizar_directorio

    od = ses.out_dir()
    if not od or not (od / "03_ocr").is_dir():
        raise ValueError("No hay textos en 03_ocr — convierte o extrae primero")
    dirs = [d for d in sorted((od / "03_ocr").iterdir()) if d.is_dir()]
    if numero:
        dirs = [d for d in dirs if d.name == numero]
        if not dirs:
            raise ValueError(f"Número no encontrado: {numero}")

    def _fn(trabajo: Trabajo):
        total = {"archivos": 0, "palabras_cambiadas": 0, "guiones_unidos": 0, "errores": 0}
        for i, d in enumerate(dirs):
            trabajo.avanzar(int(i / max(1, len(dirs)) * 100), f"Normalizando {d.name}…")
            stats = normalizar_directorio(d)
            for k in total:
                total[k] += stats.get(k, 0)
        ses.st.marcar_etapa("norm", "ready")
        ses.st.norm_done = True
        return total

    return _lanzar_trabajo(ses, "norm", _fn)


def _trabajo_segmentar(ses: EstadoServidor):
    from core.article_segmenter import segmentar_numero

    od = ses.out_dir()
    if not od or not (od / "03_ocr").is_dir():
        raise ValueError("No hay textos en 03_ocr — convierte o extrae primero")
    dirs = [d for d in sorted((od / "03_ocr").iterdir()) if d.is_dir()]
    if not dirs:
        raise ValueError("03_ocr está vacío")

    def _fn(trabajo: Trabajo):
        # segmentar_numero(ocr_dir, nombre) reconstruye la ruta como
        # ocr_dir/nombre — hay que pasarle el PADRE "03_ocr", no la carpeta
        # del número (pasar esta última duplicaba el segmento de ruta y la
        # carpeta resultante nunca existía, así que siempre volvía vacío).
        raiz = od / "03_ocr"
        articulos: list[dict] = []
        for i, d in enumerate(dirs):
            trabajo.avanzar(int(i / len(dirs) * 100), f"Segmentando {d.name}…")
            arts = segmentar_numero(raiz, d.name)
            articulos.extend(arts)
        for i, a in enumerate(articulos):
            a.setdefault("id", f"doc_{i:04d}")
        with ses.lock:
            ses.articulos = articulos
        ses.st.corpus_txt = [a.get("texto", "") for a in articulos]
        ses.st.marcar_etapa("seg", "ready")
        ses.st.seg_done = True
        return {"n_articulos": len(articulos)}

    return _lanzar_trabajo(ses, "seg", _fn)


_STOPWORDS_MIN = {
    "de",
    "la",
    "el",
    "en",
    "y",
    "a",
    "que",
    "los",
    "del",
    "se",
    "las",
    "por",
    "un",
    "con",
    "no",
    "una",
    "su",
    "para",
    "es",
    "al",
    "lo",
    "como",
    "más",
    "mas",
    "o",
    "pero",
    "sus",
    "le",
    "ha",
    "me",
    "si",
    "sin",
    "sobre",
    "este",
    "ya",
    "entre",
    "cuando",
    "todo",
    "esta",
    "ser",
    "son",
    "dos",
    "también",
    "fue",
    "había",
    "era",
    "muy",
    "años",
    "hasta",
    "desde",
    "está",
    "mi",
    "porque",
    "qué",
    "sólo",
    "han",
    "yo",
    "hay",
    "vez",
    "puede",
    "todos",
    "así",
    "nos",
    "ni",
    "parte",
    "tiene",
    "él",
    "uno",
    "donde",
    "bien",
    "tiempo",
    "mismo",
    "ese",
    "ahora",
    "cada",
    "e",
    "vida",
    "otro",
    "después",
    "te",
    "otros",
    "aunque",
    "esa",
    "eso",
    "hace",
    "otra",
    "gobierno",
    "tan",
    "durante",
    "siempre",
    "día",
    "tanto",
    "ella",
    "tres",
    "sí",
    "dijo",
    "sido",
    "gran",
    "país",
    "según",
    "menos",
    "año",
    "antes",
    "estado",
    "quien",
    "les",
}


def _trabajo_analizar(ses: EstadoServidor):
    """Análisis léxico básico del corpus segmentado (primer tramo web).

    LDA/campos semánticos/word2vec siguen en el escritorio; se portan en el
    siguiente tramo.
    """
    if not ses.articulos:
        raise ValueError("No hay artículos — segmenta primero")

    def _fn(trabajo: Trabajo):
        from collections import Counter

        stop = _STOPWORDS_MIN | {w.lower() for w in ses.st.stopwords_proyecto}
        frec: Counter = Counter()
        secciones: Counter = Counter()
        por_numero: Counter = Counter()
        total_palabras = 0
        for i, a in enumerate(ses.articulos):
            if i % 25 == 0:
                trabajo.avanzar(
                    int(i / len(ses.articulos) * 100), f"Analizando {i}/{len(ses.articulos)}…"
                )
            texto = (a.get("texto") or "").lower()
            palabras = re.findall(r"[a-záéíóúüñ]{3,}", texto)
            total_palabras += len(palabras)
            frec.update(p for p in palabras if p not in stop)
            secciones[a.get("seccion", "—")] += 1
            por_numero[a.get("numero", "—")] += 1
        resultado = {
            "top_terminos": frec.most_common(60),
            "secciones": secciones.most_common(),
            "por_numero": por_numero.most_common(),
            "n_articulos": len(ses.articulos),
            "total_palabras": total_palabras,
            "vocabulario": len(frec),
        }
        with ses.lock:
            ses.analisis = resultado
        ses.st.marcar_etapa("anal", "ready")
        ses.st.anal_done = True
        return {"n_articulos": len(ses.articulos), "vocabulario": len(frec)}

    return _lanzar_trabajo(ses, "anal", _fn)


def _trabajo_ner(ses: EstadoServidor):
    if not ses.articulos:
        raise ValueError("No hay artículos — segmenta primero")
    caps = detectar_capacidades()
    if not caps["spacy_es"]["disponible"]:
        raise ValueError("spaCy español no está instalado en este servidor")

    def _fn(trabajo: Trabajo):
        import spacy

        from core.ner_engine import (
            actualizar_indice_global,
            indice_global_vacio,
            pipeline_ner,
        )

        trabajo.avanzar(2, "Cargando modelo spaCy…")
        nlp = None
        for m in ("es_core_news_lg", "es_core_news_md", "es_core_news_sm"):
            try:
                nlp = spacy.load(m)
                break
            except Exception:
                continue
        if nlp is None:
            raise ValueError("No se pudo cargar ningún modelo spaCy es_core_news_*")
        indice = indice_global_vacio()
        for i, art in enumerate(ses.articulos):
            if i % 10 == 0:
                trabajo.avanzar(
                    5 + int(i / len(ses.articulos) * 90), f"NER {i}/{len(ses.articulos)}…"
                )
            texto = art.get("texto", "")
            if not texto:
                continue
            try:
                ner = pipeline_ner(texto, nlp)
                actualizar_indice_global(indice, art.get("id", str(i)), ner)
            except Exception:
                continue
        ses.st.indice_ner_global = indice
        ses.st.ner_done = True
        n = sum(len(v) for v in indice.values() if isinstance(v, dict))
        return {"n_entidades": n}

    return _lanzar_trabajo(ses, "ner", _fn)


def _exportar(ses: EstadoServidor, formato: str) -> Path:
    """Genera un exporte en la carpeta de la sesión y devuelve la ruta."""
    destino = ses.dir_trabajo / "exportes"
    destino.mkdir(exist_ok=True)
    arts = [
        {
            "id": a.get("id", str(i)),
            "texto": a.get("texto", ""),
            "titulo": a.get("titulo", ""),
            "autor": a.get("autor", ""),
        }
        for i, a in enumerate(ses.articulos)
    ]

    if formato == "tei":
        from core.tei_engine import exportar_corpus_tei

        ruta = destino / "corpus_tei.xml"
        exportar_corpus_tei(arts, ruta, titulo=ses.st.publicacion, fecha=ses.st.periodo)
        return ruta
    if formato == "bibtex":
        from core.tei_engine import exportar_bibtex

        ruta = destino / "corpus.bib"
        exportar_bibtex(arts, ruta)
        return ruta
    if formato == "csv_ner":
        from core.ner_engine import exportar_csv

        if not ses.st.indice_ner_global:
            raise ValueError("No hay índice NER — corre NER primero")
        ruta = destino / "entidades.csv"
        exportar_csv(ses.st.indice_ner_global, ruta)
        return ruta
    if formato == "csv_articulos":
        import csv

        if not ses.articulos:
            raise ValueError("No hay artículos segmentados")
        ruta = destino / "articulos.csv"
        campos = ["id", "numero", "titulo", "autor", "seccion", "palabras", "tipo_pagina"]
        with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
            w.writeheader()
            for a in ses.articulos:
                fila = {k: a.get(k, "") for k in campos}
                fila["palabras"] = a.get("palabras", len((a.get("texto") or "").split()))
                w.writerow(fila)
        return ruta
    raise ValueError(f"Formato desconocido: {formato}")


# ══════════════════════════════════════════════════════════════════════════════
# GUÍAS DE MÓDULOS (reuso directo de core/guia_modulos.py)
# ══════════════════════════════════════════════════════════════════════════════
def _guias_json() -> dict:
    from core.guia_modulos import GUIA_MODULOS

    return GUIA_MODULOS


# ══════════════════════════════════════════════════════════════════════════════
# HANDLER HTTP
# ══════════════════════════════════════════════════════════════════════════════
RUTAS_SIN_SESION = {"/api/login", "/api/sesion", "/api/capacidades"}


class ManejadorAPI(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "BashkarWeb/" + VERSION_WEB

    # ── infraestructura ──────────────────────────────────────────────────────
    def log_message(self, fmt, *args):  # silenciar log de acceso
        pass

    def _json(self, payload, status: int = 200, extra_headers: dict | None = None):
        cuerpo = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(cuerpo)

    def _error(self, msg: str, status: int = 400):
        self._json({"error": msg}, status)

    def _cookie_sid(self) -> str | None:
        c = SimpleCookie(self.headers.get("Cookie", ""))
        return c["sid"].value if "sid" in c else None

    def _sesion(self) -> EstadoServidor | None:
        """Sesión del solicitante. En modo local siempre existe (global)."""
        if not MODO_PUBLICO:
            ESTADO_LOCAL.tocar()
            return ESTADO_LOCAL
        sid = self._cookie_sid()
        if not sid:
            return None
        with _SESIONES_LOCK:
            ses = SESIONES.get(sid)
        if ses:
            ses.tocar()
        return ses

    def _set_cookie_sesion(self) -> tuple[str, dict]:
        sid = secrets.token_urlsafe(32)
        atributos = "HttpOnly; Path=/; SameSite=Lax"
        # Secure solo detrás de TLS real — un Secure incondicional rompe el
        # login sobre HTTP plano en pruebas locales (la cookie nunca vuelve).
        if self.headers.get("X-Forwarded-Proto") == "https":
            atributos += "; Secure"
        return sid, {"Set-Cookie": f"sid={sid}; {atributos}"}

    # ── GET ──────────────────────────────────────────────────────────────────
    def do_GET(self):
        try:
            _barrer_sesiones()
            parsed = urlparse(self.path)
            ruta = parsed.path
            qs = {k: v[0] for k, v in parse_qs(parsed.query).items()}
            if ruta.startswith("/api/"):
                self._api_get(ruta, qs)
            else:
                self._servir_estatico(ruta)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            traceback.print_exc()
            try:
                self._error("Error interno del servidor", 500)
            except Exception:
                pass

    def _api_get(self, ruta: str, qs: dict):
        if ruta == "/api/sesion":
            ses = self._sesion()
            self._json(
                {
                    "modo_publico": MODO_PUBLICO,
                    "autenticado": ses is not None,
                    "version": VERSION_WEB,
                }
            )
            return
        if ruta == "/api/capacidades":
            self._json(detectar_capacidades())
            return

        ses = self._sesion()
        if ses is None:
            self._error("Sesión requerida", 401)
            return

        if ruta == "/api/estado":
            self._json(_snapshot_estado(ses))
        elif ruta == "/api/guias":
            self._json(_guias_json())
        elif ruta == "/api/proyectos":
            self._json(_listar_proyectos(ses))
        elif ruta == "/api/pagina":
            self._get_pagina(ses, qs)
        elif ruta == "/api/articulos":
            resumen = [
                {
                    "i": i,
                    "id": a.get("id"),
                    "numero": a.get("numero", ""),
                    "titulo": a.get("titulo", ""),
                    "autor": a.get("autor", ""),
                    "seccion": a.get("seccion", ""),
                    "palabras": a.get("palabras", len((a.get("texto") or "").split())),
                }
                for i, a in enumerate(ses.articulos)
            ]
            self._json(resumen)
        elif ruta == "/api/articulo":
            try:
                i = int(qs.get("i", "-1"))
                self._json(ses.articulos[i])
            except (ValueError, IndexError):
                self._error("Artículo no encontrado", 404)
        elif ruta == "/api/ner":
            self._json(ses.st.indice_ner_global)
        elif ruta == "/api/analisis":
            self._json(ses.analisis)
        elif ruta == "/api/trabajo":
            with ses.lock:
                t = ses.trabajos.get(qs.get("id", ""))
            if t is None:
                self._error("Trabajo no encontrado", 404)
            else:
                self._json(t.snapshot())
        elif ruta == "/api/descargar":
            self._get_descargar(ses, qs)
        else:
            self._error("Ruta no encontrada", 404)

    def _get_pagina(self, ses: EstadoServidor, qs: dict):
        od = ses.out_dir()
        numero = _sanear_nombre(qs.get("numero", ""))
        pagina = _sanear_nombre(qs.get("pagina", ""))
        if not od or not numero or not pagina:
            self._error("Faltan parámetros numero/pagina")
            return
        ruta = (od / "03_ocr" / numero / pagina).resolve()
        if not ruta.is_relative_to((od / "03_ocr").resolve()) or not ruta.exists():
            self._error("Página no encontrada", 404)
            return
        self._json(
            {
                "numero": numero,
                "pagina": pagina,
                "texto": ruta.read_text(encoding="utf-8", errors="replace"),
            }
        )

    def _get_descargar(self, ses: EstadoServidor, qs: dict):
        nombre = _sanear_nombre(qs.get("nombre", ""))
        ruta = (ses.dir_trabajo / "exportes" / nombre).resolve()
        if not ruta.is_relative_to(ses.dir_trabajo.resolve()) or not ruta.exists():
            self._error("Archivo no encontrado", 404)
            return
        datos = ruta.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Disposition", f'attachment; filename="{nombre}"')
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def _servir_estatico(self, ruta: str):
        if ruta in ("/", ""):
            ruta = "/index.html"
        destino = (WEB_DIR / ruta.lstrip("/")).resolve()
        if not destino.is_relative_to(WEB_DIR.resolve()) or not destino.is_file():
            self._error("No encontrado", 404)
            return
        datos = destino.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", _MIME.get(destino.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    # ── POST ─────────────────────────────────────────────────────────────────
    def do_POST(self):
        try:
            _barrer_sesiones()
            ruta = urlparse(self.path).path
            # El body se lee EXACTAMENTE UNA VEZ aquí, antes de despachar.
            # En HTTP/1.1 con keep-alive, bytes sin consumir (o una segunda
            # lectura) desincronizan la SIGUIENTE petición de la conexión.
            largo = int(self.headers.get("Content-Length", 0) or 0)
            cuerpo = self.rfile.read(largo) if largo else b""
            self._api_post(ruta, cuerpo)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            traceback.print_exc()
            try:
                self._error("Error interno del servidor", 500)
            except Exception:
                pass

    def _api_post(self, ruta: str, cuerpo: bytes):
        if ruta == "/api/login":
            self._post_login(cuerpo)
            return

        ses = self._sesion()
        if ses is None and ruta not in RUTAS_SIN_SESION:
            self._error("Sesión requerida", 401)
            return

        if ruta == "/api/subir":
            self._post_subir(ses, cuerpo)
            return

        # Resto de rutas: body JSON
        try:
            datos = json.loads(cuerpo.decode("utf-8")) if cuerpo else {}
        except json.JSONDecodeError:
            self._error("Body JSON inválido")
            return

        try:
            if ruta == "/api/proyecto/nuevo":
                nombre = (datos.get("nombre") or "").strip()
                if not nombre:
                    self._error("Falta el nombre del proyecto")
                    return
                _crear_proyecto(ses, nombre, datos.get("publicacion", ""), datos.get("periodo", ""))
                self._json(_snapshot_estado(ses))
            elif ruta == "/api/proyecto/cargar":
                _cargar_proyecto(ses, datos.get("ruta", ""))
                self._json(_snapshot_estado(ses))
            elif ruta == "/api/proyecto/guardar":
                _guardar_proyecto_seguro(ses)
                self._json({"ok": True})
            elif ruta == "/api/config":
                self._post_config(ses, datos)
            elif ruta == "/api/conv/iniciar":
                self._post_conv(ses, datos)
            elif ruta == "/api/norm/iniciar":
                t = _trabajo_normalizar(ses, datos.get("numero") or None)
                self._json({"trabajo": t.id})
            elif ruta == "/api/seg/iniciar":
                t = _trabajo_segmentar(ses)
                self._json({"trabajo": t.id})
            elif ruta == "/api/anal/iniciar":
                t = _trabajo_analizar(ses)
                self._json({"trabajo": t.id})
            elif ruta == "/api/ner/iniciar":
                t = _trabajo_ner(ses)
                self._json({"trabajo": t.id})
            elif ruta == "/api/exportar":
                salida = _exportar(ses, datos.get("formato", ""))
                self._json({"archivo": salida.name})
            else:
                self._error("Ruta no encontrada", 404)
        except (ValueError, FileNotFoundError) as e:
            self._error(str(e))

    def _post_login(self, cuerpo: bytes):
        if not MODO_PUBLICO:
            self._json({"ok": True, "modo_publico": False})
            return
        try:
            datos = json.loads(cuerpo.decode("utf-8")) if cuerpo else {}
        except json.JSONDecodeError:
            datos = {}
        intento = str(datos.get("password", ""))
        if not secrets.compare_digest(intento.encode(), PASSWORD.encode()):
            self._error("Contraseña incorrecta", 401)
            return
        sid, headers = self._set_cookie_sesion()
        with _SESIONES_LOCK:
            SESIONES[sid] = EstadoServidor()
        self._json({"ok": True}, extra_headers=headers)

    def _post_subir(self, ses: EstadoServidor, cuerpo: bytes):
        nombre = _sanear_nombre(unquote(self.headers.get("X-Filename", "archivo.pdf")))
        if not cuerpo:
            self._error("Archivo vacío")
            return
        destino = ses.dir_trabajo / "subidas" / nombre
        destino.write_bytes(cuerpo)
        self._json({"ok": True, "nombre": nombre, "bytes": len(cuerpo)})

    def _post_config(self, ses: EstadoServidor, datos: dict):
        st = ses.st
        for campo in ("publicacion", "periodo"):
            if campo in datos:
                setattr(st, campo, str(datos[campo]))
        if "ia_habilitada" in datos:
            st.ia_habilitada = bool(datos["ia_habilitada"])
        if isinstance(datos.get("api_keys"), dict):
            for prov, clave in datos["api_keys"].items():
                if prov in st.api_keys:
                    st.api_keys[prov] = str(clave)
        if "out_dir" in datos and not MODO_PUBLICO:
            st.out_dir = str(datos["out_dir"])
        self._json(_snapshot_estado(ses))

    def _post_conv(self, ses: EstadoServidor, datos: dict):
        if MODO_PUBLICO:
            carpeta = ses.dir_trabajo / "subidas"
        else:
            carpeta = (
                Path(datos["carpeta"]) if datos.get("carpeta") else ses.dir_trabajo / "subidas"
            )
            if not carpeta.is_dir():
                self._error(f"Carpeta no encontrada: {carpeta}")
                return
        if not list(carpeta.glob("*.pdf")) and not list(carpeta.glob("*.PDF")):
            self._error("No hay PDFs en la carpeta de entrada")
            return
        t = _trabajo_convertir(ses, carpeta)
        self._json({"trabajo": t.id})


# ══════════════════════════════════════════════════════════════════════════════
# ARRANQUE
# ══════════════════════════════════════════════════════════════════════════════
def crear_servidor(puerto: int = PUERTO) -> ThreadingHTTPServer:
    servidor = ThreadingHTTPServer(("0.0.0.0", puerto), ManejadorAPI)
    servidor.daemon_threads = True
    return servidor


def main():
    # La consola de Windows suele quedar en cp1252 (no soporta "→"); forzar
    # utf-8 con reemplazo evita que un print() tumbe el arranque del servidor.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    servidor = crear_servidor()
    modo = "PÚBLICO (multi-sesión con contraseña)" if MODO_PUBLICO else "local (un usuario)"
    print(f"Bashkar Station Web v{VERSION_WEB} — modo {modo}")
    print(f"  → http://127.0.0.1:{servidor.server_address[1]}")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nDetenido.")
        sys.exit(0)


if __name__ == "__main__":
    main()
